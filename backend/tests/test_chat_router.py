import os

os.environ.setdefault("ENCRYPTION_KEY", "SC5Vv1b3Ug2fqGvnnY8ctC-fNvUj_JoyK5zB1w8OX3E=")
os.environ.setdefault("JWT_SECRET", "test-secret")
os.environ.setdefault("DATABASE_URL", "sqlite:///./test_chat_router.db")

from fastapi.testclient import TestClient

from backend.main import app
from backend.routers import chat


def test_chat_router_returns_unknown_for_unparsed_message(monkeypatch):
    monkeypatch.setattr(chat, "parse_intent", lambda _: {"action": "unknown"})

    with TestClient(app) as client:
        response = client.post("/chat", json={"message": "hello", "network": "studionet"})

    assert response.status_code == 200
    assert response.json()["intent"]["action"] == "unknown"
