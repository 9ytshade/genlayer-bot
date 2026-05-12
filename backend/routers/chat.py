from fastapi import APIRouter, HTTPException, Header, Query
from pydantic import BaseModel, Field
from web3 import Web3
import os
from typing import Any

try:
    from ..intent_parser import parse_intent
    from ..contract_validation import validate_python_contract
    from ..safety import validate_intent, normalize_intent
    from ..simulator import simulate_intent
    from ..genlayer_client import send_transfer, get_balance, get_client
    from ..network_config import normalize_network
except ImportError:
    from intent_parser import parse_intent
    from contract_validation import validate_python_contract
    from safety import validate_intent, normalize_intent
    from simulator import simulate_intent
    from genlayer_client import send_transfer, get_balance, get_client
    from network_config import normalize_network

try:
    from ..logs_store import logs_store
except ImportError:
    from logs_store import logs_store

router = APIRouter(prefix="/chat", tags=["chat"])

class ChatRequest(BaseModel):
    message: str
    wallet_address: str | None = None
    network: str | None = None

class ConfirmRequest(BaseModel):
    intent: dict
    wallet_address: str | None = None
    signed_transaction: str | None = None  # Pre-signed raw transaction from user wallet
    tx_hash: str | None = None  # Transaction hash from wallet-side broadcast
    network: str | None = None


class TxParamsResponse(BaseModel):
    chain_id: int
    gas_price: str  # In hex
    nonce: int
    gas_limit: int
    rpc_url: str


class DeployTxRequest(BaseModel):
    address: str
    code: str
    constructor_args: list[Any] = Field(default_factory=list)
    constructor_kwargs: dict[str, Any] = Field(default_factory=dict)
    value_wei: str = "0"
    gas_limit: int | None = None
    consensus_max_rotations: int | None = None
    leader_only: bool = False
    network: str | None = None


class DeployTxResponse(BaseModel):
    chain_id: int
    to: str
    data: str
    value: str
    nonce: int
    gas_limit: int
    rpc_url: str
    gas_price: str | None = None
    max_fee_per_gas: str | None = None
    max_priority_fee_per_gas: str | None = None


class ContractValidationRequest(BaseModel):
    code: str
    file_name: str | None = None


class ContractValidationResponse(BaseModel):
    valid: bool
    message: str
    errors: list[str]
    warnings: list[str]
    contract_names: list[str] = Field(default_factory=list)


def get_wallet_address(authorization: str | None = Header(None)) -> str | None:
    if not authorization or not authorization.startswith("Bearer "):
        return None
    token = authorization.split(" ", 1)[1].strip()
    return token


def resolve_balance_address(header_address: str | None) -> str:
    if header_address:
        return header_address

    env_address = os.getenv("WALLET_ADDRESS")
    if env_address:
        return env_address

    raise HTTPException(status_code=400, detail="No wallet address provided for balance lookup")


def get_private_key_or_raise() -> str:
    private_key = os.getenv("WALLET_PRIVATE_KEY")
    if not private_key:
        raise HTTPException(status_code=500, detail="Server wallet private key is not configured")
    return private_key


def resolve_network_or_400(network: str | None) -> str:
    try:
        return normalize_network(network)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

@router.post("")
async def handle_chat(request: ChatRequest):
    network = resolve_network_or_400(request.network)
    await logs_store.append(
        "INFO",
        "CHAT_RECEIVED",
        "User message received.",
        {"message": request.message, "wallet_address": request.wallet_address, "network": network},
    )

    intent = normalize_intent(parse_intent(request.message))

    if intent.get("action") == "deploy_contract" and intent.get("code"):
        validation = validate_python_contract(str(intent["code"]))
        if not validation["valid"]:
            await logs_store.append("ERROR", "DEPLOY_CONTRACT_INVALID", "Uploaded contract failed validation.", {"errors": validation["errors"]})
            return {
                "content": validation["message"],
                "intent": intent,
                "status": "error",
                "validation": validation,
            }
            
    # Contextualize intent for the connected user
    if request.wallet_address:
        # If user asks "what's my balance", ensure we use their connected address
        if intent["action"] == "check_balance" and not intent.get("address"):
            intent["address"] = request.wallet_address
            
    await logs_store.append("INFO", "INTENT_PARSED", "Intent parsed.", {"intent": intent})

    if intent["action"] == "unknown":
        await logs_store.append("WARN", "INTENT_UNKNOWN", "Unable to parse user intent.")
        return {
            "content": "I couldn't understand that. You can say something like 'Send 10 GEN to alex' or 'Check my balance'.",
            "intent": intent,
        }

    is_safe, error_msg = validate_intent(intent)
    if not is_safe:
        await logs_store.append("ERROR", "SAFETY_BLOCK", "Safety validation failed.", {"reason": error_msg, "intent": intent})
        return {
            "content": f"Safety check failed: {error_msg}",
            "intent": intent,
            "status": "error",
        }

    simulation = simulate_intent(intent)
    await logs_store.append("INFO", "SIMULATION_READY", "Simulation generated.", {"action": intent.get("action")})

    if intent["action"] == "check_balance":
        await logs_store.append("INFO", "AWAIT_CONFIRMATION", "Awaiting confirmation for balance check.")
        return {
            "content": "I can check your wallet balance. Do you want me to proceed?",
            "intent": intent,
            "status": "awaiting_confirmation",
        }

    if intent["action"] == "deploy_contract":
        if not intent.get("code"):
            return {
                "content": "Please provide the Python code for your GenLayer Intelligent Contract.",
                "intent": intent,
                "status": "awaiting_input",
            }
        await logs_store.append("INFO", "AWAIT_CONFIRMATION", "Awaiting confirmation for contract deployment.")
        return {
            "content": f"I'm ready to deploy your contract '{intent.get('contract_name', 'MyContract')}'. Do you want me to proceed?",
            "intent": intent,
            "status": "awaiting_confirmation",
        }

    await logs_store.append("INFO", "AWAIT_CONFIRMATION", "Awaiting confirmation for transfer.", {"intent": intent})
    return {
        "content": "I have parsed your intent and simulated the outcome. Please review and confirm execution.",
        "intent": intent,
        "simulation": simulation,
        "status": "awaiting_confirmation",
    }

@router.post("/confirm")
async def confirm_action(request: ConfirmRequest, authorization: str | None = Header(None)):
    intent = normalize_intent(request.intent)
    network = resolve_network_or_400(request.network)
    await logs_store.append("INFO", "CONFIRM_RECEIVED", "Execution confirmed by user.", {"intent": intent, "network": network})

    is_safe, error_msg = validate_intent(intent)
    if intent.get("action") != "check_balance" and not is_safe:
        await logs_store.append("ERROR", "SAFETY_BLOCK_CONFIRM", "Confirmation blocked by safety checks.", {"reason": error_msg, "intent": intent})
        raise HTTPException(status_code=400, detail=f"Safety check failed: {error_msg}")

    if intent["action"] == "check_balance":
        balance_address = resolve_balance_address(request.wallet_address or get_wallet_address(authorization))
        try:
            balance = await get_balance(balance_address, network=network)
            await logs_store.append("SUCCESS", "BALANCE_SUCCESS", "Balance read succeeded.", {"balance": balance})
            return {"balance": balance}
        except Exception as e:
            await logs_store.append("ERROR", "BALANCE_FAILED", "Balance fetch failed.", {"error": str(e)})
            raise HTTPException(status_code=502, detail=f"Balance fetch failed: {str(e)}")

    if intent["action"] == "transfer":
        if not request.signed_transaction and not request.tx_hash:
            raise HTTPException(status_code=400, detail="Transfer requires tx_hash or signed_transaction from user wallet")
        try:
            client = get_client(network=network)
            tx_hash = request.tx_hash or await client._rpc_call("eth_sendRawTransaction", [request.signed_transaction])
            await client._wait_for_receipt_or_raise(tx_hash)
            await logs_store.append("SUCCESS", "TRANSFER_SUCCESS", "Transfer broadcast succeeded.", {"txHash": tx_hash})
            return {"txHash": tx_hash}
        except Exception as e:
            await logs_store.append("ERROR", "TRANSFER_FAILED", "Transfer failed.", {"error": str(e), "intent": intent})
            raise HTTPException(status_code=502, detail=f"Transfer failed: {str(e)}")

    if intent["action"] == "deploy_contract":
        if not request.signed_transaction and not request.tx_hash:
            raise HTTPException(status_code=400, detail="Deploy requires tx_hash or signed_transaction from user wallet")
        try:
            await logs_store.append("INFO", "DEPLOY_START", "Starting contract deployment process...", {"contract_name": intent.get("contract_name", "MyContract")})
            await logs_store.append("INFO", "DEPLOY_COMPILING", "Compiling intelligent contract code...")
            await logs_store.append("INFO", "DEPLOY_ESTIMATING", "Estimating gas for deployment...")
            client = get_client(network=network)
            tx_hash = request.tx_hash or await client._rpc_call("eth_sendRawTransaction", [request.signed_transaction])
            await client._wait_for_receipt_or_raise(tx_hash)
            consensus_tx_id = await client.get_consensus_transaction_id(tx_hash)
            deployment_details = await client.get_deployment_details(consensus_tx_id)
            await logs_store.append(
                "SUCCESS",
                "DEPLOY_SUCCESS",
                "Contract deployment transaction accepted by Studionet.",
                {
                    "txHash": tx_hash,
                    "consensusTxId": consensus_tx_id,
                    "contractAddress": deployment_details["contract_address"],
                    "derivedAddresses": deployment_details["derived_addresses"],
                },
            )
            return {
                "txHash": tx_hash,
                "consensusTxId": consensus_tx_id,
                "contractAddress": deployment_details["contract_address"],
                "derivedAddresses": deployment_details["derived_addresses"],
                "content": "Intelligent Contract deployment submitted to GenLayer Studionet.",
            }
        except Exception as e:
            await logs_store.append("ERROR", "DEPLOY_FAILED", "Deployment process failed.", {"error": str(e), "intent": intent})
            raise HTTPException(status_code=502, detail=f"Deployment failed: {str(e)}")

    await logs_store.append("ERROR", "UNSUPPORTED_ACTION", "Unsupported action during confirmation.", {"intent": intent})
    raise HTTPException(status_code=400, detail="Unsupported action for execution")


@router.post("/deploy-tx")
async def build_deploy_tx(request: DeployTxRequest) -> DeployTxResponse:
    """Build the Studionet consensus-contract transaction for wallet-side deployment."""
    try:
        network = resolve_network_or_400(request.network)
        client = get_client(network=network)
        checksum_address = Web3.to_checksum_address(request.address)
        value = int(request.value_wei or "0")
        if value < 0:
            raise ValueError("Deployment value cannot be negative")
        if request.gas_limit is not None and request.gas_limit < 21000:
            raise ValueError("Gas limit is too low")

        await logs_store.append(
            "INFO",
            "DEPLOY_TX_BUILD",
            "Preparing GenLayer deployment transaction.",
            {
                "network": network,
                "from": checksum_address,
                "argsCount": len(request.constructor_args),
                "valueWei": str(value),
            },
        )
        tx = await client.build_deploy_transaction(
            sender_address=checksum_address,
            code=request.code,
            args=request.constructor_args,
            kwargs=request.constructor_kwargs,
            value=value,
            gas_limit=request.gas_limit,
            consensus_max_rotations=request.consensus_max_rotations,
            leader_only=request.leader_only,
        )
        return DeployTxResponse(
            chain_id=tx["chain_id"],
            to=tx["to"],
            data=tx["data"],
            value=str(tx["value"]),
            nonce=tx["nonce"],
            gas_limit=tx["gas_limit"],
            rpc_url=client.rpc_url,
            gas_price=str(tx["gasPrice"]) if "gasPrice" in tx else None,
            max_fee_per_gas=str(tx["maxFeePerGas"]) if "maxFeePerGas" in tx else None,
            max_priority_fee_per_gas=str(tx["maxPriorityFeePerGas"]) if "maxPriorityFeePerGas" in tx else None,
        )
    except Exception as e:
        await logs_store.append("ERROR", "DEPLOY_TX_BUILD_FAILED", "Failed to prepare deployment transaction.", {"error": str(e)})
        raise HTTPException(status_code=502, detail=f"Failed to prepare deployment transaction: {str(e)}")


@router.post("/validate-contract")
async def validate_contract(request: ContractValidationRequest) -> ContractValidationResponse:
    validation = validate_python_contract(request.code)
    await logs_store.append(
        "INFO" if validation["valid"] else "ERROR",
        "CONTRACT_VALIDATION",
        validation["message"],
        {"file_name": request.file_name, "errors": validation["errors"], "warnings": validation["warnings"]},
    )
    return ContractValidationResponse(**validation)


@router.get("/tx-params")
async def get_tx_params(address: str = Query(...), network: str | None = Query(default=None)) -> TxParamsResponse:
    """Get transaction parameters needed for client-side signing"""
    try:
        selected_network = resolve_network_or_400(network)
        client = get_client(network=selected_network)
        checksum_address = Web3.to_checksum_address(address)

        # Get current nonce
        nonce_hex = await client._rpc_call("eth_getTransactionCount", [checksum_address, "pending"])
        nonce = int(nonce_hex, 16)
        
        # Get gas price
        gas_price_hex = await client._rpc_call("eth_gasPrice", [])
        
        rpc_url = client.rpc_url
        chain_id = client.chain_id
        
        return TxParamsResponse(
            chain_id=chain_id,
            gas_price=gas_price_hex,
            nonce=nonce,
            gas_limit=21000,
            rpc_url=rpc_url
        )
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Failed to get transaction parameters: {str(e)}")
