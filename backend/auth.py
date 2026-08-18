from datetime import datetime, timedelta, timezone
import hashlib
import os
from typing import Any
from urllib.parse import urlparse

from dotenv import load_dotenv
from fastapi import APIRouter, Depends, Header, HTTPException, Query
from jose import JWTError, jwt
from pydantic import BaseModel
from siwe import SiweMessage, VerificationError, generate_nonce
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from web3 import Web3

from .database import get_db
from .models import SiweNonce, User

load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), ".env"))

ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_HOURS = 24
NONCE_EXPIRE_MINUTES = 10
SIWE_ISSUED_AT_SKEW_SECONDS = 120

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


def _hash_nonce(nonce: str) -> str:
    return hashlib.sha256(nonce.encode("ascii")).hexdigest()


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _nonce_from_message(message: str) -> str:
    try:
        nonce = str(SiweMessage.from_message(message).nonce)
    except (ValueError, TypeError) as exc:
        raise HTTPException(status_code=401, detail="Invalid SIWE message or signature") from exc
    if not nonce:
        raise HTTPException(status_code=401, detail="Invalid SIWE message or signature")
    return nonce


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


def get_allowed_siwe_origins() -> dict[str, str]:
    configured = os.getenv("SIWE_ORIGINS") or os.getenv(
        "ALLOWED_ORIGINS",
        "http://localhost:3000",
    )
    origins: dict[str, str] = {}
    for raw_origin in configured.split(","):
        candidate = raw_origin.strip()
        if not candidate:
            continue
        if "://" not in candidate:
            candidate = f"http://{candidate}"
        parsed = urlparse(candidate)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            continue
        origins[parsed.netloc.lower()] = f"{parsed.scheme}://{parsed.netloc}".lower()
    if not origins:
        raise HTTPException(status_code=500, detail="No valid SIWE origins are configured")
    return origins


def get_allowed_siwe_chain_ids() -> set[int] | None:
    configured = os.getenv("SIWE_CHAIN_IDS")
    if not configured:
        return None
    try:
        return {int(value.strip()) for value in configured.split(",") if value.strip()}
    except ValueError as exc:
        raise HTTPException(status_code=500, detail="SIWE_CHAIN_IDS contains an invalid chain id") from exc


def verify_siwe_signature(
    message: str,
    signature: str,
    expected_address: str,
    expected_nonce: str,
    nonce_expires_at: datetime,
) -> None:
    try:
        siwe_message = SiweMessage.from_message(message)
        allowed_origins = get_allowed_siwe_origins()
        domain = str(siwe_message.domain).lower()
        expected_origin = allowed_origins.get(domain)
        if not expected_origin:
            raise HTTPException(status_code=401, detail="SIWE domain is not allowed")

        parsed_uri = urlparse(str(siwe_message.uri))
        message_origin = f"{parsed_uri.scheme}://{parsed_uri.netloc}".lower()
        if message_origin != expected_origin:
            raise HTTPException(status_code=401, detail="SIWE URI does not match the allowed origin")
        if str(siwe_message.uri).rstrip("/").lower() != expected_origin.rstrip("/"):
            raise HTTPException(status_code=401, detail="SIWE URI does not match the allowed resource")
        allowed_chain_ids = get_allowed_siwe_chain_ids()
        if allowed_chain_ids is not None and int(siwe_message.chain_id) not in allowed_chain_ids:
            raise HTTPException(status_code=401, detail="SIWE chain id is not supported")
        if Web3.to_checksum_address(str(siwe_message.address)) != normalize_address(expected_address):
            raise HTTPException(status_code=401, detail="SIWE address does not match wallet address")

        issued_at = datetime.fromisoformat(str(siwe_message.issued_at).replace("Z", "+00:00"))
        if issued_at.tzinfo is None:
            issued_at = issued_at.replace(tzinfo=timezone.utc)
        now = datetime.now(timezone.utc)
        earliest_issue = nonce_expires_at - timedelta(
            minutes=NONCE_EXPIRE_MINUTES,
            seconds=SIWE_ISSUED_AT_SKEW_SECONDS,
        )
        latest_issue = now + timedelta(seconds=SIWE_ISSUED_AT_SKEW_SECONDS)
        if issued_at < earliest_issue or issued_at > latest_issue:
            raise HTTPException(status_code=401, detail="SIWE issued-at time is outside the allowed window")

        siwe_message.verify(
            signature,
            domain=str(siwe_message.domain),
            nonce=expected_nonce,
            timestamp=now,
        )
    except HTTPException:
        raise
    except (VerificationError, ValueError, TypeError) as exc:
        raise HTTPException(status_code=401, detail="Invalid SIWE message or signature") from exc


@router.get("/nonce", response_model=NonceResponse)
def get_nonce(address: str = Query(...), db: Session = Depends(get_db)) -> NonceResponse:
    wallet_address = normalize_address(address)
    nonce = generate_nonce()
    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(minutes=NONCE_EXPIRE_MINUTES)
    nonce_record = db.query(SiweNonce).filter(SiweNonce.wallet_address == wallet_address).first()
    if nonce_record:
        nonce_record.nonce_hash = _hash_nonce(nonce)
        nonce_record.created_at = now
        nonce_record.expires_at = expires_at
    else:
        db.add(
            SiweNonce(
                wallet_address=wallet_address,
                nonce_hash=_hash_nonce(nonce),
                created_at=now,
                expires_at=expires_at,
            )
        )
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        nonce_record = db.query(SiweNonce).filter(SiweNonce.wallet_address == wallet_address).first()
        if not nonce_record:
            raise HTTPException(status_code=503, detail="Unable to issue SIWE nonce")
        nonce_record.nonce_hash = _hash_nonce(nonce)
        nonce_record.created_at = now
        nonce_record.expires_at = expires_at
        db.commit()
    return NonceResponse(nonce=nonce)


@router.post("/verify", response_model=VerifyResponse)
def verify_signature(request: VerifyRequest, db: Session = Depends(get_db)) -> VerifyResponse:
    wallet_address = normalize_address(request.address)
    nonce = _nonce_from_message(request.message)
    nonce_hash = _hash_nonce(nonce)
    nonce_record = (
        db.query(SiweNonce)
        .filter(
            SiweNonce.wallet_address == wallet_address,
            SiweNonce.nonce_hash == nonce_hash,
        )
        .with_for_update()
        .first()
    )
    if not nonce_record:
        raise HTTPException(status_code=401, detail="No SIWE nonce found for this wallet")

    expires_at = _as_utc(nonce_record.expires_at)
    deleted = (
        db.query(SiweNonce)
        .filter(
            SiweNonce.id == nonce_record.id,
            SiweNonce.nonce_hash == nonce_hash,
        )
        .delete(synchronize_session=False)
    )
    if deleted != 1:
        db.rollback()
        raise HTTPException(status_code=401, detail="No SIWE nonce found for this wallet")
    db.commit()

    if datetime.now(timezone.utc) > expires_at:
        raise HTTPException(status_code=401, detail="SIWE nonce has expired")

    verify_siwe_signature(
        request.message,
        request.signature,
        wallet_address,
        nonce,
        expires_at,
    )

    user = db.query(User).filter(User.connected_wallet_address == wallet_address).first()
    if not user:
        user = User(connected_wallet_address=wallet_address)
        db.add(user)
        db.commit()
        db.refresh(user)

    return VerifyResponse(access_token=create_access_token(wallet_address), wallet_address=wallet_address)
