from datetime import datetime, timedelta, timezone
import os
import secrets
from typing import Any

from dotenv import load_dotenv
from eth_account import Account
from eth_account.messages import encode_defunct
from fastapi import APIRouter, Depends, Header, HTTPException, Query
from jose import JWTError, jwt
from pydantic import BaseModel
from sqlalchemy.orm import Session
from web3 import Web3

from .database import get_db
from .models import User

load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), ".env"))

ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_HOURS = 24
NONCE_EXPIRE_MINUTES = 10
NONCES: dict[str, tuple[str, datetime]] = {}

router = APIRouter(prefix="/auth", tags=["auth"])


class NonceResponse(BaseModel):
    nonce: str


class VerifyRequest(BaseModel):
    message: str
    signature: str
    address: str


class VerifyResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    wallet_address: str


def get_jwt_secret() -> str:
    secret = os.getenv("JWT_SECRET")
    if not secret:
        raise HTTPException(status_code=500, detail="JWT_SECRET is not configured")
    return secret


def normalize_address(address: str) -> str:
    if not Web3.is_address(address):
        raise HTTPException(status_code=400, detail="Invalid wallet address")
    return Web3.to_checksum_address(address)


def create_access_token(wallet_address: str) -> str:
    expires = datetime.now(timezone.utc) + timedelta(hours=ACCESS_TOKEN_EXPIRE_HOURS)
    payload = {"sub": normalize_address(wallet_address), "exp": expires}
    return jwt.encode(payload, get_jwt_secret(), algorithm=ALGORITHM)


def decode_access_token(token: str) -> dict[str, Any]:
    try:
        return jwt.decode(token, get_jwt_secret(), algorithms=[ALGORITHM])
    except JWTError as exc:
        raise HTTPException(status_code=401, detail="Invalid or expired token") from exc


def get_bearer_token(authorization: str | None = Header(None)) -> str:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid authorization header")
    return authorization.split(" ", 1)[1].strip()


def get_wallet_address_from_authorization(authorization: str | None) -> str | None:
    if not authorization or not authorization.startswith("Bearer "):
        return None
    token = authorization.split(" ", 1)[1].strip()
    try:
        payload = decode_access_token(token)
    except HTTPException:
        return None
    subject = payload.get("sub")
    return normalize_address(subject) if isinstance(subject, str) else None


def get_current_user(token: str = Depends(get_bearer_token), db: Session = Depends(get_db)) -> User:
    payload = decode_access_token(token)
    wallet_address = payload.get("sub")
    if not isinstance(wallet_address, str):
        raise HTTPException(status_code=401, detail="Token is missing wallet subject")

    user = db.query(User).filter(User.connected_wallet_address == normalize_address(wallet_address)).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user


def extract_nonce(message: str) -> str | None:
    for line in message.splitlines():
        if line.startswith("Nonce:"):
            return line.split(":", 1)[1].strip()
    return None


def verify_siwe_signature(message: str, signature: str, expected_address: str, expected_nonce: str) -> None:
    siwe_message = None
    try:
        from siwe import SiweMessage  # type: ignore

        if hasattr(SiweMessage, "from_message"):
            siwe_message = SiweMessage.from_message(message)
            if getattr(siwe_message, "nonce", None) != expected_nonce:
                raise HTTPException(status_code=401, detail="Invalid SIWE nonce")
    except ImportError:
        pass

    if extract_nonce(message) != expected_nonce:
        raise HTTPException(status_code=401, detail="Invalid SIWE nonce")

    recovered = Account.recover_message(encode_defunct(text=message), signature=signature)
    if Web3.to_checksum_address(recovered) != normalize_address(expected_address):
        raise HTTPException(status_code=401, detail="Signature does not match wallet address")

    if siwe_message is not None:
        message_address = getattr(siwe_message, "address", None)
        if message_address and Web3.to_checksum_address(message_address) != normalize_address(expected_address):
            raise HTTPException(status_code=401, detail="SIWE address does not match wallet address")


@router.get("/nonce", response_model=NonceResponse)
def get_nonce(address: str = Query(...)) -> NonceResponse:
    wallet_address = normalize_address(address)
    nonce = secrets.token_urlsafe(16)
    NONCES[wallet_address.lower()] = (
        nonce,
        datetime.now(timezone.utc) + timedelta(minutes=NONCE_EXPIRE_MINUTES),
    )
    return NonceResponse(nonce=nonce)


@router.post("/verify", response_model=VerifyResponse)
def verify_signature(request: VerifyRequest, db: Session = Depends(get_db)) -> VerifyResponse:
    wallet_address = normalize_address(request.address)
    nonce_entry = NONCES.get(wallet_address.lower())
    if not nonce_entry:
        raise HTTPException(status_code=401, detail="No SIWE nonce found for this wallet")

    nonce, expires_at = nonce_entry
    if datetime.now(timezone.utc) > expires_at:
        NONCES.pop(wallet_address.lower(), None)
        raise HTTPException(status_code=401, detail="SIWE nonce has expired")

    verify_siwe_signature(request.message, request.signature, wallet_address, nonce)
    NONCES.pop(wallet_address.lower(), None)

    user = db.query(User).filter(User.connected_wallet_address == wallet_address).first()
    if not user:
        user = User(connected_wallet_address=wallet_address)
        db.add(user)
        db.commit()
        db.refresh(user)

    return VerifyResponse(access_token=create_access_token(wallet_address), wallet_address=wallet_address)
