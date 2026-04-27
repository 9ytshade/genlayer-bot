from fastapi import APIRouter, HTTPException, Depends, Header
from pydantic import BaseModel
from sqlalchemy.orm import Session
import os

try:
    from ..intent_parser import parse_intent
    from ..safety import validate_intent, normalize_intent
    from ..simulator import simulate_intent
    from ..genlayer_client import send_transfer, get_balance, deploy_contract
    from ..database import get_db
    from ..models import User, PlatformWallet
except ImportError:
    # Fallback when running from inside backend directory.
    from intent_parser import parse_intent
    from safety import validate_intent, normalize_intent
    from simulator import simulate_intent
    from genlayer_client import send_transfer, get_balance, deploy_contract
    from database import get_db
    from models import User, PlatformWallet

try:
    from ..logs_store import logs_store
except ImportError:
    from logs_store import logs_store

from web3 import Web3

router = APIRouter(prefix="/chat", tags=["chat"])

class ChatRequest(BaseModel):
    message: str

class ConfirmRequest(BaseModel):
    intent: dict


def get_current_user(authorization: str = Header(None), db: Session = Depends(get_db)):
    """Extract user from token (wallet address)"""
    if not authorization:
        raise HTTPException(status_code=401, detail="Authorization header required")
    
    try:
        # Token format: "Bearer 0x..."
        token = authorization.split(" ")[1]
        if not Web3.is_address(token):
            raise HTTPException(status_code=401, detail="Invalid wallet address")
        
        user = db.query(User).filter(User.connected_wallet_address == token).first()
        if not user:
            raise HTTPException(status_code=404, detail="User not found. Please register first.")
        return user
    except IndexError:
        raise HTTPException(status_code=401, detail="Invalid token format. Use: Bearer 0x...")


@router.post("")
async def handle_chat(
    request: ChatRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    await logs_store.append("INFO", "CHAT_RECEIVED", "User message received.", {"message": request.message, "user": current_user.id})
    
    # Get user's platform wallet
    platform_wallet = db.query(PlatformWallet).filter(
        PlatformWallet.user_id == current_user.id
    ).first()
    
    if not platform_wallet:
        raise HTTPException(status_code=404, detail="Platform wallet not found. Please create one first.")
    
    intent = normalize_intent(parse_intent(request.message))
    intent["platform_wallet_address"] = platform_wallet.address
    intent["user_id"] = current_user.id
    
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
        
    if intent["action"] == "deploy_contract":
        if not intent.get("code"):
            return {
                "content": "Please provide the Python code for your GenLayer Intelligent Contract.",
                "intent": intent,
                "status": "awaiting_input"
            }
        await logs_store.append("INFO", "AWAIT_CONFIRMATION", "Awaiting confirmation for contract deployment.")
        return {
            "content": f"I'm ready to deploy your contract '{intent.get('contract_name', 'MyContract')}'. Do you want me to proceed?",
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
async def confirm_action(
    request: ConfirmRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    intent = normalize_intent(request.intent)
    await logs_store.append("INFO", "CONFIRM_RECEIVED", "Execution confirmed by user.", {"intent": intent, "user": current_user.id})

    # Get user's platform wallet
    platform_wallet = db.query(PlatformWallet).filter(
        PlatformWallet.user_id == current_user.id
    ).first()
    
    if not platform_wallet:
        raise HTTPException(status_code=404, detail="Platform wallet not found")

    is_safe, error_msg = validate_intent(intent)
    if intent.get("action") != "check_balance" and not is_safe:
        await logs_store.append("ERROR", "SAFETY_BLOCK_CONFIRM", "Confirmation blocked by safety checks.", {"reason": error_msg, "intent": intent})
        raise HTTPException(status_code=400, detail=f"Safety check failed: {error_msg}")
    
    if intent["action"] == "check_balance":
        try:
            balance = get_balance(platform_wallet.address)
            await logs_store.append("SUCCESS", "BALANCE_SUCCESS", "Balance read succeeded.", {"balance": balance, "user": current_user.id})
            return {"txHash": f"Your platform wallet balance is {balance} GEN."}
        except Exception as e:
            await logs_store.append("ERROR", "BALANCE_FAILED", "Balance fetch failed.", {"error": str(e)})
            raise HTTPException(status_code=502, detail=f"Balance fetch failed: {str(e)}")
        
    if intent["action"] == "transfer":
        try:
            # Use platform wallet private key for transfer
            private_key = platform_wallet.get_private_key()
            tx_hash = send_transfer(intent["recipient"], intent["amount"], private_key=private_key)
            await logs_store.append("SUCCESS", "TRANSFER_SUCCESS", "Transfer broadcast succeeded.", {"txHash": tx_hash, "user": current_user.id})
            return {"txHash": tx_hash}
        except Exception as e:
            await logs_store.append("ERROR", "TRANSFER_FAILED", "Transfer failed.", {"error": str(e), "intent": intent})
            raise HTTPException(status_code=502, detail=f"Transfer failed: {str(e)}")
            
    if intent["action"] == "deploy_contract":
        try:
            private_key = platform_wallet.get_private_key()
            await logs_store.append("INFO", "DEPLOY_START", "Starting contract deployment process...", {"contract_name": intent.get("contract_name", "MyContract")})
            
            await logs_store.append("INFO", "DEPLOY_COMPILING", "Compiling intelligent contract code...")
            # Simulation/Validation could go here
            
            await logs_store.append("INFO", "DEPLOY_ESTIMATING", "Estimating gas for deployment on GenLayer Studionet...")
            
            tx_hash = deploy_contract(intent["code"], private_key=private_key)
            
            await logs_store.append("SUCCESS", "DEPLOY_SUCCESS", "Contract successfully deployed!", {"txHash": tx_hash, "user": current_user.id})
            return {"txHash": tx_hash, "content": "Intelligent Contract successfully deployed on GenLayer Studionet."}
        except Exception as e:
            await logs_store.append("ERROR", "DEPLOY_FAILED", "Deployment process failed.", {"error": str(e), "intent": intent})
            raise HTTPException(status_code=502, detail=f"Deployment failed: {str(e)}")
        
    await logs_store.append("ERROR", "UNSUPPORTED_ACTION", "Unsupported action during confirmation.", {"intent": intent})
    raise HTTPException(status_code=400, detail="Unsupported action for execution")
