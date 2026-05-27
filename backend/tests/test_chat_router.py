import os

os.environ.setdefault("ENCRYPTION_KEY", "SC5Vv1b3Ug2fqGvnnY8ctC-fNvUj_JoyK5zB1w8OX3E=")
os.environ.setdefault("JWT_SECRET", "test-secret")
os.environ.setdefault("DATABASE_URL", "sqlite:///./test_chat_router.db")

from fastapi.testclient import TestClient

from backend.auth import create_access_token, normalize_address
from backend.database import SessionLocal
from backend.main import app
from backend.models import User
from backend.routers import chat


def test_chat_router_returns_unknown_for_unparsed_message(monkeypatch):
    monkeypatch.setattr(chat, "parse_intent", lambda _: {"action": "unknown"})

    with TestClient(app) as client:
        response = client.post("/chat", json={"message": "hello", "network": "studionet"})

    assert response.status_code == 200
    assert response.json()["intent"]["action"] == "unknown"


def test_chat_history_round_trip():
    wallet_address = normalize_address("0xfB73b3b3C379A8ec184959F114d19481B891d54E")
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.connected_wallet_address == wallet_address).first()
        if not user:
            user = User(connected_wallet_address=wallet_address)
            db.add(user)
            db.commit()
    finally:
        db.close()

    token = create_access_token(wallet_address)
    headers = {"Authorization": f"Bearer {token}"}
    payload = {
        "chats": [
            {
                "id": "chat-test",
                "title": "Balance check",
                "updatedAt": 1,
                "messages": [{"id": "msg-1", "role": "user", "content": "check balance"}],
            }
        ],
        "currentChatId": "chat-test",
    }

    with TestClient(app) as client:
        save_response = client.put("/chat/history", json=payload, headers=headers)
        load_response = client.get("/chat/history", headers=headers)

    assert save_response.status_code == 200
    assert load_response.status_code == 200
    assert load_response.json() == payload
