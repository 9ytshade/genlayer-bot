from fastapi import APIRouter, Depends, HTTPException, Query
import os
from dotenv import load_dotenv

from ..auth import get_current_user
from ..database import get_db
from ..genlayer_client import get_balance as fetch_balance, send_transfer
from ..models import User
from ..network_config import normalize_network
from ..schemas import FundWalletRequest, TransactionResponse

load_dotenv(dotenv_path=os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env"))

router = APIRouter(prefix="/wallet", tags=["wallet"])

@router.get("/balance")
async def get_balance(address: str | None = Query(default=None), network: str | None = Query(default=None)):
    wallet_address = address or os.getenv("ADMIN_WALLET_ADDRESS", "0x0")
    try:
        selected_network = normalize_network(network)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    balance = await fetch_balance(wallet_address, network=selected_network)
    return {"address": wallet_address, "balance": balance, "token": "GEN"}

@router.post("/fund", response_model=TransactionResponse)
async def fund_platform_wallet(
    request: FundWalletRequest,
    current_user: User = Depends(get_current_user),
):
    """Fund user's platform wallet from admin wallet"""
    platform_wallet = current_user.platform_wallets[0] if current_user.platform_wallets else None
    if not platform_wallet:
        raise HTTPException(status_code=400, detail="User has no platform wallet")
    
    try:
        # Use admin wallet to fund the platform wallet
        admin_private_key = os.getenv("ADMIN_PRIVATE_KEY")
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
