import os
import asyncio
import re
from dotenv import load_dotenv
from web3 import Web3
import httpx
import eth_utils
from eth_abi import encode as abi_encode
from genlayer_py.abi import calldata
from genlayer_py.abi.transactions import serialize
from web3.constants import ADDRESS_ZERO
from .network_config import get_network_config

load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), ".env"))

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
        self.receipt_timeout_sec = int(os.getenv("TX_RECEIPT_TIMEOUT_SEC", "45"))
        self.receipt_poll_interval_sec = float(os.getenv("TX_RECEIPT_POLL_INTERVAL_SEC", "1.5"))

    async def _rpc_call(self, method: str, params: list):
        payload = {
            "jsonrpc": "2.0",
            "method": method,
            "params": params,
            "id": 1,
        }
        async with httpx.AsyncClient() as client:
            response = await client.post(self.rpc_url, json=payload, timeout=30.0)
        response.raise_for_status()
        data = response.json()
        if "error" in data and data["error"]:
            raise RuntimeError(data["error"].get("message", str(data["error"])))
        return data.get("result")

    def _chain_config(self):
        if self.network == "studionet":
            from genlayer_py.chains.studionet import studionet

            return studionet

        from genlayer_py.chains.testnet_bradbury import testnet_bradbury

        return testnet_bradbury

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
        consensus_address = os.getenv("GENLAYER_CONSENSUS_CONTRACT_ADDRESS")
        if not consensus_address:
            raise RuntimeError("GENLAYER_CONSENSUS_CONTRACT_ADDRESS is not set")

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
        consensus_address = os.getenv("GENLAYER_CONSENSUS_CONTRACT_ADDRESS")
        if not consensus_address:
            raise RuntimeError("GENLAYER_CONSENSUS_CONTRACT_ADDRESS is not set")

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

        estimated_gas = gas_limit
        if estimated_gas is None:
            try:
                gas_hex = await self._rpc_call("eth_estimateGas", [{**tx_for_estimate, **{k: hex(v) for k, v in fee_fields.items()}}])
                estimated_gas = int(gas_hex, 16)
            except Exception:
                estimated_gas = 1_500_000

        return {
            "to": Web3.to_checksum_address(to_address),
            "data": encoded_data,
            "value": value,
            "chain_id": self.chain_id,
            "nonce": nonce,
            "gas_limit": estimated_gas,
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

    async def get_consensus_transaction_id(self, evm_tx_hash: str) -> str | None:
        receipt = await self._rpc_call("eth_getTransactionReceipt", [evm_tx_hash])
        if not receipt or not receipt.get("logs"):
            return None

        new_tx_topic = Web3.keccak(text="NewTransaction(bytes32,address,address)").hex().lower()
        created_tx_topic = Web3.keccak(text="CreatedTransaction(bytes32,uint256)").hex().lower()
        for log in receipt["logs"]:
            topics = [str(topic).lower() for topic in log.get("topics", [])]
            if len(topics) > 1 and topics[0] in {new_tx_topic, created_tx_topic}:
                return topics[1]

        return None

    def _collect_addresses(self, value, found: set[str]):
        if isinstance(value, str):
            if re.fullmatch(r"0x[a-fA-F0-9]{40}", value):
                found.add(Web3.to_checksum_address(value))
            return
        if isinstance(value, dict):
            for nested_value in value.values():
                self._collect_addresses(nested_value, found)
            return
        if isinstance(value, (list, tuple, set)):
            for nested_value in value:
                self._collect_addresses(nested_value, found)

    async def get_deployment_details(self, consensus_tx_id: str | None) -> dict:
        if not consensus_tx_id:
            return {"contract_address": None, "derived_addresses": []}

        try:
            chain = self._chain_config()
            from genlayer_py.client import create_client

            client = create_client(chain=chain, endpoint=self.rpc_url)
            transaction = client.get_transaction(consensus_tx_id)
            found_addresses: set[str] = set()
            self._collect_addresses(transaction, found_addresses)

            contract_address = None
            tx_data_decoded = transaction.get("tx_data_decoded") if isinstance(transaction, dict) else None
            if isinstance(tx_data_decoded, dict):
                candidate = tx_data_decoded.get("contract_address")
                if isinstance(candidate, str) and re.fullmatch(r"0x[a-fA-F0-9]{40}", candidate):
                    contract_address = Web3.to_checksum_address(candidate)
                    found_addresses.add(contract_address)

            if contract_address:
                derived_addresses = [address for address in sorted(found_addresses) if address != contract_address]
            else:
                derived_addresses = sorted(found_addresses)

            return {
                "contract_address": contract_address,
                "derived_addresses": derived_addresses,
            }
        except Exception:
            return {"contract_address": None, "derived_addresses": []}

    async def get_balance(self, address: str) -> float:
        checksum_address = Web3.to_checksum_address(address)
        balance_hex = await self._rpc_call("eth_getBalance", [checksum_address, "latest"])
        balance_wei = int(balance_hex, 16)
        # GenLayer uses 18 decimals like ETH
        return float(Web3.from_wei(balance_wei, 'ether'))

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

async def get_balance(address: str, network: str | None = None) -> float:
    return await get_client(network=network).get_balance(address)
