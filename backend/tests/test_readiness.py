import os

os.environ.setdefault("JWT_SECRET", "test-secret-with-at-least-32-characters")
os.environ.setdefault("DATABASE_URL", "sqlite:///./test_chat_router.db")
os.environ.setdefault("ALLOWED_ORIGINS", "http://localhost:3000")
os.environ.setdefault("SIWE_ORIGINS", "http://localhost:3000")
os.environ.setdefault("GENLAYER_RPC_URL_STUDIONET", "https://studio.genlayer.com/api")
os.environ.setdefault("GENLAYER_RPC_URL_BRADBURY", "https://rpc-bradbury.genlayer.com")

from fastapi.testclient import TestClient
import pytest

from backend.main import app
from backend.readiness import (
    assert_production_configuration,
    configuration_checks,
    rpc_connectivity_checks,
)


def test_health_is_liveness_only():
    with TestClient(app) as client:
        response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "healthy", "service": "genlayer-bot-api"}


def test_ready_reports_database_and_configuration(monkeypatch):
    monkeypatch.setenv("APP_ENV", "development")
    monkeypatch.setenv("JWT_SECRET", "a-secure-test-secret-that-is-long-enough")
    monkeypatch.setenv("DATABASE_URL", "sqlite:///./test_chat_router.db")
    monkeypatch.setenv("ALLOWED_ORIGINS", "http://localhost:3000")
    monkeypatch.setenv("SIWE_ORIGINS", "http://localhost:3000")
    monkeypatch.setenv("GENLAYER_RPC_URL_STUDIONET", "https://studio.genlayer.com/api")
    monkeypatch.setenv("GENLAYER_RPC_URL_BRADBURY", "https://rpc-bradbury.genlayer.com")

    with TestClient(app) as client:
        response = client.get("/ready")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ready"
    assert any(check["name"] == "database_connection" and check["status"] == "pass" for check in payload["checks"])
    assert any(check["name"] == "database_migrations" and check["status"] == "pass" for check in payload["checks"])


def test_production_configuration_rejects_unsafe_defaults(monkeypatch):
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("JWT_SECRET", "short")
    monkeypatch.setenv("DATABASE_URL", "sqlite:///./genlayer_bot.db")
    monkeypatch.setenv("ALLOWED_ORIGINS", "*")
    monkeypatch.setenv("SIWE_ORIGINS", "http://localhost:3000")
    monkeypatch.delenv("GENLAYER_RPC_URL_STUDIONET", raising=False)
    monkeypatch.delenv("GENLAYER_RPC_URL_BRADBURY", raising=False)

    failures = [check.name for check in configuration_checks() if check.required and not check.ok]
    assert {"jwt_secret", "database_configuration", "ALLOWED_ORIGINS", "SIWE_ORIGINS", "studionet_rpc", "bradbury_rpc"}.issubset(failures)
    with pytest.raises(RuntimeError, match="Unsafe production configuration"):
        assert_production_configuration()


def test_rpc_readiness_verifies_chain_identity(monkeypatch):
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("GENLAYER_RPC_URL_STUDIONET", "https://studio.test")
    monkeypatch.setenv("GENLAYER_RPC_URL_BRADBURY", "https://bradbury.test")
    monkeypatch.setenv("GENLAYER_CHAIN_ID_STUDIONET", "61999")
    monkeypatch.setenv("GENLAYER_CHAIN_ID_BRADBURY", "4221")

    class Response:
        def __init__(self, chain_id):
            self.chain_id = chain_id

        def raise_for_status(self):
            return None

        def json(self):
            return {"result": hex(self.chain_id)}

    def rpc_post(url, **_kwargs):
        return Response(61999 if "studio" in url else 4221)

    monkeypatch.setattr("backend.readiness.httpx.post", rpc_post)

    checks = rpc_connectivity_checks()

    assert len(checks) == 2
    assert all(check.ok for check in checks)


def test_rpc_readiness_rejects_wrong_chain(monkeypatch):
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("GENLAYER_RPC_URL_STUDIONET", "https://studio.test")
    monkeypatch.setenv("GENLAYER_RPC_URL_BRADBURY", "https://bradbury.test")

    class Response:
        def raise_for_status(self):
            return None

        def json(self):
            return {"result": "0x1"}

    monkeypatch.setattr("backend.readiness.httpx.post", lambda *_args, **_kwargs: Response())

    assert all(not check.ok for check in rpc_connectivity_checks())
