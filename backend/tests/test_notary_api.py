import json
import os

os.environ.setdefault("JWT_SECRET", "test-secret")
os.environ.setdefault("DATABASE_URL", "sqlite:///./test_chat_router.db")

from fastapi.testclient import TestClient

from backend.auth import create_access_token, normalize_address
from backend.database import SessionLocal
from backend.main import app
from backend.models import NotaryClaim, NotaryRegistry, User
from backend.routers import chat


OWNER = "0x75C53c08A011F423b948a5178023e0E9F8b4A2F1"
CLAIMANT = "0x51F2e27c6C3b3A2351726548934Dde021eaAFc7e"
OUTSIDER = "0x3333333333333333333333333333333333333333"
CONTRACT = "0x1111111111111111111111111111111111111111"


def ensure_user(wallet_address: str) -> User:
    wallet_address = normalize_address(wallet_address)
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.connected_wallet_address == wallet_address).first()
        if not user:
            user = User(connected_wallet_address=wallet_address)
            db.add(user)
            db.commit()
            db.refresh(user)
        db.expunge(user)
        return user
    finally:
        db.close()


def auth_headers(wallet_address: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {create_access_token(normalize_address(wallet_address))}"}


def notary_spec() -> dict:
    return {
        "statement": "GenLayer published the Intelligent Contracts documentation.",
        "source_urls": ["https://docs.genlayer.com/"],
    }


def create_registry(
    owner_address: str = OWNER,
    *,
    contract_address: str = CONTRACT,
    status: str = "active",
) -> NotaryRegistry:
    owner = ensure_user(owner_address)
    checksum_contract = normalize_address(contract_address)
    db = SessionLocal()
    try:
        registry_ids = [
            row[0]
            for row in db.query(NotaryRegistry.id).filter(
                NotaryRegistry.contract_address == checksum_contract,
                NotaryRegistry.network == "studionet",
            ).all()
        ]
        if registry_ids:
            db.query(NotaryClaim).filter(
                NotaryClaim.registry_id.in_(registry_ids)
            ).delete(synchronize_session=False)
        db.query(NotaryRegistry).filter(
            NotaryRegistry.contract_address == checksum_contract,
            NotaryRegistry.network == "studionet",
        ).delete(synchronize_session=False)
        registry = NotaryRegistry(
            user_id=owner.id,
            network="studionet",
            contract_address=checksum_contract,
            deploy_tx_hash="0x" + "11" * 32,
            consensus_tx_id="0x" + "12" * 32,
            status=status,
            source_hash="0x" + "13" * 32,
        )
        db.add(registry)
        db.commit()
        db.refresh(registry)
        db.expunge(registry)
        return registry
    finally:
        db.close()


def create_claim(
    registry_id: int,
    claimant_address: str,
    claim_id: str,
    *,
    status: str = "pending",
    verdict: str = "PENDING",
) -> None:
    claimant = ensure_user(claimant_address)
    db = SessionLocal()
    try:
        db.query(NotaryClaim).filter(
            NotaryClaim.registry_id == registry_id,
            NotaryClaim.claim_id == claim_id,
        ).delete(synchronize_session=False)
        db.add(
            NotaryClaim(
                registry_id=registry_id,
                user_id=claimant.id,
                claim_id=claim_id,
                spec_json=json.dumps(notary_spec(), separators=(",", ":")),
                status=status,
                verdict=verdict,
            )
        )
        db.commit()
    finally:
        db.close()


def fake_transaction(value: int = 0) -> dict:
    return {
        "chain_id": 61999,
        "to": "0x2222222222222222222222222222222222222222",
        "data": "0x1234",
        "value": value,
        "nonce": 9,
        "gas_limit": 1_500_000,
        "gasPrice": 1,
    }


def test_notary_blueprint_requires_auth_and_returns_canonical_metadata():
    wallet_address = ensure_user(CLAIMANT).connected_wallet_address

    with TestClient(app) as client:
        unauthorized = client.post("/chat/notary-blueprint", json={"notary_spec": notary_spec()})
        response = client.post(
            "/chat/notary-blueprint",
            json={"notary_spec": notary_spec()},
            headers=auth_headers(wallet_address),
        )

    assert unauthorized.status_code == 401
    assert response.status_code == 200
    body = response.json()
    assert body["contract_name"] == "AiNotaryRegistry"
    assert body["contract_type"] == "ai_notary"
    assert body["source_origin"] == "notary"
    assert body["notary_spec"]["claim_id"].startswith("notary-")
    assert len(body["notary_spec"]["claim_id"]) == 72
    assert body["notary_spec"]["claim_id"].split("-")[1] == CLAIMANT.lower()[2:]
    assert body["notary_spec"]["product_status"] == "prototype"
    assert body["constructor_args"] == [wallet_address]
    assert body["validation"]["valid"] is True


def test_notary_chat_completes_partial_blueprint_across_follow_up_messages(monkeypatch):
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    wallet_address = ensure_user(CLAIMANT).connected_wallet_address

    with TestClient(app) as client:
        first = client.post(
            "/chat",
            json={
                "message": "Notarize whether GenLayer published the Intelligent Contracts documentation",
                "wallet_address": wallet_address,
                "network": "studionet",
            },
        )
        partial_spec = first.json()["intent"]["notary_spec"]
        second = client.post(
            "/chat",
            json={
                "message": (
                    "Sources: https://docs.genlayer.com/\n"
                    "Rubric: CONFIRMED only when the documentation directly describes Intelligent Contracts.\n"
                    "Freshness rule: Use documentation available at evaluation time."
                ),
                "wallet_address": wallet_address,
                "network": "studionet",
                "notary_spec": partial_spec,
            },
        )

    assert first.status_code == 200
    assert first.json()["status"] == "awaiting_input"
    assert partial_spec["statement"] == "GenLayer published the Intelligent Contracts documentation"
    assert partial_spec["source_urls"] == []

    assert second.status_code == 200
    body = second.json()
    assert body["status"] == "awaiting_confirmation"
    assert body["intent"]["notary_spec"]["statement"] == partial_spec["statement"]
    assert body["intent"]["notary_spec"]["source_urls"] == ["https://docs.genlayer.com/"]
    assert body["intent"]["notary_spec"]["rubric"].startswith("CONFIRMED only")
    assert body["intent"]["notary_spec"]["freshness_rule"] == "Use documentation available at evaluation time."
    assert body["intent"]["notary_spec"]["claim_id"].startswith("notary-")


def test_notary_deploy_uses_exact_reviewed_source_and_rejects_stale_hash(monkeypatch):
    wallet_address = ensure_user(OWNER).connected_wallet_address
    built_codes: list[str] = []

    class FakeClient:
        rpc_url = "https://rpc.test"

        async def build_deploy_transaction(self, **kwargs):
            built_codes.append(kwargs["code"])
            assert kwargs["sender_address"] == wallet_address
            assert kwargs["args"] == [wallet_address]
            assert kwargs["value"] == 0
            return fake_transaction()

    monkeypatch.setattr(chat, "get_client", lambda network=None: FakeClient())

    with TestClient(app) as client:
        reviewed = client.post(
            "/chat/notary-blueprint",
            json={"notary_spec": notary_spec()},
            headers=auth_headers(wallet_address),
        ).json()
        deploy_payload = {
            "address": wallet_address,
            "notary_spec": reviewed["notary_spec"],
            "source_hash": reviewed["source_hash"],
            "py_genlayer_dependency": reviewed["py_genlayer_dependency"],
            "generator_version": reviewed["generator_version"],
            "validator_version": reviewed["validator_version"],
            "network": "studionet",
        }
        stale = client.post(
            "/chat/notary-deploy-tx",
            json={**deploy_payload, "source_hash": "0x" + "00" * 32},
            headers=auth_headers(wallet_address),
        )
        response = client.post(
            "/chat/notary-deploy-tx",
            json=deploy_payload,
            headers=auth_headers(wallet_address),
        )

    assert stale.status_code == 409
    assert response.status_code == 200
    body = response.json()
    assert built_codes == [reviewed["code"]]
    assert body["code"] == reviewed["code"]
    assert body["value"] == "0"
    assert body["source_hash"] == reviewed["source_hash"]
    assert body["prepared_intent"]["source_origin"] == "notary"
    assert body["prepared_intent"]["notary_operation"] == "deploy_registry"


def test_notary_submit_and_evaluate_build_exact_zero_value_calldata(monkeypatch):
    claimant = ensure_user(CLAIMANT).connected_wallet_address
    registry = create_registry()
    calls: list[dict] = []

    class FakeClient:
        rpc_url = "https://rpc.test"

        async def build_contract_call_transaction(self, **kwargs):
            calls.append(kwargs)
            assert kwargs["value"] == 0
            return fake_transaction()

    monkeypatch.setattr(chat, "get_client", lambda network=None: FakeClient())

    with TestClient(app) as client:
        reviewed = client.post(
            "/chat/notary-blueprint",
            json={"notary_spec": notary_spec()},
            headers=auth_headers(claimant),
        ).json()
        claim_id = reviewed["notary_spec"]["claim_id"]
        submit = client.post(
            "/chat/notary-call-tx",
            json={
                "address": claimant,
                "contract_address": CONTRACT,
                "notary_action": "submit_claim",
                "claim_id": claim_id,
                "notary_spec": reviewed["notary_spec"],
                "network": "studionet",
            },
            headers=auth_headers(claimant),
        )

        create_claim(registry.id, claimant, claim_id)
        evaluate = client.post(
            "/chat/notary-call-tx",
            json={
                "address": claimant,
                "contract_address": CONTRACT,
                "notary_action": "evaluate_claim",
                "claim_id": claim_id,
                "network": "studionet",
            },
            headers=auth_headers(claimant),
        )

    assert submit.status_code == 200
    assert evaluate.status_code == 200
    assert submit.json()["value"] == "0"
    assert evaluate.json()["value"] == "0"
    assert calls[0]["method"] == "submit_claim"
    assert calls[0]["args"] == [
        claim_id,
        reviewed["notary_spec"]["statement"],
        reviewed["notary_spec"]["source_urls"],
        reviewed["notary_spec"]["rubric"],
        reviewed["notary_spec"]["freshness_rule"],
    ]
    assert calls[1]["method"] == "evaluate_claim"
    assert calls[1]["args"] == [claim_id]
    assert submit.json()["prepared_intent"]["notary_operation"] == "submit_claim"
    assert evaluate.json()["prepared_intent"]["notary_operation"] == "evaluate_claim"


def test_notary_evaluation_is_restricted_to_claimant(monkeypatch):
    registry = create_registry()
    claimant = ensure_user(CLAIMANT).connected_wallet_address
    outsider = ensure_user(OUTSIDER).connected_wallet_address

    with TestClient(app) as client:
        reviewed = client.post(
            "/chat/notary-blueprint",
            json={"notary_spec": notary_spec()},
            headers=auth_headers(claimant),
        ).json()
        claim_id = reviewed["notary_spec"]["claim_id"]
        create_claim(registry.id, claimant, claim_id)
        response = client.post(
            "/chat/notary-call-tx",
            json={
                "address": outsider,
                "contract_address": CONTRACT,
                "notary_action": "evaluate_claim",
                "claim_id": claim_id,
                "network": "studionet",
            },
            headers=auth_headers(outsider),
        )

    assert response.status_code == 403
    assert response.json()["detail"] == "Only the claimant can evaluate this claim."


def test_notary_finalized_record_read_updates_cached_claim(monkeypatch):
    registry = create_registry()
    claimant = ensure_user(CLAIMANT).connected_wallet_address

    with TestClient(app) as client:
        reviewed = client.post(
            "/chat/notary-blueprint",
            json={"notary_spec": notary_spec()},
            headers=auth_headers(claimant),
        ).json()
    claim_id = reviewed["notary_spec"]["claim_id"]
    create_claim(registry.id, claimant, claim_id, status="evaluating")

    class FakeClient:
        async def read_contract(self, **kwargs):
            assert kwargs == {
                "caller_address": claimant,
                "contract_address": normalize_address(CONTRACT),
                "method": "get_claim",
                "args": [claim_id],
            }
            return {
                "claim_id": claim_id,
                "claimant": claimant,
                "statement": reviewed["notary_spec"]["statement"],
                "source_urls": reviewed["notary_spec"]["source_urls"],
                "rubric": reviewed["notary_spec"]["rubric"],
                "freshness_rule": reviewed["notary_spec"]["freshness_rule"],
                "verdict": "CONFIRMED",
                "source_statuses": ["USABLE"],
                "material_facts": ["s1: intelligent contracts documentation is published"],
                "rationale": "The cited public documentation supports the claim.",
                "failure_reason": "",
                "evaluated": True,
            }

    monkeypatch.setattr(chat, "get_client", lambda network=None: FakeClient())

    with TestClient(app) as client:
        response = client.get(
            f"/chat/notary-registries/{CONTRACT}/claims/{claim_id}?network=studionet",
            headers=auth_headers(claimant),
        )

    assert response.status_code == 200
    body = response.json()
    assert body["transaction_hash_variant"] == "latest-final"
    assert body["record"]["verdict"] == "CONFIRMED"
    assert body["record"]["evaluated"] is True

    db = SessionLocal()
    try:
        claim = db.query(NotaryClaim).filter(
            NotaryClaim.registry_id == registry.id,
            NotaryClaim.claim_id == claim_id,
        ).one()
        assert claim.status == "evaluated"
        assert claim.verdict == "CONFIRMED"
    finally:
        db.close()
