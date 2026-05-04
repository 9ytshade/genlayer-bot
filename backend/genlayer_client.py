import os
import time
from dotenv import load_dotenv
from genlayer_py import create_account
from web3 import Web3
import httpx

load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), ".env"))

class GenLayerClientWrapper:
    def __init__(self, private_key: str = None):
        rpc_url = os.getenv("GENLAYER_RPC_URL")
        self.private_key = private_key or os.getenv("WALLET_PRIVATE_KEY")
        chain_id = int(os.getenv("GENLAYER_CHAIN_ID", "4221"))
        
        if not rpc_url:
            raise ValueError("GENLAYER_RPC_URL not found in environment variables")

        self.rpc_url = rpc_url
        self.chain_id = chain_id
        self.account = create_account(self.private_key) if self.private_key else None
        self.sender_address = self.account.address if self.account else None
        self.receipt_timeout_sec = int(os.getenv("TX_RECEIPT_TIMEOUT_SEC", "45"))
        self.receipt_poll_interval_sec = float(os.getenv("TX_RECEIPT_POLL_INTERVAL_SEC", "1.5"))

    def _rpc_call(self, method: str, params: list):
        payload = {
            "jsonrpc": "2.0",
            "method": method,
            "params": params,
            "id": 1,
        }
        response = httpx.post(self.rpc_url, json=payload, timeout=30.0)
        response.raise_for_status()
        data = response.json()

        if "error" in data and data["error"]:
            raise RuntimeError(data["error"].get("message", str(data["error"])))

        return data.get("result")

    def get_balance(self, address: str) -> float:
        try:
            checksum_address = Web3.to_checksum_address(address)
            balance_hex = self._rpc_call("eth_getBalance", [checksum_address, "latest"])
            balance_wei = int(balance_hex, 16)
            # GenLayer uses 18 decimals like ETH
            return float(Web3.from_wei(balance_wei, 'ether'))
        except Exception as e:
            print(f"Error fetching balance: {e}")
            return 0.0

    def send_transfer(self, to_address: str, amount: float) -> str:
        if not self.account or not self.sender_address:
            raise ValueError("Private key is required for sending transfers")

        try:
            # Sign locally and broadcast raw transaction to avoid RPC signer requirements.
            checksum_to = Web3.to_checksum_address(to_address)
            nonce_hex = self._rpc_call("eth_getTransactionCount", [self.sender_address, "pending"])
            nonce = int(nonce_hex, 16)
            value = Web3.to_wei(amount, "ether")

            tx_params = {
                "from": self.sender_address,
                "to": checksum_to,
                "value": value,
                "nonce": nonce,
                "chainId": self.chain_id,
            }

            try:
                gas_hex = self._rpc_call(
                    "eth_estimateGas",
                    [{"from": self.sender_address, "to": checksum_to, "value": hex(value)}],
                )
                tx_params["gas"] = int(gas_hex, 16)
            except Exception:
                tx_params["gas"] = 21000

            try:
                gas_price_hex = self._rpc_call("eth_gasPrice", [])
                tx_params["gasPrice"] = int(gas_price_hex, 16)
            except Exception:
                pass

            signed = self.account.sign_transaction(tx_params)
            raw_tx = Web3.to_hex(signed.raw_transaction)
            tx_hash = self._rpc_call("eth_sendRawTransaction", [raw_tx])
            self._wait_for_receipt_or_raise(tx_hash)
            return tx_hash
        except Exception as e:
            print(f"Error sending transfer: {e}")
            raise e

    def deploy_contract(self, code: str, args: list = []) -> str:
        if not self.account or not self.sender_address:
            raise ValueError("Private key is required for contract deployment")

        try:
            # Get latest nonce
            nonce_hex = self._rpc_call("eth_getTransactionCount", [self.sender_address, "pending"])
            nonce = int(nonce_hex, 16)

            # GenLayer deployment transaction
            tx_params = {
                "from": self.sender_address,
                "data": Web3.to_hex(text=code),
                "nonce": nonce,
                "chainId": self.chain_id,
                "value": 0,
            }

            # Estimate gas for deployment
            try:
                gas_hex = self._rpc_call(
                    "eth_estimateGas",
                    [{"from": self.sender_address, "data": tx_params["data"]}],
                )
                tx_params["gas"] = int(gas_hex, 16)
            except Exception:
                tx_params["gas"] = 1000000 # Default for deployment if estimation fails

            # Signed deployment
            signed = self.account.sign_transaction(tx_params)
            raw_tx = Web3.to_hex(signed.raw_transaction)
            tx_hash = self._rpc_call("eth_sendRawTransaction", [raw_tx])
            
            # Wait for receipt to ensure it's deployed
            self._wait_for_receipt_or_raise(tx_hash)
            return tx_hash
        except Exception as e:
            print(f"Error deploying contract: {e}")
            raise e

    def _wait_for_receipt_or_raise(self, tx_hash: str):
        deadline = time.time() + self.receipt_timeout_sec
        while time.time() < deadline:
            receipt = self._rpc_call("eth_getTransactionReceipt", [tx_hash])
            if receipt:
                status_hex = receipt.get("status")
                if status_hex in ("0x1", 1):
                    return
                raise RuntimeError(f"Transaction reverted on-chain. status={status_hex}")
            time.sleep(self.receipt_poll_interval_sec)

        raise RuntimeError(
            f"Timed out waiting for transaction receipt after {self.receipt_timeout_sec}s"
        )

_client_wrapper = None

def get_client(private_key: str = None):
    global _client_wrapper
    if private_key:
        return GenLayerClientWrapper(private_key)
    if _client_wrapper is None:
        _client_wrapper = GenLayerClientWrapper()
    return _client_wrapper

def get_balance(address: str, private_key: str = None) -> float:
    return get_client(private_key).get_balance(address)

def send_transfer(to_address: str, amount: float, private_key: str = None) -> str:
    return get_client(private_key).send_transfer(to_address, amount)

def deploy_contract(code: str, args: list = [], private_key: str = None) -> str:
    return get_client(private_key).deploy_contract(code, args)
