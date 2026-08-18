import os
import asyncio
import re
from dotenv import load_dotenv
from web3 import Web3
import httpx
import eth_utils
from eth_abi import decode as abi_decode
from eth_abi import encode as abi_encode
from genlayer_py.abi import calldata
from genlayer_py.abi.transactions import serialize
from web3.constants import ADDRESS_ZERO
from .network_config import get_network_config

load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), ".env"))

CONSENSUS_STATUS_BY_CODE = {
    0: "UNINITIALIZED", 1: "PENDING", 2: "PROPOSING", 3: "COMMITTING",
    4: "REVEALING", 5: "ACCEPTED", 6: "UNDETERMINED", 7: "FINALIZED",
    8: "CANCELED", 9: "APPEAL_REVEALING", 10: "APPEAL_COMMITTING",
    11: "READY_TO_FINALIZE", 12: "VALIDATORS_TIMEOUT", 13: "LEADER_TIMEOUT",
}
CONSENSUS_STATUS_CODE_BY_NAME = {status: code for code, status in CONSENSUS_STATUS_BY_CODE.items()}
CONSENSUS_TRANSACTION_ID_PATTERN = re.compile(r'^0x[a-fA-F0-9]{64}$')
BRADBURY_APPEAL_PROTOCOL_CONTRACTS = {
    'fee_manager_contract': {
        'address': '0xF205868bf5db79d2162843742D18D0900A9E462a',
        'abi': [{
            'type': 'function',
            'name': 'calculateMinAppealBond',
            'stateMutability': 'view',
            'inputs': [
                {'name': '_txId', 'type': 'bytes32'},
                {'name': '_round', 'type': 'uint256'},
                {'name': '_status', 'type': 'uint8'},
            ],
            'outputs': [{'name': 'totalFeesToPay', 'type': 'uint256'}],
        }],
    },
    'rounds_storage_contract': {
        'address': '0x7134D05af13A14c0b66Fe129fb930b1d0C420e33',
        'abi': [{
            'type': 'function',
            'name': 'getRoundNumber',
            'stateMutability': 'view',
            'inputs': [{'name': 'txId', 'type': 'bytes32'}],
            'outputs': [{'name': '', 'type': 'uint256'}],
        }],
    },
    'appeals_contract': {
        'address': '0xbb8C35AA878D09b9830aFF9e5aAC6492BFbd5471',
        'abi': [{
            'type': 'function',
            'name': 'canAppeal',
            'stateMutability': 'view',
            'inputs': [{'name': '_txId', 'type': 'bytes32'}],
            'outputs': [{'name': '', 'type': 'bool'}],
        }],
    },
}

EXECUTION_STATUS_NOT_VOTED = "NOT_VOTED"
EXECUTION_STATUS_FINISHED_WITH_RETURN = "FINISHED_WITH_RETURN"
EXECUTION_STATUS_FINISHED_WITH_ERROR = "FINISHED_WITH_ERROR"
EXECUTION_STATUS_UNKNOWN = "UNKNOWN"
EXECUTION_STATUS_BY_VALUE = {
    "NOT_VOTED": EXECUTION_STATUS_NOT_VOTED,
    "FINISHED_WITH_RETURN": EXECUTION_STATUS_FINISHED_WITH_RETURN,
    "FINISHED_WITH_ERROR": EXECUTION_STATUS_FINISHED_WITH_ERROR,
    "SUCCESS": EXECUTION_STATUS_FINISHED_WITH_RETURN,
    "ERROR": EXECUTION_STATUS_FINISHED_WITH_ERROR,
}
TRANSACTION_RESULT_BY_CODE = {
    0: "IDLE", 1: "AGREE", 2: "DISAGREE", 3: "TIMEOUT",
    4: "DETERMINISTIC_VIOLATION", 5: "NO_MAJORITY",
    6: "MAJORITY_AGREE", 7: "MAJORITY_DISAGREE",
}

def make_calldata_object(
    method: str | None = None,
    args: list | None = None,
    kwargs: dict | None = None,
):
    ret = {}
    if method is not None:
        ret["method"] = method
    if args is not None and len(args) > 0:
        ret["args"] = args
    if kwargs is not None and isinstance(kwargs, dict) and kwargs:
        ret["kwargs"] = kwargs
    return ret

class GenLayerClientWrapper:
    def __init__(self, network: str | None = None):
        self.network, rpc_url, chain_id = get_network_config(network)

        self.rpc_url = rpc_url
        self.chain_id = chain_id
        self.rpc_timeout_sec = min(max(float(os.getenv("RPC_REQUEST_TIMEOUT_SEC", "15")), 1.0), 60.0)
        self.rpc_max_attempts = min(max(int(os.getenv("RPC_MAX_ATTEMPTS", "3")), 1), 5)
        self.rpc_retry_backoff_sec = min(max(float(os.getenv("RPC_RETRY_BACKOFF_SEC", "0.25")), 0.0), 5.0)
        self.receipt_timeout_sec = int(os.getenv("TX_RECEIPT_TIMEOUT_SEC", "45"))
        self.receipt_poll_interval_sec = float(os.getenv("TX_RECEIPT_POLL_INTERVAL_SEC", "1.5"))
        self._http_client: httpx.AsyncClient | None = None

    def _get_http_client(self) -> httpx.AsyncClient:
        if self._http_client is None or self._http_client.is_closed:
            self._http_client = httpx.AsyncClient(
                timeout=httpx.Timeout(self.rpc_timeout_sec),
                limits=httpx.Limits(max_connections=50, max_keepalive_connections=20),
            )
        return self._http_client

    async def close(self) -> None:
        if self._http_client is not None and not self._http_client.is_closed:
            await self._http_client.aclose()

    async def _rpc_call(self, method: str, params: list):
        payload = {
            "jsonrpc": "2.0",
            "method": method,
            "params": params,
            "id": 1,
        }
        client = self._get_http_client()
        for attempt in range(1, self.rpc_max_attempts + 1):
            try:
                response = await client.post(self.rpc_url, json=payload)
                response.raise_for_status()
            except httpx.HTTPStatusError as exc:
                retriable = exc.response.status_code == 429 or exc.response.status_code >= 500
                if not retriable or attempt == self.rpc_max_attempts:
                    raise
            except (httpx.TimeoutException, httpx.TransportError):
                if attempt == self.rpc_max_attempts:
                    raise
            else:
                try:
                    data = response.json()
                except ValueError as exc:
                    raise RuntimeError("RPC returned an invalid JSON response.") from exc
                if not isinstance(data, dict):
                    raise RuntimeError("RPC returned an invalid response envelope.")
                if data.get("error"):
                    error = data["error"]
                    message = error.get("message") if isinstance(error, dict) else str(error)
                    raise RuntimeError(message or "RPC request failed.")
                return data.get("result")
            await asyncio.sleep(self.rpc_retry_backoff_sec * attempt)
        raise RuntimeError("RPC request failed after bounded retries.")

    def _chain_config(self):
        if self.network == "studionet":
            from genlayer_py.chains.studionet import studionet

            return studionet

        from genlayer_py.chains.testnet_bradbury import testnet_bradbury

        return testnet_bradbury

    @staticmethod
    def _validate_consensus_transaction_id(consensus_tx_id: str) -> str:
        if not isinstance(consensus_tx_id, str) or not CONSENSUS_TRANSACTION_ID_PATTERN.fullmatch(consensus_tx_id):
            raise ValueError('consensus_tx_id must be a 32-byte hex string with a 0x prefix')
        return consensus_tx_id.lower()

    def _protocol_contract_for_function(self, function_name: str) -> tuple[dict, str, dict]:
        chain = self._chain_config()
        fallback_contracts = (
            BRADBURY_APPEAL_PROTOCOL_CONTRACTS
            if self.network == 'bradbury'
            else {}
        )
        candidates = (
            (
                getattr(chain, 'appeals_contract', None)
                or fallback_contracts.get('appeals_contract'),
                (
                    f'GENLAYER_APPEALS_CONTRACT_ADDRESS_{self.network.upper()}',
                    'GENLAYER_APPEALS_CONTRACT_ADDRESS',
                ),
            ),
            (
                getattr(chain, 'rounds_storage_contract', None)
                or fallback_contracts.get('rounds_storage_contract'),
                (
                    f'GENLAYER_ROUNDS_STORAGE_CONTRACT_ADDRESS_{self.network.upper()}',
                    'GENLAYER_ROUNDS_STORAGE_CONTRACT_ADDRESS',
                ),
            ),
            (
                getattr(chain, 'fee_manager_contract', None)
                or fallback_contracts.get('fee_manager_contract'),
                (
                    f'GENLAYER_FEE_MANAGER_CONTRACT_ADDRESS_{self.network.upper()}',
                    'GENLAYER_FEE_MANAGER_CONTRACT_ADDRESS',
                ),
            ),
            (
                getattr(chain, 'consensus_main_contract', None),
                (
                    f'GENLAYER_CONSENSUS_CONTRACT_ADDRESS_{self.network.upper()}',
                    'GENLAYER_CONSENSUS_CONTRACT_ADDRESS',
                ),
            ),
        )
        for contract_config, override_names in candidates:
            if not isinstance(contract_config, dict):
                continue
            function_abi = next(
                (
                    entry
                    for entry in contract_config.get('abi', [])
                    if entry.get('type') == 'function' and entry.get('name') == function_name
                ),
                None,
            )
            if not function_abi:
                continue
            configured_address = next(
                (os.getenv(name) for name in override_names if os.getenv(name)),
                None,
            ) or contract_config.get('address')
            if not configured_address:
                raise RuntimeError(
                    f'Protocol contract address for {function_name} is not configured for {self.network}'
                )
            return contract_config, Web3.to_checksum_address(configured_address), function_abi
        raise RuntimeError(
            f'Protocol function {function_name} is not configured for {self.network}'
        )

    def _has_protocol_function(self, function_name: str) -> bool:
        try:
            self._protocol_contract_for_function(function_name)
            return True
        except RuntimeError as exc:
            if 'not configured' in str(exc):
                return False
            raise

    @staticmethod
    def _encode_protocol_function(function_abi: dict, args: list) -> str:
        input_types = [item['type'] for item in function_abi.get('inputs', [])]
        function_name = function_abi.get('name', 'protocol function')
        if len(input_types) != len(args):
            raise RuntimeError(f'Invalid argument count for {function_name}')
        signature = function_name + '(' + ','.join(input_types) + ')'
        selector = eth_utils.keccak(text=signature)[:4]
        encoded_args = abi_encode(input_types, args) if input_types else b''
        return '0x' + (selector + encoded_args).hex()

    async def _read_protocol_function(self, function_name: str, args: list):
        _, contract_address, function_abi = self._protocol_contract_for_function(function_name)
        encoded_data = self._encode_protocol_function(function_abi, args)
        result = await self._rpc_call(
            'eth_call',
            [{'to': contract_address, 'data': encoded_data}, 'latest'],
        )
        if not isinstance(result, str):
            raise RuntimeError(f'Protocol read {function_name} returned an invalid result')
        output_types = [item['type'] for item in function_abi.get('outputs', [])]
        if not output_types:
            return None
        encoded_result = result if result.startswith('0x') else f'0x{result}'
        decoded = abi_decode(output_types, Web3.to_bytes(hexstr=encoded_result))
        return decoded[0] if len(decoded) == 1 else decoded

    def _encode_deploy_contract_data(
        self,
        sender_address: str,
        code: str,
        args: list | None = None,
        kwargs: dict | None = None,
        consensus_max_rotations: int | None = None,
        leader_only: bool = False,
    ) -> tuple[str, str]:
        chain = self._chain_config()
        consensus_contract = chain.consensus_main_contract
        if not consensus_contract:
            raise RuntimeError(f"Consensus contract is not configured for {self.network}")
        consensus_address = (
            os.getenv(f"GENLAYER_CONSENSUS_CONTRACT_ADDRESS_{self.network.upper()}")
            or os.getenv("GENLAYER_CONSENSUS_CONTRACT_ADDRESS")
            or consensus_contract.get("address")
        )
        if not consensus_address:
            raise RuntimeError(f"Consensus contract is not configured for {self.network}")

        rotations = consensus_max_rotations or chain.default_consensus_max_rotations
        data = [
            code,
            calldata.encode(make_calldata_object(method=None, args=args or [], kwargs=kwargs or {})),
            leader_only,
        ]
        serialized_data = serialize(data)

        contract = Web3().eth.contract(abi=consensus_contract["abi"])
        contract_fn = contract.get_function_by_name("addTransaction")
        add_transaction_args = [
            Web3.to_checksum_address(sender_address),
            ADDRESS_ZERO,
            chain.default_number_of_initial_validators,
            rotations,
            Web3.to_bytes(hexstr=serialized_data),
        ]
        if len(contract_fn.argument_types) >= 6:
            add_transaction_args.append(0)

        params = abi_encode(contract_fn.argument_types, add_transaction_args)
        selector = eth_utils.keccak(text=contract_fn.signature)[:4].hex()
        return "0x" + selector + params.hex(), Web3.to_checksum_address(consensus_address)

    def _encode_contract_call_data(
        self,
        sender_address: str,
        contract_address: str,
        method: str,
        args: list | None = None,
        kwargs: dict | None = None,
        consensus_max_rotations: int | None = None,
        leader_only: bool = False,
    ) -> tuple[str, str]:
        chain = self._chain_config()
        consensus_contract = chain.consensus_main_contract
        if not consensus_contract:
            raise RuntimeError(f"Consensus contract is not configured for {self.network}")
        consensus_address = (
            os.getenv(f"GENLAYER_CONSENSUS_CONTRACT_ADDRESS_{self.network.upper()}")
            or os.getenv("GENLAYER_CONSENSUS_CONTRACT_ADDRESS")
            or consensus_contract.get("address")
        )
        if not consensus_address:
            raise RuntimeError(f"Consensus contract is not configured for {self.network}")

        rotations = consensus_max_rotations or chain.default_consensus_max_rotations
        serialized_data = serialize([
            calldata.encode(make_calldata_object(method=method, args=args or [], kwargs=kwargs or {})),
            leader_only,
        ])

        contract = Web3().eth.contract(abi=consensus_contract["abi"])
        contract_fn = contract.get_function_by_name("addTransaction")
        add_transaction_args = [
            Web3.to_checksum_address(sender_address),
            Web3.to_checksum_address(contract_address),
            chain.default_number_of_initial_validators,
            rotations,
            Web3.to_bytes(hexstr=serialized_data),
        ]
        if len(contract_fn.argument_types) >= 6:
            add_transaction_args.append(0)

        params = abi_encode(contract_fn.argument_types, add_transaction_args)
        selector = eth_utils.keccak(text=contract_fn.signature)[:4].hex()
        return "0x" + selector + params.hex(), Web3.to_checksum_address(consensus_address)

    async def _build_wallet_transaction(
        self,
        sender_address: str,
        to_address: str,
        encoded_data: str,
        value: int = 0,
        gas_limit: int | None = None,
        require_gas_estimate: bool = False,
    ) -> dict:
        checksum_sender = Web3.to_checksum_address(sender_address)
        nonce_hex = await self._rpc_call("eth_getTransactionCount", [checksum_sender, "pending"])
        nonce = int(nonce_hex, 16)

        tx_for_estimate = {
            "from": checksum_sender,
            "to": Web3.to_checksum_address(to_address),
            "data": encoded_data,
            "value": hex(value),
        }

        fee_fields: dict[str, int] = {}
        try:
            latest_block = await self._rpc_call("eth_getBlockByNumber", ["latest", False])
            base_fee_hex = latest_block.get("baseFeePerGas") if isinstance(latest_block, dict) else None
            if base_fee_hex:
                base_fee = int(base_fee_hex, 16)
                try:
                    priority_hex = await self._rpc_call("eth_maxPriorityFeePerGas", [])
                    priority_fee = int(priority_hex, 16)
                except Exception:
                    priority_fee = Web3.to_wei(2, "gwei")
                fee_fields["maxPriorityFeePerGas"] = priority_fee
                fee_fields["maxFeePerGas"] = base_fee + priority_fee
            else:
                gas_price_hex = await self._rpc_call("eth_gasPrice", [])
                fee_fields["gasPrice"] = int(gas_price_hex, 16)
        except Exception:
            try:
                gas_price_hex = await self._rpc_call("eth_gasPrice", [])
                fee_fields["gasPrice"] = int(gas_price_hex, 16)
            except Exception:
                pass

        estimated_gas = None
        if gas_limit is None or require_gas_estimate:
            try:
                gas_hex = await self._rpc_call(
                    'eth_estimateGas',
                    [{**tx_for_estimate, **{k: hex(v) for k, v in fee_fields.items()}}],
                )
                estimated_gas = int(gas_hex, 16)
                if estimated_gas <= 0:
                    raise RuntimeError('Gas estimate must be positive')
            except Exception as exc:
                if require_gas_estimate:
                    raise RuntimeError('Unable to verify the required transaction gas') from exc

        if gas_limit is not None:
            if estimated_gas is not None and gas_limit < estimated_gas:
                raise ValueError(
                    f'Gas limit {gas_limit} is below the network estimate of {estimated_gas}'
                )
            selected_gas_limit = gas_limit
        else:
            selected_gas_limit = estimated_gas or 1_500_000

        return {
            "to": Web3.to_checksum_address(to_address),
            "data": encoded_data,
            "value": value,
            "chain_id": self.chain_id,
            "nonce": nonce,
            "gas_limit": selected_gas_limit,
            **fee_fields,
        }

    async def build_deploy_transaction(
        self,
        sender_address: str,
        code: str,
        args: list | None = None,
        kwargs: dict | None = None,
        value: int = 0,
        gas_limit: int | None = None,
        consensus_max_rotations: int | None = None,
        leader_only: bool = False,
        ) -> dict:
        checksum_sender = Web3.to_checksum_address(sender_address)
        encoded_data, consensus_address = self._encode_deploy_contract_data(
            sender_address=checksum_sender,
            code=code,
            args=args,
            kwargs=kwargs,
            consensus_max_rotations=consensus_max_rotations,
            leader_only=leader_only,
        )
        return await self._build_wallet_transaction(
            sender_address=checksum_sender,
            to_address=consensus_address,
            encoded_data=encoded_data,
            value=value,
            gas_limit=gas_limit,
        )

    async def build_contract_call_transaction(
        self,
        sender_address: str,
        contract_address: str,
        method: str,
        args: list | None = None,
        kwargs: dict | None = None,
        value: int = 0,
        gas_limit: int | None = None,
        consensus_max_rotations: int | None = None,
        leader_only: bool = False,
    ) -> dict:
        checksum_sender = Web3.to_checksum_address(sender_address)
        encoded_data, consensus_address = self._encode_contract_call_data(
            sender_address=checksum_sender,
            contract_address=contract_address,
            method=method,
            args=args,
            kwargs=kwargs,
            consensus_max_rotations=consensus_max_rotations,
            leader_only=leader_only,
        )
        return await self._build_wallet_transaction(
            sender_address=checksum_sender,
            to_address=consensus_address,
            encoded_data=encoded_data,
            value=value,
            gas_limit=gas_limit,
        )

    async def read_contract(
        self,
        caller_address: str,
        contract_address: str,
        method: str,
        args: list | None = None,
        kwargs: dict | None = None,
    ):
        """Read finalized contract state without requiring a server-side private key."""
        serialized_data = serialize([
            calldata.encode(make_calldata_object(method=method, args=args or [], kwargs=kwargs or {})),
            b"\x00",
        ])
        result = await self._rpc_call(
            "gen_call",
            [{
                "type": "read",
                "to": Web3.to_checksum_address(contract_address),
                "from": Web3.to_checksum_address(caller_address),
                "data": serialized_data,
                "transaction_hash_variant": "latest-final",
            }],
        )
        if not isinstance(result, str):
            raise RuntimeError("GenLayer contract read returned an invalid result")
        encoded_result = result if result.startswith("0x") else f"0x{result}"
        return calldata.decode(Web3.to_bytes(hexstr=encoded_result))

    async def get_consensus_transaction_id(self, evm_tx_hash: str) -> str | None:
        receipt = await self._rpc_call("eth_getTransactionReceipt", [evm_tx_hash])
        if not receipt or not receipt.get("logs"):
            return None

        new_tx_topic = Web3.keccak(text="NewTransaction(bytes32,address,address)").hex().lower()
        created_tx_topic = Web3.keccak(text="CreatedTransaction(bytes32,uint256)").hex().lower()
        new_tx_topic = new_tx_topic if new_tx_topic.startswith("0x") else f"0x{new_tx_topic}"
        created_tx_topic = created_tx_topic if created_tx_topic.startswith("0x") else f"0x{created_tx_topic}"
        for log in receipt["logs"]:
            topics = [str(topic).lower() for topic in log.get("topics", [])]
            if len(topics) > 1 and topics[0] in {new_tx_topic, created_tx_topic}:
                return topics[1]

        return None

    async def get_consensus_transaction_status(self, consensus_tx_id: str) -> dict:
        """Return the current GenLayer consensus state for a transaction id."""
        consensus_tx_id = self._validate_consensus_transaction_id(consensus_tx_id)
        try:
            result = await self._rpc_call("gen_getTransactionStatus", [{"txId": consensus_tx_id}])
        except Exception:
            result = await self._rpc_call("gen_getTransactionStatus", [consensus_tx_id])

        raw_status = result.get("status") if isinstance(result, dict) else result
        raw_code = result.get("statusCode") if isinstance(result, dict) else None
        if hasattr(raw_status, "value"):
            raw_status = raw_status.value

        status_code = None
        if isinstance(raw_code, str):
            status_code = int(raw_code, 16) if raw_code.startswith("0x") else int(raw_code)
        elif isinstance(raw_code, int):
            status_code = raw_code

        if isinstance(raw_status, int):
            status_code = raw_status
            status = CONSENSUS_STATUS_BY_CODE.get(raw_status, "UNKNOWN")
        elif isinstance(raw_status, str):
            normalized_status = raw_status.strip().upper()
            if normalized_status.startswith("0X"):
                status_code = int(normalized_status, 16)
                status = CONSENSUS_STATUS_BY_CODE.get(status_code, "UNKNOWN")
            else:
                status = normalized_status
                status_code = status_code if status_code is not None else CONSENSUS_STATUS_CODE_BY_NAME.get(status)
        elif status_code is not None:
            status = CONSENSUS_STATUS_BY_CODE.get(status_code, "UNKNOWN")
        else:
            status = "UNINITIALIZED"

        return {
            "status": status,
            "statusCode": status_code,
            "final": status == "FINALIZED",
            "appealable": status in {"ACCEPTED", "UNDETERMINED"},
            "terminal": status in {"FINALIZED", "CANCELED", "UNDETERMINED", "VALIDATORS_TIMEOUT", "LEADER_TIMEOUT"},
        }

    @staticmethod
    def _normalize_address(value) -> str | None:
        if not isinstance(value, str) or not re.fullmatch(r"0x[a-fA-F0-9]{40}", value):
            return None
        return Web3.to_checksum_address(value)

    def _extract_contract_address(self, transaction) -> str | None:
        if not isinstance(transaction, dict):
            return None

        # genlayer-py uses tx_data_decoded, while Studio receipts expose data.
        for container_key in ("tx_data_decoded", "txDataDecoded", "data"):
            container = transaction.get(container_key)
            if not isinstance(container, dict):
                continue
            for address_key in ("contract_address", "contractAddress"):
                address = self._normalize_address(container.get(address_key))
                if address:
                    return address

        for address_key in ("contract_address", "contractAddress"):
            address = self._normalize_address(transaction.get(address_key))
            if address:
                return address

        transaction_type = transaction.get("type")
        if transaction_type in ("deploy", "DEPLOY", 0):
            return self._normalize_address(
                transaction.get("recipient") or transaction.get("to_address")
            )
        return None

    @staticmethod
    def _normalize_execution_status(value) -> str:
        if hasattr(value, "value"):
            value = value.value
        if not isinstance(value, str):
            return EXECUTION_STATUS_UNKNOWN
        return EXECUTION_STATUS_BY_VALUE.get(value.strip().upper(), EXECUTION_STATUS_UNKNOWN)

    @classmethod
    def _extract_execution_status(cls, transaction) -> str:
        if not isinstance(transaction, dict):
            return EXECUTION_STATUS_UNKNOWN

        candidates = []
        for key in (
            "tx_execution_result_name",
            "txExecutionResultName",
            "execution_result",
            "executionResult",
        ):
            candidates.append(transaction.get(key))

        consensus_data = transaction.get("consensus_data") or transaction.get("consensusData")
        if isinstance(consensus_data, dict):
            leader_receipts = consensus_data.get("leader_receipt") or consensus_data.get("leaderReceipt")
            if isinstance(leader_receipts, dict):
                leader_receipts = [leader_receipts]
            if isinstance(leader_receipts, (list, tuple)):
                for receipt in leader_receipts:
                    if not isinstance(receipt, dict):
                        continue
                    for key in (
                        "tx_execution_result_name",
                        "txExecutionResultName",
                        "execution_result",
                        "executionResult",
                    ):
                        candidates.append(receipt.get(key))
                    result = receipt.get("result")
                    if isinstance(result, dict):
                        candidates.append(result.get("status"))

        for candidate in candidates:
            execution_status = cls._normalize_execution_status(candidate)
            if execution_status != EXECUTION_STATUS_UNKNOWN:
                return execution_status
        return EXECUTION_STATUS_UNKNOWN

    async def get_transaction_details(self, consensus_tx_id: str | None) -> dict:
        if not consensus_tx_id:
            return {"execution_status": EXECUTION_STATUS_UNKNOWN, "transaction": None}

        try:
            chain = self._chain_config()
            from genlayer_py.client import create_client

            client = create_client(chain=chain, endpoint=self.rpc_url)
            transaction = await asyncio.to_thread(client.get_transaction, consensus_tx_id)
            return {
                "execution_status": self._extract_execution_status(transaction),
                "transaction": transaction,
            }
        except Exception:
            return {"execution_status": EXECUTION_STATUS_UNKNOWN, "transaction": None}

    async def get_protocol_transaction_diagnostics(self, consensus_tx_id: str) -> dict:
        """Read protocol-level outcome details that the SDK may omit."""
        consensus_tx_id = self._validate_consensus_transaction_id(consensus_tx_id)
        transaction = await self._rpc_call("eth_getTransactionByHash", [consensus_tx_id])
        if not isinstance(transaction, dict):
            return {"protocol_result": None, "num_rounds": None, "validator_count": None, "vote_count": None, "zero_round_no_majority": False, "transaction": transaction}
        raw_result = transaction.get("result_name") or transaction.get("resultName")
        if hasattr(raw_result, "value"):
            raw_result = raw_result.value
        if isinstance(raw_result, str):
            protocol_result = raw_result.strip().upper()
        else:
            result_code = transaction.get("result")
            if isinstance(result_code, str):
                try:
                    result_code = int(result_code, 16) if result_code.startswith("0x") else int(result_code)
                except ValueError:
                    result_code = None
            protocol_result = TRANSACTION_RESULT_BY_CODE.get(result_code)
        raw_rounds = transaction.get("num_of_rounds", transaction.get("numOfRounds"))
        try:
            num_rounds = int(raw_rounds, 16) if isinstance(raw_rounds, str) and raw_rounds.startswith("0x") else int(raw_rounds)
        except (TypeError, ValueError):
            num_rounds = None
        last_round = transaction.get("last_round") or transaction.get("lastRound") or {}
        validators = last_round.get("round_validators") or last_round.get("roundValidators") or []
        validator_count = len(validators) if isinstance(validators, (list, tuple)) else None
        votes = last_round.get("votes") or transaction.get("votes") or []
        vote_count = len(votes) if isinstance(votes, (list, tuple, dict)) else None
        zero_round_no_majority = protocol_result == "NO_MAJORITY" and num_rounds == 0 and validator_count in {0, None}
        return {"protocol_result": protocol_result, "num_rounds": num_rounds, "validator_count": validator_count, "vote_count": vote_count, "zero_round_no_majority": zero_round_no_majority, "transaction": transaction}

    async def get_deployment_details(self, consensus_tx_id: str | None, transaction=None) -> dict:
        if not consensus_tx_id:
            return {"contract_address": None, "derived_addresses": []}

        try:
            chain = self._chain_config()
            from genlayer_py.client import create_client

            client = create_client(chain=chain, endpoint=self.rpc_url)
            if transaction is None:
                transaction = await asyncio.to_thread(client.get_transaction, consensus_tx_id)
            contract_address = self._extract_contract_address(transaction)
            derived_addresses: set[str] = set()

            triggered_ids = []
            if isinstance(transaction, dict):
                for key in ("triggered_transactions", "triggered_transaction_ids", "triggeredTransactions"):
                    value = transaction.get(key)
                    if isinstance(value, (list, tuple, set)):
                        triggered_ids.extend(value)

            for triggered_id in triggered_ids:
                if not triggered_id:
                    continue
                try:
                    child_transaction = await asyncio.to_thread(client.get_transaction, triggered_id)
                except Exception:
                    continue
                child_address = self._extract_contract_address(child_transaction)
                if child_address and child_address != contract_address:
                    derived_addresses.add(child_address)

            return {
                "contract_address": contract_address,
                "derived_addresses": sorted(derived_addresses),
            }
        except Exception:
            return {"contract_address": None, "derived_addresses": []}

    async def get_balance(self, address: str) -> float:
        checksum_address = Web3.to_checksum_address(address)
        balance_hex = await self._rpc_call("eth_getBalance", [checksum_address, "latest"])
        balance_wei = int(balance_hex, 16)
        # GenLayer uses 18 decimals like ETH
        return float(Web3.from_wei(balance_wei, 'ether'))

    async def debug_trace_transaction(self, tx_hash: str) -> dict:
        """Get a debug trace for a GenLayer consensus transaction."""
        result = await self._rpc_call("debug_traceTransaction", [tx_hash])
        return result if isinstance(result, dict) else {"raw": result}

    async def build_appeal_transaction(
        self,
        sender_address: str,
        consensus_tx_id: str,
        bond_wei: int | None = None,
        gas_limit: int | None = None,
    ) -> dict:
        """Build a wallet-reviewed protocol appeal with verified bond and gas."""
        consensus_tx_id = self._validate_consensus_transaction_id(consensus_tx_id)
        requirements = await self.get_appeal_requirements(consensus_tx_id)
        if not requirements['appeal_window_open']:
            raise ValueError(
                f"Transaction is not appealable in status {requirements['consensus_status']}"
            )

        minimum_bond = requirements['minimum_appeal_bond_wei']
        selected_bond = minimum_bond if bond_wei is None else int(bond_wei)
        if selected_bond < minimum_bond:
            raise ValueError(
                f'Appeal bond {selected_bond} wei is below the required minimum of {minimum_bond} wei'
            )

        _, consensus_address, appeal_function_abi = self._protocol_contract_for_function(
            'submitAppeal'
        )
        checksum_sender = Web3.to_checksum_address(sender_address)
        appeal_data = self._encode_protocol_function(
            appeal_function_abi,
            [Web3.to_bytes(hexstr=consensus_tx_id)],
        )

        tx = await self._build_wallet_transaction(
            sender_address=checksum_sender,
            to_address=consensus_address,
            encoded_data=appeal_data,
            value=selected_bond,
            gas_limit=gas_limit,
            require_gas_estimate=True,
        )
        return {**tx, 'appeal_requirements': requirements}

    async def get_appeal_requirements(self, consensus_tx_id: str) -> dict:
        """Read the authoritative appeal window and minimum bond from protocol contracts."""
        consensus_tx_id = self._validate_consensus_transaction_id(consensus_tx_id)
        tx_id_bytes = Web3.to_bytes(hexstr=consensus_tx_id)
        status_result = await self.get_consensus_transaction_status(consensus_tx_id)
        status_code = status_result['statusCode']
        if status_code is None:
            status_code = CONSENSUS_STATUS_CODE_BY_NAME.get(
                status_result['status'],
                0,
            )

        if not self._has_protocol_function('canAppeal'):
            raise RuntimeError('Authoritative appeal-window function canAppeal is not configured for this network')
        can_appeal = bool(await self._read_protocol_function('canAppeal', [tx_id_bytes]))
        appeal_window_source = 'protocol_can_appeal'

        if not self._has_protocol_function('getRoundNumber'):
            raise RuntimeError('Authoritative appeal round function getRoundNumber is not configured for this network')
        if not self._has_protocol_function('calculateMinAppealBond'):
            raise RuntimeError('Authoritative minimum appeal bond function calculateMinAppealBond is not configured for this network')
        round_number = int(await self._read_protocol_function('getRoundNumber', [tx_id_bytes]))
        transaction_details = await self.get_transaction_details(consensus_tx_id)
        transaction = transaction_details.get('transaction') if isinstance(transaction_details, dict) else None
        raw_transaction_status = transaction.get('status') if isinstance(transaction, dict) else None
        if hasattr(raw_transaction_status, 'value'):
            raw_transaction_status = raw_transaction_status.value
        try:
            transaction_status = int(raw_transaction_status, 16) if isinstance(raw_transaction_status, str) and raw_transaction_status.startswith('0x') else int(raw_transaction_status)
        except (TypeError, ValueError):
            raise RuntimeError('Authoritative transaction status is unavailable for appeal bond calculation')
        minimum_bond = int(await self._read_protocol_function('calculateMinAppealBond', [tx_id_bytes, round_number, transaction_status]))
        if minimum_bond <= 0:
            raise RuntimeError('Protocol returned an invalid minimum appeal bond')
        return {
            'consensus_tx_id': consensus_tx_id,
            'consensus_status': status_result['status'],
            'appeal_window_open': can_appeal,
            'appeal_window_status': 'open' if can_appeal else 'closed',
            'minimum_appeal_bond_wei': minimum_bond,
            'appeal_window_source': appeal_window_source,
            'minimum_appeal_bond_source': 'protocol_calculate_min_appeal_bond',
            'appeal_round': round_number,
            'appeal_status_code': transaction_status,
        }

    async def _wait_for_receipt_or_raise(self, tx_hash: str):
        loop = asyncio.get_event_loop()
        deadline = loop.time() + self.receipt_timeout_sec
        while loop.time() < deadline:
            receipt = await self._rpc_call("eth_getTransactionReceipt", [tx_hash])
            if receipt:
                status_hex = receipt.get("status")
                if status_hex in ("0x1", 1):
                    return
                raise RuntimeError(
                    f"Transaction reverted on-chain. status={status_hex}"
                )
            await asyncio.sleep(self.receipt_poll_interval_sec)
        raise RuntimeError(
            f"Timed out waiting for transaction receipt after {self.receipt_timeout_sec}s"
        )

_client_wrapper = None
_network_clients = {}

def get_client(network: str | None = None):
    global _client_wrapper
    global _network_clients
    if network is None:
        if _client_wrapper is None:
            _client_wrapper = GenLayerClientWrapper()
        return _client_wrapper

    if network not in _network_clients:
        _network_clients[network] = GenLayerClientWrapper(network=network)
    return _network_clients[network]


async def close_clients() -> None:
    global _client_wrapper
    global _network_clients
    clients = [client for client in [_client_wrapper, *_network_clients.values()] if client]
    await asyncio.gather(*(client.close() for client in clients), return_exceptions=True)
    _client_wrapper = None
    _network_clients = {}

async def get_balance(address: str, network: str | None = None) -> float:
    return await get_client(network=network).get_balance(address)
