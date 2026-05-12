from fastapi import APIRouter, Query, Depends, HTTPException, Header
from sqlalchemy.orm import Session
import os
from dotenv import load_dotenv

try:
    from ..genlayer_client import get_balance as fetch_balance, send_transfer
    from ..network_config import normalize_network
    from ..database import get_db
    from ..models import User
    from ..schemas import FundWalletRequest, TransactionResponse
except ImportError:
    # Fallback when running from inside backend directory.
    from genlayer_client import get_balance as fetch_balance, send_transfer
    from network_config import normalize_network
    from database import get_db
    from models import User
    from schemas import FundWalletRequest, TransactionResponse

load_dotenv(dotenv_path=os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env"))

def get_current_user(authorization: str = Header(None), db: Session = Depends(get_db)):
    """Extract user from Authorization header"""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid authorization header")
    
    wallet_address = authorization.replace("Bearer ", "").strip()
    user = db.query(User).filter(User.connected_wallet_address == wallet_address).first()
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    return user

router = APIRouter(prefix="/wallet", tags=["wallet"])

@router.get("/balance")
async def get_balance(address: str | None = Query(default=None), network: str | None = Query(default=None)):
    wallet_address = address or os.getenv("WALLET_ADDRESS", "0x0")
    try:
        selected_network = normalize_network(network)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    balance = await fetch_balance(wallet_address, network=selected_network)
    return {"address": wallet_address, "balance": balance, "token": "GEN"}

@router.post("/fund", response_model=TransactionResponse)
async def fund_platform_wallet(
    request: FundWalletRequest,
    authorization: str = Header(None),
    db: Session = Depends(get_db)
):
    """Fund user's platform wallet from admin wallet"""
    # Validate authorization
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid authorization header")
    
    wallet_address = authorization.replace("Bearer ", "").strip()
    user = db.query(User).filter(User.connected_wallet_address == wallet_address).first()
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    
    platform_wallet = user.platform_wallets[0] if user.platform_wallets else None
    if not platform_wallet:
        raise HTTPException(status_code=400, detail="User has no platform wallet")
    
    try:
        # Use admin wallet to fund the platform wallet
        admin_private_key = os.getenv("WALLET_PRIVATE_KEY")
        if not admin_private_key:
            raise HTTPException(status_code=500, detail="Admin wallet not configured")
        
        # Send transfer from admin wallet to platform wallet
        tx_hash = await send_transfer(
            to_address=platform_wallet.address,
            amount=request.amount,
            private_key=admin_private_key
        )
        
        return TransactionResponse(
            tx_hash=tx_hash,
            status="success"
        )
    except Exception as e:
        return TransactionResponse(
            tx_hash="",
            status="failed",
            error=str(e)
        )
