from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
import os

try:
    from ..intent_parser import parse_intent
    from ..safety import validate_intent, normalize_intent
    from ..simulator import simulate_intent
    from ..genlayer_client import send_transfer, get_balance
except ImportError:
    # Fallback when running from inside backend directory.
    from intent_parser import parse_intent
    from safety import validate_intent, normalize_intent
    from simulator import simulate_intent
    from genlayer_client import send_transfer, get_balance
try:
    from ..logs_store import logs_store
except ImportError:
    from logs_store import logs_store

router = APIRouter(prefix="/chat", tags=["chat"])

class ChatRequest(BaseModel):
    message: str

class ConfirmRequest(BaseModel):
    intent: dict

@router.post("")
async def handle_chat(request: ChatRequest):
    await logs_store.append("INFO", "CHAT_RECEIVED", "User message received.", {"message": request.message})
    intent = normalize_intent(parse_intent(request.message))
    await logs_store.append("INFO", "INTENT_PARSED", "Intent parsed.", {"intent": intent})
    
    if intent["action"] == "unknown":
        await logs_store.append("WARN", "INTENT_UNKNOWN", "Unable to parse user intent.")
        return {
            "content": "I couldn't understand that. You can say something like 'Send 10 GEN to alex' or 'Check my balance'.",
            "intent": intent
        }
        
    is_safe, error_msg = validate_intent(intent)
    if not is_safe:
        await logs_store.append("ERROR", "SAFETY_BLOCK", "Safety validation failed.", {"reason": error_msg, "intent": intent})
        return {
            "content": f"Safety check failed: {error_msg}",
            "intent": intent,
            "status": "error"
        }
        
    simulation = simulate_intent(intent)
    await logs_store.append("INFO", "SIMULATION_READY", "Simulation generated.", {"action": intent.get("action")})
    
    if intent["action"] == "check_balance":
        await logs_store.append("INFO", "AWAIT_CONFIRMATION", "Awaiting confirmation for balance check.")
        return {
            "content": "I can check your GenLayer wallet balance. Do you want me to proceed?",
            "intent": intent,
            "status": "awaiting_confirmation"
        }
        
    await logs_store.append("INFO", "AWAIT_CONFIRMATION", "Awaiting confirmation for transfer.", {"intent": intent})
    return {
        "content": "I have parsed your intent and simulated the outcome. Please review and confirm execution.",
        "intent": intent,
        "simulation": simulation,
        "status": "awaiting_confirmation"
    }

@router.post("/confirm")
async def confirm_action(request: ConfirmRequest):
    intent = normalize_intent(request.intent)
    await logs_store.append("INFO", "CONFIRM_RECEIVED", "Execution confirmed by user.", {"intent": intent})

    is_safe, error_msg = validate_intent(intent)
    if intent.get("action") != "check_balance" and not is_safe:
        await logs_store.append("ERROR", "SAFETY_BLOCK_CONFIRM", "Confirmation blocked by safety checks.", {"reason": error_msg, "intent": intent})
        raise HTTPException(status_code=400, detail=f"Safety check failed: {error_msg}")
    
    if intent["action"] == "check_balance":
        try:
            wallet_address = os.getenv("WALLET_ADDRESS", "0x0")
            balance = get_balance(wallet_address)
            await logs_store.append("SUCCESS", "BALANCE_SUCCESS", "Balance read succeeded.", {"balance": balance})
            return {"txHash": f"Simulated Tx. Your balance is {balance} GEN."}
        except Exception as e:
            await logs_store.append("ERROR", "BALANCE_FAILED", "Balance fetch failed.", {"error": str(e)})
            raise HTTPException(status_code=502, detail=f"Balance fetch failed: {str(e)}")
        
    if intent["action"] == "transfer":
        try:
            tx_hash = send_transfer(intent["recipient"], intent["amount"])
            await logs_store.append("SUCCESS", "TRANSFER_SUCCESS", "Transfer broadcast succeeded.", {"txHash": tx_hash})
            return {"txHash": tx_hash}
        except Exception as e:
            await logs_store.append("ERROR", "TRANSFER_FAILED", "Transfer failed.", {"error": str(e), "intent": intent})
            raise HTTPException(status_code=502, detail=f"Transfer failed: {str(e)}")
        
    await logs_store.append("ERROR", "UNSUPPORTED_ACTION", "Unsupported action during confirmation.", {"intent": intent})
    raise HTTPException(status_code=400, detail="Unsupported action for execution")
