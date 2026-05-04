from fastapi import APIRouter, HTTPException, Header, Query
from pydantic import BaseModel
from web3 import Web3
import os

try:
    from ..intent_parser import parse_intent
    from ..safety import validate_intent, normalize_intent
    from ..simulator import simulate_intent
    from ..genlayer_client import send_transfer, get_balance, deploy_contract
except ImportError:
    from intent_parser import parse_intent
    from safety import validate_intent, normalize_intent
    from simulator import simulate_intent
    from genlayer_client import send_transfer, get_balance, deploy_contract

try:
    from ..logs_store import logs_store
except ImportError:
    from logs_store import logs_store

router = APIRouter(prefix="/chat", tags=["chat"])

class ChatRequest(BaseModel):
    message: str
    wallet_address: str | None = None

class ConfirmRequest(BaseModel):
    intent: dict
    wallet_address: str | None = None
    signed_transaction: str | None = None  # Pre-signed raw transaction from user wallet


class TxParamsResponse(BaseModel):
    chain_id: int
    gas_price: str  # In hex
    nonce: int
    rpc_url: str


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

@router.post("")
async def handle_chat(request: ChatRequest):
    await logs_store.append("INFO", "CHAT_RECEIVED", "User message received.", {"message": request.message, "wallet_address": request.wallet_address})

    intent = normalize_intent(parse_intent(request.message))
    
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
    await logs_store.append("INFO", "CONFIRM_RECEIVED", "Execution confirmed by user.", {"intent": intent})

    is_safe, error_msg = validate_intent(intent)
    if intent.get("action") != "check_balance" and not is_safe:
        await logs_store.append("ERROR", "SAFETY_BLOCK_CONFIRM", "Confirmation blocked by safety checks.", {"reason": error_msg, "intent": intent})
        raise HTTPException(status_code=400, detail=f"Safety check failed: {error_msg}")

    if intent["action"] == "check_balance":
        balance_address = resolve_balance_address(request.wallet_address or get_wallet_address(authorization))
        try:
            balance = get_balance(balance_address)
            await logs_store.append("SUCCESS", "BALANCE_SUCCESS", "Balance read succeeded.", {"balance": balance})
            return {"balance": balance}
        except Exception as e:
            await logs_store.append("ERROR", "BALANCE_FAILED", "Balance fetch failed.", {"error": str(e)})
            raise HTTPException(status_code=502, detail=f"Balance fetch failed: {str(e)}")

    if intent["action"] == "transfer":
        if not request.signed_transaction:
            raise HTTPException(status_code=400, detail="Transfer requires signed_transaction from user wallet")
        try:
            from ..genlayer_client import get_client
            client = get_client()
            tx_hash = client._rpc_call("eth_sendRawTransaction", [request.signed_transaction])
            client._wait_for_receipt_or_raise(tx_hash)
            await logs_store.append("SUCCESS", "TRANSFER_SUCCESS", "Transfer broadcast succeeded.", {"txHash": tx_hash})
            return {"txHash": tx_hash}
        except Exception as e:
            await logs_store.append("ERROR", "TRANSFER_FAILED", "Transfer failed.", {"error": str(e), "intent": intent})
            raise HTTPException(status_code=502, detail=f"Transfer failed: {str(e)}")

    if intent["action"] == "deploy_contract":
        if not request.signed_transaction:
            raise HTTPException(status_code=400, detail="Deploy requires signed_transaction from user wallet")
        try:
            await logs_store.append("INFO", "DEPLOY_START", "Starting contract deployment process...", {"contract_name": intent.get("contract_name", "MyContract")})
            await logs_store.append("INFO", "DEPLOY_COMPILING", "Compiling intelligent contract code...")
            await logs_store.append("INFO", "DEPLOY_ESTIMATING", "Estimating gas for deployment...")
            from ..genlayer_client import get_client
            client = get_client()
            tx_hash = client._rpc_call("eth_sendRawTransaction", [request.signed_transaction])
            client._wait_for_receipt_or_raise(tx_hash)
            await logs_store.append("SUCCESS", "DEPLOY_SUCCESS", "Contract successfully deployed!", {"txHash": tx_hash})
            return {"txHash": tx_hash, "content": "Intelligent Contract successfully deployed."}
        except Exception as e:
            await logs_store.append("ERROR", "DEPLOY_FAILED", "Deployment process failed.", {"error": str(e), "intent": intent})
            raise HTTPException(status_code=502, detail=f"Deployment failed: {str(e)}")

    await logs_store.append("ERROR", "UNSUPPORTED_ACTION", "Unsupported action during confirmation.", {"intent": intent})
    raise HTTPException(status_code=400, detail="Unsupported action for execution")


@router.get("/tx-params")
async def get_tx_params(address: str = Query(...)) -> TxParamsResponse:
    """Get transaction parameters needed for client-side signing"""
    try:
        from ..genlayer_client import get_client
        client = get_client()
        checksum_address = Web3.to_checksum_address(address)

        # Get current nonce
        nonce_hex = client._rpc_call("eth_getTransactionCount", [checksum_address, "pending"])
        nonce = int(nonce_hex, 16)
        
        # Get gas price
        gas_price_hex = client._rpc_call("eth_gasPrice", [])
        
        rpc_url = os.getenv("GENLAYER_RPC_URL", "http://localhost:8545")
        chain_id = int(os.getenv("GENLAYER_CHAIN_ID", "4221"))
        
        return TxParamsResponse(
            chain_id=chain_id,
            gas_price=gas_price_hex,
            nonce=nonce,
            rpc_url=rpc_url
        )
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Failed to get transaction parameters: {str(e)}")

