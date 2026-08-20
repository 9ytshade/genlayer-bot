import os
from dataclasses import dataclass
from typing import Any

import httpx
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from .database import engine
from .network_config import get_network_config


PRODUCTION_ENVIRONMENTS = {"production", "prod"}
PLACEHOLDER_MARKERS = ("replace_with", "your_", "changeme", "change-me", "example")


@dataclass(frozen=True)
class ReadinessCheck:
    name: str
    ok: bool
    message: str
    required: bool = True

    def as_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "status": "pass" if self.ok else ("fail" if self.required else "warn"),
            "message": self.message,
        }


def deployment_environment() -> str:
    return (os.getenv("APP_ENV") or os.getenv("ENVIRONMENT") or "development").strip().lower()


def is_production() -> bool:
    return deployment_environment() in PRODUCTION_ENVIRONMENTS


def _configured(name: str) -> str:
    return os.getenv(name, "").strip()


def _is_placeholder(value: str) -> bool:
    lowered = value.lower()
    return any(marker in lowered for marker in PLACEHOLDER_MARKERS)


def _origin_check(name: str) -> ReadinessCheck:
    value = _configured(name)
    if not value:
        return ReadinessCheck(name, False, f"{name} must be explicitly configured.")
    origins = [origin.strip() for origin in value.split(",") if origin.strip()]
    if not origins or "*" in origins:
        return ReadinessCheck(name, False, f"{name} must contain explicit origins and cannot use '*'.")
    if is_production() and any(not origin.startswith("https://") for origin in origins):
        return ReadinessCheck(name, False, f"{name} must use HTTPS origins in production.")
    return ReadinessCheck(name, True, f"{len(origins)} explicit origin(s) configured.")


def configuration_checks() -> list[ReadinessCheck]:
    jwt_secret = _configured("JWT_SECRET")
    jwt_ok = len(jwt_secret) >= 32 and not _is_placeholder(jwt_secret)
    configured_database_url = _configured("DATABASE_URL")
    database_explicit = bool(configured_database_url)
    database_ok = database_explicit and (not is_production() or not configured_database_url.startswith("sqlite"))

    checks = [
        ReadinessCheck(
            "jwt_secret",
            jwt_ok,
            "JWT secret is configured with at least 32 non-placeholder characters."
            if jwt_ok
            else "JWT_SECRET must contain at least 32 non-placeholder characters.",
        ),
        ReadinessCheck(
            "database_configuration",
            database_ok,
            "DATABASE_URL is explicitly configured."
            if database_ok
            else "DATABASE_URL must be explicit and production cannot use SQLite.",
        ),
        _origin_check("ALLOWED_ORIGINS"),
        ReadinessCheck(
            "SIWE_ORIGINS",
            _origin_check("SIWE_ORIGINS").ok,
            _origin_check("SIWE_ORIGINS").message,
            required=is_production(),
        ),
    ]

    for network in ("STUDIONET", "BRADBURY"):
        rpc_url = _configured(f"GENLAYER_RPC_URL_{network}")
        rpc_ok = rpc_url.startswith(("http://", "https://")) and not _is_placeholder(rpc_url)
        checks.append(
            ReadinessCheck(
                f"{network.lower()}_rpc",
                rpc_ok,
                f"{network.title()} RPC URL is configured."
                if rpc_ok
                else f"GENLAYER_RPC_URL_{network} must be an explicit HTTP(S) URL.",
            )
        )

    redis_url = _configured("REDIS_URL")
    require_redis = _configured("REQUIRE_REDIS").lower() in {"1", "true", "yes"}
    checks.append(
        ReadinessCheck(
            "shared_log_store",
            bool(redis_url) or not require_redis,
            "Redis-backed logs are configured."
            if redis_url
            else "In-memory logs are active; set REDIS_URL and REQUIRE_REDIS=true for multi-instance deployments.",
            required=require_redis,
        )
    )
    return checks


def database_check() -> ReadinessCheck:
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        return ReadinessCheck("database_connection", True, "Database connection succeeded.")
    except SQLAlchemyError:
        return ReadinessCheck("database_connection", False, "Database connection failed.")


def migration_check() -> ReadinessCheck:
    try:
        backend_dir = __import__("pathlib").Path(__file__).resolve().parent
        config = Config(str(backend_dir / "alembic.ini"))
        config.set_main_option("script_location", str(backend_dir / "alembic"))
        expected_heads = set(ScriptDirectory.from_config(config).get_heads())
        with engine.connect() as connection:
            current_heads = {row[0] for row in connection.execute(text("SELECT version_num FROM alembic_version"))}
        if current_heads == expected_heads:
            return ReadinessCheck("database_migrations", True, "Database schema is at the current Alembic head.")
        return ReadinessCheck("database_migrations", False, "Database schema is not at the current Alembic head.")
    except (SQLAlchemyError, OSError):
        return ReadinessCheck("database_migrations", False, "Unable to verify the Alembic migration state.")


def rpc_connectivity_checks() -> list[ReadinessCheck]:
    enabled = is_production() or _configured("CHECK_RPC_READINESS").lower() in {"1", "true", "yes"}
    if not enabled:
        return []
    try:
        timeout = min(max(float(_configured("RPC_READINESS_TIMEOUT_SEC") or "5"), 1.0), 15.0)
    except ValueError:
        timeout = 5.0

    checks: list[ReadinessCheck] = []
    for network in ("studionet", "bradbury"):
        try:
            _, rpc_url, expected_chain_id = get_network_config(network)
            response = httpx.post(
                rpc_url,
                json={"jsonrpc": "2.0", "method": "eth_chainId", "params": [], "id": 1},
                timeout=timeout,
            )
            response.raise_for_status()
            payload = response.json()
            actual_chain_id = int(payload.get("result"), 16)
            ok = actual_chain_id == expected_chain_id
        except (httpx.HTTPError, TypeError, ValueError, AttributeError):
            ok = False
        checks.append(
            ReadinessCheck(
                f"{network}_rpc_connection",
                ok,
                f"{network.title()} RPC connectivity and chain identity verified."
                if ok
                else f"{network.title()} RPC connectivity or chain identity verification failed.",
            )
        )
    return checks


def readiness_report() -> dict[str, Any]:
    checks = [
        *configuration_checks(),
        database_check(),
        migration_check(),
        *rpc_connectivity_checks(),
    ]
    ready = all(check.ok or not check.required for check in checks)
    return {
        "status": "ready" if ready else "not_ready",
        "environment": deployment_environment(),
        "checks": [check.as_dict() for check in checks],
    }


def assert_production_configuration() -> None:
    if not is_production():
        return
    failures = [check.message for check in configuration_checks() if check.required and not check.ok]
    if failures:
        raise RuntimeError("Unsafe production configuration: " + " ".join(failures))
