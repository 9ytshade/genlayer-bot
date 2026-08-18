import os
import secrets
import json

os.environ.setdefault("JWT_SECRET", "test-secret")
os.environ.setdefault("DATABASE_URL", "sqlite:///./test_chat_router.db")

from fastapi.testclient import TestClient

from backend.auth import create_access_token, normalize_address
from backend.database import SessionLocal
from backend.main import app
from backend.models import User, WorkflowDeployment
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


def ensure_workflow_deployment(
    wallet_address: str,
    contract_address: str,
    workflow_config: dict,
    network: str = "studionet",
) -> None:
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.connected_wallet_address == wallet_address).first()
        assert user is not None
        checksum_contract = normalize_address(contract_address)
        db.query(WorkflowDeployment).filter(
            WorkflowDeployment.contract_address == checksum_contract,
            WorkflowDeployment.network == network,
        ).delete()
        db.add(WorkflowDeployment(
            user_id=user.id,
            workflow_type=workflow_config["workflowType"],
            network=network,
            config_json=json.dumps(validate_workflow_config(workflow_config, wallet_address)),
            contract_address=checksum_contract,
            status="active",
        ))
        db.commit()
    finally:
        db.close()


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


def test_disabled_workflow_endpoints_fail_closed_before_client_access(monkeypatch):
    wallet_address = ensure_user("0x19C785a005581D5D24E7B1A0147B9A519eB56B8f")
    headers = {"Authorization": f"Bearer {create_access_token(wallet_address)}"}

    def fail_if_client_accessed(network=None):
        raise AssertionError("Disabled workflows must fail before GenLayer client access")

    monkeypatch.setattr(chat, "get_client", fail_if_client_accessed)

    cases = [
        (
            "conditional_payment",
            "conditional_payment_rebuild_required",
            {
                "workflowType": "conditional_payment",
                "recipient": "0x2222222222222222222222222222222222222222",
                "amount": "1",
                "token": "GEN",
                "condition": "Evidence demonstrates delivery.",
            },
        ),
        (
            "bounty",
            "bounty_rebuild_required",
            {
                "workflowType": "bounty",
                "title": "Qualitative completion",
                "reward": "1",
                "token": "GEN",
                "description": "Validators judge whether the work is complete.",
            },
        ),
    ]

    with TestClient(app) as client:
        for workflow_type, expected_code, workflow_config in cases:
            review_response = client.post(
                "/chat/workflow-contract",
                json={"workflow_config": workflow_config},
                headers=headers,
            )
            deploy_response = client.post(
                "/chat/workflow-deploy-tx",
                json={
                    "address": wallet_address,
                    "workflow_config": workflow_config,
                    "network": "studionet",
                },
                headers=headers,
            )
            call_response = client.post(
                "/chat/contract-call-tx",
                json={
                    "address": wallet_address,
                    "contract_address": "0x1111111111111111111111111111111111111111",
                    "method": "settle",
                    "args": [],
                    "workflow_type": workflow_type,
                    "network": "studionet",
                },
                headers=headers,
            )

            for response in (review_response, deploy_response, call_response):
                assert response.status_code == 503
                assert response.json()["detail"]["code"] == expected_code


def test_phase9_conditional_harness_is_hidden_by_default(monkeypatch):
    wallet_address = ensure_user("0x19C785a005581D5D24E7B1A0147B9A519eB56B8f")
    headers = {"Authorization": f"Bearer {create_access_token(wallet_address)}"}
    monkeypatch.delenv(chat.PHASE9_LIVE_PROOF_ENV, raising=False)

    with TestClient(app) as client:
        response = client.post(
            "/chat/phase9/conditional-artifact",
            json={
                "workflow_config": {
                    "workflowType": "conditional_payment",
                    "recipient": "0x2222222222222222222222222222222222222222",
                    "amount": "0.01",
                    "token": "GEN",
                    "condition": "The source is official GenLayer documentation.",
                    "evidenceSources": ["https://docs.genlayer.com/"],
                },
            },
            headers=headers,
        )

    assert response.status_code == 404


def test_phase9_conditional_harness_uses_canonical_builder_and_exact_funding(monkeypatch):
    wallet_address = ensure_user("0x19C785a005581D5D24E7B1A0147B9A519eB56B8f")
    recipient = "0x2222222222222222222222222222222222222222"
    contract_address = "0x1111111111111111111111111111111111111111"
    headers = {"Authorization": f"Bearer {create_access_token(wallet_address)}"}
    workflow_config = {
        "workflowType": "conditional_payment",
        "recipient": recipient,
        "amount": "0.01",
        "token": "GEN",
        "condition": "The source is official GenLayer documentation.",
        "evidenceSources": ["https://docs.genlayer.com/"],
    }
    built_transactions = []

    class FakeClient:
        rpc_url = "https://rpc.test"

        async def build_deploy_transaction(self, **kwargs):
            built_transactions.append(("deploy", kwargs))
            return {
                "chain_id": 61999,
                "to": "0x2222222222222222222222222222222222222222",
                "data": "0x1234",
                "value": kwargs["value"],
                "nonce": 11,
                "gas_limit": 1500000,
                "gasPrice": 1,
            }

        async def build_contract_call_transaction(self, **kwargs):
            built_transactions.append(("call", kwargs))
            return {
                "chain_id": 61999,
                "to": "0x2222222222222222222222222222222222222222",
                "data": "0x5678",
                "value": kwargs["value"],
                "nonce": 12,
                "gas_limit": 1500000,
                "gasPrice": 1,
            }

    monkeypatch.setenv(chat.PHASE9_LIVE_PROOF_ENV, "1")
    monkeypatch.setattr(chat, "get_client", lambda network=None: FakeClient())

    with TestClient(app) as client:
        reviewed_response = client.post(
            "/chat/phase9/conditional-artifact",
            json={"workflow_config": workflow_config},
            headers=headers,
        )
        reviewed = reviewed_response.json()
        public_response = client.post(
            "/chat/workflow-deploy-tx",
            json={
                "address": wallet_address,
                "workflow_config": workflow_config,
                "source_hash": reviewed["source_hash"],
                "py_genlayer_dependency": reviewed["py_genlayer_dependency"],
                "generator_version": reviewed["generator_version"],
                "validator_version": reviewed["validator_version"],
                "network": "studionet",
            },
            headers=headers,
        )
        deploy_response = client.post(
            "/chat/phase9/conditional-deploy-tx",
            json={
                "address": wallet_address,
                "workflow_config": workflow_config,
                "source_hash": reviewed["source_hash"],
                "py_genlayer_dependency": reviewed["py_genlayer_dependency"],
                "generator_version": reviewed["generator_version"],
                "validator_version": reviewed["validator_version"],
                "network": "studionet",
            },
            headers=headers,
        )

        ensure_workflow_deployment(wallet_address, contract_address, workflow_config)
        fund_response = client.post(
            "/chat/phase9/conditional-call-tx",
            json={
                "address": wallet_address,
                "contract_address": contract_address,
                "method": "fund",
                "args": [],
                "workflow_type": "conditional_payment",
                "network": "studionet",
            },
            headers=headers,
        )

    assert reviewed_response.status_code == 200
    assert reviewed["constructor_args"] == [
        wallet_address,
        recipient,
        10**16,
        workflow_config["condition"],
        "GEN",
        "https://docs.genlayer.com/",
    ]
    assert public_response.status_code == 503
    assert deploy_response.status_code == 200
    assert deploy_response.json()["value"] == "0"
    assert built_transactions[0][1]["code"] == reviewed["code"]
    assert fund_response.status_code == 200
    assert fund_response.json()["value"] == str(10**16)
    assert built_transactions[1][1]["method"] == "fund"
    assert built_transactions[1][1]["value"] == 10**16


def test_workflow_deploy_uses_exact_reviewed_backend_source(monkeypatch):
    wallet_address = ensure_user("0x19C785a005581D5D24E7B1A0147B9A519eB56B8f")
    headers = {"Authorization": f"Bearer {create_access_token(wallet_address)}"}
    workflow_config = {
        "workflowType": "subscription",
        "recipient": "0x2222222222222222222222222222222222222222",
        "amount": 5,
        "token": "GEN",
        "frequency": "weekly",
    }
    built_codes = []

    class FakeClient:
        rpc_url = "https://rpc.test"

        async def build_deploy_transaction(self, **kwargs):
            built_codes.append(kwargs["code"])
            return {
                "chain_id": 61999,
                "to": "0x2222222222222222222222222222222222222222",
                "data": "0x1234",
                "value": 0,
                "nonce": 11,
                "gas_limit": 1500000,
                "gasPrice": 1,
            }

    monkeypatch.setattr(chat, "get_client", lambda network=None: FakeClient())

    with TestClient(app) as client:
        review_response = client.post(
            "/chat/workflow-contract",
            json={"workflow_config": workflow_config},
            headers=headers,
        )
        reviewed = review_response.json()
        stale_response = client.post(
            "/chat/workflow-deploy-tx",
            json={
                "address": wallet_address,
                "workflow_config": workflow_config,
                "source_hash": "0x" + "00" * 32,
                "py_genlayer_dependency": reviewed["py_genlayer_dependency"],
                "generator_version": reviewed["generator_version"],
                "validator_version": reviewed["validator_version"],
                "network": "studionet",
            },
            headers=headers,
        )
        deploy_response = client.post(
            "/chat/workflow-deploy-tx",
            json={
                "address": wallet_address,
                "workflow_config": workflow_config,
                "source_hash": reviewed["source_hash"],
                "py_genlayer_dependency": reviewed["py_genlayer_dependency"],
                "generator_version": reviewed["generator_version"],
                "validator_version": reviewed["validator_version"],
                "network": "studionet",
            },
            headers=headers,
        )

    assert review_response.status_code == 200
    assert stale_response.status_code == 409
    assert built_codes == [reviewed["code"]]
    assert deploy_response.status_code == 200
    deployed = deploy_response.json()
    assert deployed["source_hash"] == reviewed["source_hash"]
    assert deployed["prepared_intent"]["code"] == reviewed["code"]


def test_funded_workflow_deploy_builder_uses_exact_validated_wei(monkeypatch):
    wallet_address = ensure_user("0xA14A03E830a463eD1cC9ECF5F74D5a582F9843F2")
    headers = {"Authorization": f"Bearer {create_access_token(wallet_address)}"}
    workflow_config = {
        "workflowType": "escrow",
        "buyer": wallet_address,
        "seller": "0x2222222222222222222222222222222222222222",
        "amount": "1.25",
        "description": "delivery custody",
        "token": "GEN",
    }
    expected_value = 1250000000000000000

    class FakeClient:
        rpc_url = "https://rpc.test"

        async def build_deploy_transaction(self, **kwargs):
            assert kwargs["value"] == expected_value
            return {
                "chain_id": 61999,
                "to": "0x2222222222222222222222222222222222222222",
                "data": "0x1234",
                "value": kwargs["value"],
                "nonce": 12,
                "gas_limit": 1500000,
                "gasPrice": 1,
            }

    monkeypatch.setattr(chat, "get_client", lambda network=None: FakeClient())

    with TestClient(app) as client:
        reviewed = client.post(
            "/chat/workflow-contract",
            json={"workflow_config": workflow_config},
            headers=headers,
        ).json()
        request_body = {
            "address": wallet_address,
            "workflow_config": workflow_config,
            "source_hash": reviewed["source_hash"],
            "py_genlayer_dependency": reviewed["py_genlayer_dependency"],
            "generator_version": reviewed["generator_version"],
            "validator_version": reviewed["validator_version"],
            "network": "studionet",
        }
        mismatch = client.post(
            "/chat/workflow-deploy-tx",
            json={**request_body, "value_wei": "1"},
            headers=headers,
        )
        response = client.post(
            "/chat/workflow-deploy-tx",
            json=request_body,
            headers=headers,
        )

    assert mismatch.status_code == 400
    assert response.status_code == 200
    body = response.json()
    assert body["value"] == str(expected_value)
    assert body["prepared_intent"]["deploy_value_wei"] == str(expected_value)


def test_generated_contract_deploy_rejects_stale_generator_metadata(monkeypatch):
    wallet_address = ensure_user("0xA14A03E830a463eD1cC9ECF5F74D5a582F9843F2")
    headers = {"Authorization": f"Bearer {create_access_token(wallet_address)}"}
    monkeypatch.setattr(chat.contract_generation_service, "client", None)
    generated = chat.contract_generation_service.generate("Create a subscription contract")
    built_codes = []

    class FakeClient:
        rpc_url = "https://rpc.test"

        async def build_deploy_transaction(self, **kwargs):
            built_codes.append(kwargs["code"])
            return {
                "chain_id": 61999,
                "to": "0x2222222222222222222222222222222222222222",
                "data": "0x5678",
                "value": 0,
                "nonce": 12,
                "gas_limit": 1500000,
                "gasPrice": 1,
            }

    monkeypatch.setattr(chat, "get_client", lambda network=None: FakeClient())
    base_payload = {
        "address": wallet_address,
        "code": generated["code"],
        "source_hash": generated["source_hash"],
        "source_origin": "generated",
        "py_genlayer_dependency": generated["py_genlayer_dependency"],
        "generator_version": generated["generator_version"],
        "validator_version": generated["validator_version"],
        "network": "studionet",
    }

    with TestClient(app) as client:
        stale_response = client.post(
            "/chat/deploy-tx",
            json={**base_payload, "generator_version": "contract-generator:stale"},
            headers=headers,
        )
        deploy_response = client.post("/chat/deploy-tx", json=base_payload, headers=headers)

    assert stale_response.status_code == 409
    assert built_codes == [generated["code"]]
    assert deploy_response.status_code == 200
    deployed = deploy_response.json()
    assert deployed["source_hash"] == generated["source_hash"]
    assert deployed["prepared_intent"]["code"] == generated["code"]


def test_contract_call_builder_requires_authenticated_matching_wallet():
    wallet_address = ensure_user("0x51F2e27c6C3b3A2351726548934Dde021eaAFc7e")
    request_body = {
        "address": wallet_address,
        "contract_address": "0x1111111111111111111111111111111111111111",
        "method": "pause",
        "args": [],
        "workflow_type": "subscription",
        "network": "studionet",
    }

    with TestClient(app) as client:
        unauthorized = client.post("/chat/contract-call-tx", json=request_body)
        wrong_wallet = client.post(
            "/chat/contract-call-tx",
            json={**request_body, "address": "0x2222222222222222222222222222222222222222"},
            headers={"Authorization": f"Bearer {create_access_token(wallet_address)}"},
        )

    assert unauthorized.status_code == 401
    assert wrong_wallet.status_code == 403


def test_contract_call_tx_endpoint_builds_wallet_transaction(monkeypatch):
    wallet_address = ensure_user("0xfB73b3b3C379A8ec184959F114d19481B891d54E")
    headers = {"Authorization": f"Bearer {create_access_token(wallet_address)}"}
    ensure_workflow_deployment(
        wallet_address,
        "0x1111111111111111111111111111111111111111",
        {
            "workflowType": "subscription",
            "recipient": "0x2222222222222222222222222222222222222222",
            "amount": "1",
            "token": "GEN",
            "frequency": "weekly",
        },
    )

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
            headers=headers,
        )

    assert response.status_code == 200
    body = response.json()
    assert body["to"] == "0x2222222222222222222222222222222222222222"
    assert body["nonce"] == 7
    assert body["prepared_transaction_id"]
    assert body["intent_hash"].startswith("0x")


def test_subscription_payment_builder_attaches_exact_configured_wei(monkeypatch):
    wallet_address = ensure_user("0xBc12aB4C5f0De6D14f4d90ccBf5081a739DcFe62")
    contract_address = "0x1111111111111111111111111111111111111111"
    headers = {"Authorization": f"Bearer {create_access_token(wallet_address)}"}
    expected_value = 125000000000000000
    ensure_workflow_deployment(
        wallet_address,
        contract_address,
        {
            "workflowType": "subscription",
            "recipient": "0x2222222222222222222222222222222222222222",
            "amount": "0.125",
            "token": "GEN",
            "frequency": "weekly",
        },
    )

    class FakeClient:
        rpc_url = "https://rpc.test"

        async def build_contract_call_transaction(self, **kwargs):
            assert kwargs["method"] == "record_payment"
            assert kwargs["args"] == ["invoice-2026-08"]
            assert kwargs["value"] == expected_value
            return {
                "chain_id": 61999,
                "to": "0x2222222222222222222222222222222222222222",
                "data": "0x1234",
                "value": kwargs["value"],
                "nonce": 8,
                "gas_limit": 1500000,
                "gasPrice": 1,
            }

    monkeypatch.setattr(chat, "get_client", lambda network=None: FakeClient())
    request_body = {
        "address": wallet_address,
        "contract_address": contract_address,
        "method": "record_payment",
        "args": ["invoice-2026-08"],
        "workflow_type": "subscription",
        "network": "studionet",
    }

    with TestClient(app) as client:
        mismatch = client.post(
            "/chat/contract-call-tx",
            json={**request_body, "value_wei": "1"},
            headers=headers,
        )
        response = client.post(
            "/chat/contract-call-tx",
            json=request_body,
            headers=headers,
        )

    assert mismatch.status_code == 400
    assert response.status_code == 200
    body = response.json()
    assert body["value"] == str(expected_value)
    assert body["prepared_intent"]["value_wei"] == str(expected_value)


def test_contract_call_confirmation_requires_matching_prepared_transaction(monkeypatch):
    wallet_address = ensure_user("0x32725d0B10fd24bF6439D5eC4B14D763C33fDeF4")
    tx_hash = "0x" + secrets.token_hex(32)
    headers = {"Authorization": f"Bearer {create_access_token(wallet_address)}"}
    ensure_workflow_deployment(
        wallet_address,
        "0x1111111111111111111111111111111111111111",
        {
            "workflowType": "subscription",
            "recipient": "0x2222222222222222222222222222222222222222",
            "amount": "1",
            "token": "GEN",
            "frequency": "weekly",
        },
    )

    class FakeClient:
        rpc_url = "https://rpc.test"
        chain_id = 61999

        async def build_contract_call_transaction(self, **kwargs):
            return {
                "chain_id": 61999,
                "to": "0x2222222222222222222222222222222222222222",
                "data": "0x1234",
                "value": 0,
                "nonce": 7,
                "gas_limit": 1500000,
                "gasPrice": 1,
            }

        async def _rpc_call(self, method, params):
            assert method == "eth_getTransactionByHash"
            assert params == [tx_hash]
            return {
                "hash": tx_hash,
                "from": wallet_address,
                "to": "0x2222222222222222222222222222222222222222",
                "input": "0x1234",
                "value": "0x0",
                "nonce": "0x7",
                "gas": hex(1500000),
                "gasPrice": "0x1",
                "chainId": hex(61999),
            }

        async def _wait_for_receipt_or_raise(self, submitted_hash):
            assert submitted_hash == tx_hash

        async def get_consensus_transaction_id(self, tx_hash):
            return "0x" + "b" * 64

    monkeypatch.setattr(chat, "get_client", lambda network=None: FakeClient())

    with TestClient(app) as client:
        prepared_response = client.post(
            "/chat/contract-call-tx",
            json={
                "address": wallet_address,
                "contract_address": "0x1111111111111111111111111111111111111111",
                "method": "pause",
                "args": [],
                "workflow_type": "subscription",
                "network": "studionet",
            },
            headers=headers,
        )
        prepared = prepared_response.json()
        duplicate_prepared_response = client.post(
            "/chat/contract-call-tx",
            json={
                "address": wallet_address,
                "contract_address": "0x1111111111111111111111111111111111111111",
                "method": "pause",
                "args": [],
                "workflow_type": "subscription",
                "network": "studionet",
            },
            headers=headers,
        )
        duplicate_prepared = duplicate_prepared_response.json()
        confirm_payload = {
            "intent": {
                "action": "contract_call",
                "contract_address": "0x1111111111111111111111111111111111111111",
                "method": "pause",
                "args": [],
                "workflow_type": "subscription",
            },
            "tx_hash": tx_hash,
            "network": "studionet",
            "prepared_transaction_id": prepared["prepared_transaction_id"],
            "intent_hash": prepared["intent_hash"],
        }
        response = client.post(
            "/chat/confirm",
            json=confirm_payload,
            headers=headers,
        )
        replay_response = client.post("/chat/confirm", json=confirm_payload, headers=headers)
        duplicate_hash_response = client.post(
            "/chat/confirm",
            json={
                **confirm_payload,
                "prepared_transaction_id": duplicate_prepared["prepared_transaction_id"],
                "intent_hash": duplicate_prepared["intent_hash"],
            },
            headers=headers,
        )

    assert prepared_response.status_code == 200
    assert response.status_code == 200
    assert response.json()["consensusTxId"] == "0x" + "b" * 64
    assert response.json()["preparedTransactionId"] == prepared["prepared_transaction_id"]
    assert replay_response.status_code == 200
    assert replay_response.json()["preparedTransactionId"] == prepared["prepared_transaction_id"]
    assert duplicate_hash_response.status_code == 409


def test_escrow_seller_can_dispute_but_cannot_release(monkeypatch):
    buyer = ensure_user("0x32725d0B10fd24bF6439D5eC4B14D763C33fDeF4")
    seller = ensure_user("0x2222222222222222222222222222222222222222")
    contract = "0x1111111111111111111111111111111111111111"
    ensure_workflow_deployment(
        buyer,
        contract,
        {
            "workflowType": "escrow",
            "buyer": buyer,
            "seller": seller,
            "amount": "2.5",
            "token": "GEN",
            "description": "Seller authorization test",
        },
    )

    class FakeClient:
        rpc_url = "https://rpc.test"

        async def build_contract_call_transaction(self, **kwargs):
            assert kwargs["sender_address"] == seller
            assert kwargs["method"] == "raise_dispute"
            return {
                "chain_id": 61999,
                "to": "0x3333333333333333333333333333333333333333",
                "data": "0x1234",
                "value": 0,
                "nonce": 1,
                "gas_limit": 1500000,
                "gasPrice": 1,
            }

    monkeypatch.setattr(chat, "get_client", lambda network=None: FakeClient())
    headers = {"Authorization": f"Bearer {create_access_token(seller)}"}
    base_payload = {
        "address": seller,
        "contract_address": contract,
        "args": [],
        "workflow_type": "escrow",
        "network": "studionet",
    }

    with TestClient(app) as client:
        dispute = client.post(
            "/chat/contract-call-tx",
            json={**base_payload, "method": "raise_dispute"},
            headers=headers,
        )
        release = client.post(
            "/chat/contract-call-tx",
            json={**base_payload, "method": "approve_release"},
            headers=headers,
        )

    assert dispute.status_code == 200
    assert release.status_code == 403


def test_workflow_state_endpoint_returns_finalized_state_to_participant(monkeypatch):
    buyer = ensure_user("0x51F2e27c6C3b3A2351726548934Dde021eaAFc7e")
    seller = ensure_user("0x2222222222222222222222222222222222222222")
    outsider = ensure_user("0x3333333333333333333333333333333333333333")
    contract = "0x1111111111111111111111111111111111111111"
    ensure_workflow_deployment(
        buyer,
        contract,
        {
            "workflowType": "escrow",
            "buyer": buyer,
            "seller": seller,
            "amount": "1",
            "token": "GEN",
            "description": "State read test",
        },
    )

    class FakeClient:
        async def read_contract(self, **kwargs):
            assert kwargs["caller_address"] == seller
            assert kwargs["method"] == "get_state"
            return {
                "workflow_type": "escrow",
                "funded": True,
                "amount_wei": 10**18,
                "balance_wei": 10**18,
                "released": False,
                "disputed": False,
                "cancelled": False,
            }

    monkeypatch.setattr(chat, "get_client", lambda network=None: FakeClient())

    with TestClient(app) as client:
        participant_response = client.get(
            f"/chat/workflows/{contract}/state?network=studionet",
            headers={"Authorization": f"Bearer {create_access_token(seller)}"},
        )
        outsider_response = client.get(
            f"/chat/workflows/{contract}/state?network=studionet",
            headers={"Authorization": f"Bearer {create_access_token(outsider)}"},
        )

    assert participant_response.status_code == 200
    state = participant_response.json()
    assert state["transaction_hash_variant"] == "latest-final"
    assert state["state"]["amount_wei"] == str(10**18)
    assert state["state"]["balance_wei"] == str(10**18)
    assert outsider_response.status_code == 403
