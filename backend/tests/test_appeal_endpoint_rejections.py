import os

os.environ.setdefault("JWT_SECRET", "test-secret")
os.environ.setdefault("DATABASE_URL", "sqlite:///./test_chat_router.db")

from fastapi.testclient import TestClient

from backend.auth import create_access_token, normalize_address
from backend.database import SessionLocal
from backend.main import app
from backend.models import PreparedTransaction, User
from backend.routers import chat


WALLET = normalize_address("0x71E6E6D223A14D27A4CD4eDa6D240262d3B98F2d")
CONSENSUS_TX_ID = "0x" + "ab" * 32


def ensure_user(wallet_address: str) -> str:
    normalized = normalize_address(wallet_address)
    db = SessionLocal()
    try:
        if not db.query(User).filter(User.connected_wallet_address == normalized).first():
            db.add(User(connected_wallet_address=normalized))
            db.commit()
    finally:
        db.close()
    return normalized


def headers(wallet: str = WALLET) -> dict[str, str]:
    return {"Authorization": f"Bearer {create_access_token(wallet)}"}


def appeal_body() -> dict[str, str]:
    return {
        "address": WALLET,
        "consensus_tx_id": CONSENSUS_TX_ID,
        "bond_wei": "100",
        "network": "studionet",
    }


def test_appeal_tx_is_disabled_without_client_or_envelope(monkeypatch):
    ensure_user(WALLET)
    called = []
    monkeypatch.setattr(chat, "get_client", lambda network=None: called.append(network))
    db = SessionLocal()
    try:
        before_count = db.query(PreparedTransaction).filter(
            PreparedTransaction.action == "appeal_transaction"
        ).count()
    finally:
        db.close()

    with TestClient(app) as client:
        response = client.post("/chat/appeal-tx", json=appeal_body(), headers=headers())

    assert response.status_code == 503
    assert response.json()["detail"]["code"] == "appeal_submission_unproven"
    assert called == []
    db = SessionLocal()
    try:
        after_count = db.query(PreparedTransaction).filter(
            PreparedTransaction.action == "appeal_transaction"
        ).count()
        assert after_count == before_count
    finally:
        db.close()


def test_appeal_chat_returns_read_only_eligibility(monkeypatch):
    class ReadOnlyAppealClient:
        async def get_appeal_requirements(self, reference):
            assert reference == CONSENSUS_TX_ID
            return {
                "consensus_tx_id": CONSENSUS_TX_ID,
                "consensus_status": "ACCEPTED",
                "appeal_window_open": True,
                "appeal_window_status": "open",
                "minimum_appeal_bond_wei": 100,
                "appeal_round": 1,
                "appeal_status_code": 5,
                "appeal_window_source": "protocol_can_appeal",
                "minimum_appeal_bond_source": "protocol_calculate_min_appeal_bond",
            }

    monkeypatch.setattr(chat, "get_client", lambda network=None: ReadOnlyAppealClient())
    with TestClient(app) as client:
        response = client.post(
            "/chat",
            json={"message": f"appeal tx {CONSENSUS_TX_ID}", "network": "studionet"},
        )

    body = response.json()
    assert response.status_code == 200
    assert body["status"] == "unavailable"
    assert body["intent"]["appeal_window_open"] is True
    assert "read-only" in body["content"].lower()
    assert "unavailable" in body["content"].lower()


def test_appeal_confirmation_is_disabled_before_envelope_lookup():
    ensure_user(WALLET)
    with TestClient(app) as client:
        response = client.post(
            "/chat/confirm",
            json={
                "intent": {
                    "action": "appeal_transaction",
                    "consensus_tx_id": CONSENSUS_TX_ID,
                },
                "tx_hash": "0x" + "cd" * 32,
                "network": "studionet",
                "prepared_transaction_id": "missing",
                "intent_hash": "0x" + "ef" * 32,
            },
            headers=headers(),
        )

    assert response.status_code == 503
    assert response.json()["detail"]["code"] == "appeal_submission_unproven"
