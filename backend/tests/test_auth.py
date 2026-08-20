import os
import asyncio
from datetime import datetime, timedelta, timezone

os.environ.setdefault("JWT_SECRET", "test-secret")
os.environ.setdefault("DATABASE_URL", "sqlite:///./test_chat_router.db")

from eth_account import Account
from eth_account.messages import encode_defunct
from fastapi.testclient import TestClient
import pytest
from siwe import SiweMessage
from starlette.websockets import WebSocketDisconnect

from backend.auth import create_access_token
from backend.database import SessionLocal
from backend.main import app
from backend.logs_store import logs_store
from backend.models import SiweNonce, User


def siwe_message(address: str, nonce: str, *, domain: str = "localhost:3000", chain_id: int = 1, issued_at=None):
    issued_at = issued_at or datetime.now(timezone.utc)
    return chr(10).join(
        [
            f"{domain} wants you to sign in with your Ethereum account:",
            address,
            "",
            "Sign in to GenLayer Bot.",
            "",
            f"URI: http://{domain}",
            "Version: 1",
            f"Chain ID: {chain_id}",
            f"Nonce: {nonce}",
            f"Issued At: {issued_at.isoformat().replace('+00:00', 'Z')}",
        ]
    )


def sign_message(account, message: str) -> str:
    signature = Account.sign_message(
        encode_defunct(text=message),
        private_key=account.key,
    ).signature.hex()
    return signature if signature.startswith("0x") else f"0x{signature}"


def test_siwe_verification_binds_domain_nonce_signature_and_prevents_replay(monkeypatch):
    monkeypatch.setenv("SIWE_ORIGINS", "http://localhost:3000")
    monkeypatch.delenv("SIWE_CHAIN_IDS", raising=False)
    account = Account.create()

    with TestClient(app) as client:
        nonce = client.get("/auth/nonce", params={"address": account.address}).json()["nonce"]
        db = SessionLocal()
        try:
            stored_nonce = db.query(SiweNonce).filter(SiweNonce.wallet_address == account.address).one()
            assert stored_nonce.nonce_hash != nonce
        finally:
            db.close()
        message = siwe_message(account.address, nonce)
        signature = sign_message(account, message)
        parsed_message = SiweMessage.from_message(message)
        parsed_message.verify(signature, domain="localhost:3000", nonce=nonce)
        payload = {
            "address": account.address,
            "message": message,
            "signature": signature,
        }
        response = client.post("/auth/verify", json=payload)
        replay = client.post("/auth/verify", json=payload)

    assert response.status_code == 200, response.json()
    assert response.json()["wallet_address"] == account.address
    assert response.json()["access_token"]
    assert replay.status_code == 401
    db = SessionLocal()
    try:
        assert db.query(SiweNonce).filter(SiweNonce.wallet_address == account.address).first() is None
    finally:
        db.close()


def test_siwe_rejects_unapproved_domain_and_stale_issued_at(monkeypatch):
    monkeypatch.setenv("SIWE_ORIGINS", "http://localhost:3000")
    account = Account.create()

    with TestClient(app) as client:
        domain_nonce = client.get("/auth/nonce", params={"address": account.address}).json()["nonce"]
        bad_domain_message = siwe_message(account.address, domain_nonce, domain="evil.example")
        bad_domain = client.post(
            "/auth/verify",
            json={
                "address": account.address,
                "message": bad_domain_message,
                "signature": sign_message(account, bad_domain_message),
            },
        )

        stale_nonce = client.get("/auth/nonce", params={"address": account.address}).json()["nonce"]
        stale_message = siwe_message(
            account.address,
            stale_nonce,
            issued_at=datetime.now(timezone.utc) - timedelta(hours=1),
        )
        stale = client.post(
            "/auth/verify",
            json={
                "address": account.address,
                "message": stale_message,
                "signature": sign_message(account, stale_message),
            },
        )

    assert bad_domain.status_code == 401
    assert stale.status_code == 401


def test_siwe_chain_allowlist_is_enforced_when_configured(monkeypatch):
    monkeypatch.setenv("SIWE_ORIGINS", "http://localhost:3000")
    monkeypatch.setenv("SIWE_CHAIN_IDS", "61999")
    account = Account.create()

    with TestClient(app) as client:
        nonce = client.get("/auth/nonce", params={"address": account.address}).json()["nonce"]
        message = siwe_message(account.address, nonce, chain_id=1)
        response = client.post(
            "/auth/verify",
            json={
                "address": account.address,
                "message": message,
                "signature": sign_message(account, message),
            },
        )

    assert response.status_code == 401


def test_activity_logs_require_authenticated_http_and_websocket_access():
    account = Account.create()
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.connected_wallet_address == account.address).first()
        if not user:
            db.add(User(connected_wallet_address=account.address))
            db.commit()
    finally:
        db.close()
    token = create_access_token(account.address)

    with TestClient(app) as client:
        unauthorized_http = client.get("/logs")
        authorized_http = client.get(
            "/logs",
            headers={"Authorization": f"Bearer {token}"},
        )
        with pytest.raises(WebSocketDisconnect):
            with client.websocket_connect("/logs/stream"):
                pass
        with client.websocket_connect(
            "/logs/stream",
            subprotocols=["genlayer-auth", token],
        ) as websocket:
            backlog = websocket.receive_json()

    assert unauthorized_http.status_code == 401
    assert authorized_http.status_code == 200
    assert backlog["type"] == "backlog"


def test_activity_log_http_feed_is_wallet_scoped():
    accounts = [Account.create(), Account.create()]
    db = SessionLocal()
    try:
        for account in accounts:
            if not db.query(User).filter(User.connected_wallet_address == account.address).first():
                db.add(User(connected_wallet_address=account.address))
        db.commit()
    finally:
        db.close()

    asyncio.run(
        logs_store.append(
            "INFO",
            "WALLET_A_ONLY",
            "Wallet A event.",
            wallet_address=accounts[0].address,
        )
    )
    asyncio.run(
        logs_store.append(
            "INFO",
            "WALLET_B_ONLY",
            "Wallet B event.",
            wallet_address=accounts[1].address,
        )
    )

    with TestClient(app) as client:
        wallet_a_response = client.get(
            "/logs",
            headers={"Authorization": f"Bearer {create_access_token(accounts[0].address)}"},
        )
        wallet_b_response = client.get(
            "/logs",
            headers={"Authorization": f"Bearer {create_access_token(accounts[1].address)}"},
        )

    wallet_a_events = {item["event"] for item in wallet_a_response.json()["items"]}
    wallet_b_events = {item["event"] for item in wallet_b_response.json()["items"]}
    assert "WALLET_A_ONLY" in wallet_a_events
    assert "WALLET_B_ONLY" not in wallet_a_events
    assert "WALLET_B_ONLY" in wallet_b_events
    assert "WALLET_A_ONLY" not in wallet_b_events
