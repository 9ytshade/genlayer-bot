import os

os.environ.setdefault("JWT_SECRET", "test-secret")
os.environ.setdefault("DATABASE_URL", "sqlite:///./test_chat_router.db")

from fastapi.testclient import TestClient

from backend.auth import create_access_token, normalize_address
from backend.database import SessionLocal
from backend.main import app
from backend.models import User
from backend.routers import chat
from backend.safety import normalize_intent, validate_intent
from backend.services.workflow_service import validate_workflow_config


def ensure_user(wallet_address: str) -> str:
    normalized = normalize_address(wallet_address)
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.connected_wallet_address == normalized).first()
        if not user:
            user = User(connected_wallet_address=normalized)
            db.add(user)
            db.commit()
    finally:
        db.close()
    return normalized


def test_removed_wallet_management_routes_are_gone():
    wallet_address = ensure_user("0xfB73b3b3C379A8ec184959F114d19481B891d54E")
    headers = {"Authorization": f"Bearer {create_access_token(wallet_address)}"}

    with TestClient(app) as client:
        me_response = client.get("/users/me", headers=headers)
        wallet_response = client.get("/users/me/wallet", headers=headers)
        create_wallet_response = client.post("/users/me/wallet/create", headers=headers)
        fund_response = client.post("/wallet/fund", json={"amount": 1}, headers=headers)

    assert me_response.status_code == 200
    assert wallet_response.status_code == 404
    assert create_wallet_response.status_code == 404
    assert fund_response.status_code == 404


def test_contract_call_intent_is_user_signed_only():
    intent = normalize_intent(
        {
            "action": "contract_call",
            "contract_address": "0x1111111111111111111111111111111111111111",
            "method": "pause",
            "args": [],
            "workflow_type": "subscription",
        }
    )

    valid, error = validate_intent(intent)

    assert intent["action"] == "contract_call"
    assert valid is True
    assert error == ""


def test_workflow_config_validation_requires_real_addresses():
    config = validate_workflow_config(
        {
            "workflowType": "subscription",
            "recipient": "0x2222222222222222222222222222222222222222",
            "amount": 50,
            "token": "GEN",
            "frequency": "weekly",
        }
    )

    assert config["workflowType"] == "subscription"
    assert config["recipient"] == "0x2222222222222222222222222222222222222222"


def test_contract_call_tx_endpoint_builds_wallet_transaction(monkeypatch):
    class FakeClient:
        rpc_url = "https://rpc.test"

        async def build_contract_call_transaction(self, **kwargs):
            assert kwargs["sender_address"] == "0xfB73b3b3C379A8ec184959F114d19481B891d54E"
            assert kwargs["contract_address"] == "0x1111111111111111111111111111111111111111"
            assert kwargs["method"] == "pause"
            return {
                "chain_id": 61999,
                "to": "0x2222222222222222222222222222222222222222",
                "data": "0x1234",
                "value": 0,
                "nonce": 7,
                "gas_limit": 1500000,
                "gasPrice": 1,
            }

    monkeypatch.setattr(chat, "get_client", lambda network=None: FakeClient())

    with TestClient(app) as client:
        response = client.post(
            "/chat/contract-call-tx",
            json={
                "address": "0xfB73b3b3C379A8ec184959F114d19481B891d54E",
                "contract_address": "0x1111111111111111111111111111111111111111",
                "method": "pause",
                "args": [],
                "workflow_type": "subscription",
                "network": "studionet",
            },
        )

    assert response.status_code == 200
    body = response.json()
    assert body["to"] == "0x2222222222222222222222222222222222222222"
    assert body["nonce"] == 7


def test_contract_call_confirmation_requires_wallet_tx_hash(monkeypatch):
    class FakeClient:
        async def _wait_for_receipt_or_raise(self, tx_hash):
            assert tx_hash == "0x" + "a" * 64

        async def get_consensus_transaction_id(self, tx_hash):
            return "0x" + "b" * 64

    monkeypatch.setattr(chat, "get_client", lambda network=None: FakeClient())

    with TestClient(app) as client:
        response = client.post(
            "/chat/confirm",
            json={
                "intent": {
                    "action": "contract_call",
                    "contract_address": "0x1111111111111111111111111111111111111111",
                    "method": "pause",
                    "args": [],
                    "workflow_type": "subscription",
                },
                "tx_hash": "0x" + "a" * 64,
                "network": "studionet",
            },
        )

    assert response.status_code == 200
    assert response.json()["consensusTxId"] == "0x" + "b" * 64
