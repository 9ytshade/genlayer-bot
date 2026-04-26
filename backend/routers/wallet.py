from fastapi import APIRouter, Query
import os
from dotenv import load_dotenv

try:
    from ..genlayer_client import get_balance as fetch_balance
except ImportError:
    # Fallback when running from inside backend directory.
    from genlayer_client import get_balance as fetch_balance

load_dotenv(dotenv_path=os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env"))

router = APIRouter(prefix="/wallet", tags=["wallet"])

@router.get("/balance")
def get_balance(address: str | None = Query(default=None)):
    wallet_address = address or os.getenv("WALLET_ADDRESS", "0x0")
    balance = fetch_balance(wallet_address)
    return {"address": wallet_address, "balance": balance, "token": "GEN"}
