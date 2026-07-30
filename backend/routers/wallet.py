from fastapi import APIRouter, HTTPException, Query
from web3 import Web3

from ..genlayer_client import get_balance as fetch_balance
from ..network_config import normalize_network

router = APIRouter(prefix="/wallet", tags=["wallet"])


@router.get("/balance")
async def get_balance(address: str = Query(...), network: str | None = Query(default=None)):
    if not Web3.is_address(address):
        raise HTTPException(status_code=400, detail="Invalid wallet address")
    wallet_address = Web3.to_checksum_address(address)
    try:
        selected_network = normalize_network(network)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    balance = await fetch_balance(wallet_address, network=selected_network)
    return {"address": wallet_address, "balance": balance, "token": "GEN"}
