import os
import secrets
import json

os.environ.setdefault("JWT_SECRET", "test-secret")
os.environ.setdefault("DATABASE_URL", "sqlite:///./test_chat_router.db")

from fastapi.testclient import TestClient

from backend.auth import create_access_token, normalize_address
from backend.contract_artifacts import PINNED_DEPENDENCY_HEADER
from backend.database import SessionLocal
from backend.main import app
from backend.models import PreparedTransaction, User, WorkflowDeployment
from backend.routers import chat
from backend.transaction_intent import create_prepared_transaction


def test_chat_router_returns_unknown_for_unparsed_message(monkeypatch):
    monkeypatch.setattr(chat, "parse_intent", lambda _message, _wallet_address=None: {"action": "unknown"})

    with TestClient(app) as client:
        response = client.post("/chat", json={"message": "hello", "network": "studionet"})

    assert response.status_code == 200
    assert response.json()["intent"]["action"] == "unknown"


def create_confirmed_envelope(wallet_address: str, consensus_tx_id: str, action: str = "deploy_contract"):
    db = SessionLocal()
    try:
        user = db.query(User).filter(
            User.connected_wallet_address == normalize_address(wallet_address)
        ).first()
        envelope = create_prepared_transaction(
            db=db,
            user=user,
            action=action,
            network="studionet",
            sender_address=user.connected_wallet_address,
            tx={
                "chain_id": 61999,
                "to": "0x2222222222222222222222222222222222222222",
                "data": "0x",
                "value": 0,
                "nonce": 7,
                "gas_limit": 21000,
                "gasPrice": 1,
            },
            intent={"action": action},
        )
        envelope.status = "confirmed"
        envelope.consensus_tx_id = consensus_tx_id
        envelope.tx_hash = "0x" + secrets.token_hex(32)
        db.commit()
        return envelope.id, envelope.intent_hash
    finally:
        db.close()


def test_finalized_unknown_execution_remains_pollable_without_addresses(monkeypatch):
    consensus_tx_id = "0x" + "fb" * 32
    wallet_address = normalize_address("0x71E6E6D223A14D27A4CD4eDa6D240262d3B98F2d")
    db = SessionLocal()
    try:
        if not db.query(User).filter(User.connected_wallet_address == wallet_address).first():
            db.add(User(connected_wallet_address=wallet_address))
            db.commit()
    finally:
        db.close()

    prepared_id, intent_hash = create_confirmed_envelope(wallet_address, consensus_tx_id)

    class FakeClient:
        async def get_consensus_transaction_status(self, _consensus_tx_id):
            return {
                "status": "FINALIZED",
                "statusCode": 7,
                "final": True,
                "appealable": False,
                "terminal": True,
            }

        async def get_transaction_details(self, _consensus_tx_id):
            return {"execution_status": "UNKNOWN", "transaction": None}

        async def get_deployment_details(self, _consensus_tx_id, transaction=None):
            raise AssertionError("unverified execution must not expose deployment addresses")

    monkeypatch.setattr(chat, "get_client", lambda network=None: FakeClient())

    with TestClient(app) as client:
        response = client.post(
            "/chat/consensus-status",
            json={
                "consensus_tx_id": consensus_tx_id,
                "network": "studionet",
                "workflow_intent": {"action": "deploy_contract"},
                "prepared_transaction_id": prepared_id,
                "intent_hash": intent_hash,
            },
            headers={"Authorization": f"Bearer {create_access_token(wallet_address)}"},
        )

    body = response.json()
    assert response.status_code == 200
    assert body["final"] is True
    assert body["executionStatus"] == "UNKNOWN"
    assert body["terminal"] is False
    assert body["contractAddress"] is None
    assert body["derivedAddresses"] == []


def test_workflow_action_persists_only_after_successful_execution():
    wallet_address = normalize_address("0x32725d0B10fd24bF6439D5eC4B14D763C33fDeF4")
    contract_address = normalize_address("0xC249ECc2BCDf782b43A304d67bb97F3F4B5728B1")
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.connected_wallet_address == wallet_address).first()
        if not user:
            user = User(connected_wallet_address=wallet_address)
            db.add(user)
            db.commit()
            db.refresh(user)
        db.query(WorkflowDeployment).filter(
            WorkflowDeployment.user_id == user.id,
            WorkflowDeployment.contract_address == contract_address,
        ).delete()
        deployment = WorkflowDeployment(
            user_id=user.id,
            workflow_type="escrow",
            network="studionet",
            config_json=json.dumps({
                "workflowType": "escrow",
                "buyer": wallet_address,
                "seller": normalize_address("0x2222222222222222222222222222222222222222"),
                "amount": "1",
                "amountWei": "1000000000000000000",
                "token": "GEN",
                "description": "Test escrow",
                "validated": True,
                "errors": [],
            }),
            contract_address=contract_address,
            deploy_tx_hash="0x" + "31" * 32,
            consensus_tx_id="0x" + "32" * 32,
            status="active",
        )
        db.add(deployment)
        db.commit()

        intent = {
            "action": "contract_call",
            "contract_address": contract_address,
            "method": "approve_release",
            "tx_hash": "0x" + "33" * 32,
        }
        chat.update_workflow_consensus_state(
            db=db,
            user=user,
            consensus_tx_id="0x" + "34" * 32,
            workflow_intent=intent,
            consensus_status="FINALIZED",
            execution_status="FINISHED_WITH_ERROR",
            contract_address=None,
        )
        db.refresh(deployment)
        assert deployment.last_action is None
        assert deployment.status == "active"

        chat.update_workflow_consensus_state(
            db=db,
            user=user,
            consensus_tx_id="0x" + "35" * 32,
            workflow_intent=intent,
            consensus_status="FINALIZED",
            execution_status="FINISHED_WITH_RETURN",
            contract_address=None,
        )
        db.refresh(deployment)
        assert deployment.last_action == "approve_release"
        assert deployment.last_action_tx_hash == intent["tx_hash"]
        assert deployment.status == "active"
    finally:
        db.close()


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


def test_chat_and_contract_payload_limits_fail_before_processing():
    with TestClient(app) as client:
        chat_response = client.post(
            "/chat",
            json={"message": "x" * (chat.MAX_CHAT_MESSAGE_CHARS + 1)},
        )
        contract_response = client.post(
            "/chat/validate-contract",
            json={"code": "x" * (chat.MAX_CONTRACT_SOURCE_CHARS + 1), "file_name": "large.py"},
        )

    assert chat_response.status_code == 422
    assert contract_response.status_code == 422


def test_chat_history_rejects_excessive_chat_and_message_counts():
    wallet_address = normalize_address("0x6C88D71Df2f47fF67f09c39eD252E280Cc539992")
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.connected_wallet_address == wallet_address).first()
        if not user:
            db.add(User(connected_wallet_address=wallet_address))
            db.commit()
    finally:
        db.close()
    headers = {"Authorization": f"Bearer {create_access_token(wallet_address)}"}

    too_many_chats = [{"id": str(index), "messages": []} for index in range(chat.MAX_HISTORY_CHATS + 1)]
    too_many_messages = [
        {"id": str(index), "role": "user", "content": "hello"}
        for index in range(chat.MAX_HISTORY_MESSAGES_PER_CHAT + 1)
    ]

    with TestClient(app) as client:
        chats_response = client.put(
            "/chat/history",
            json={"chats": too_many_chats},
            headers=headers,
        )
        messages_response = client.put(
            "/chat/history",
            json={"chats": [{"id": "chat", "messages": too_many_messages}]},
            headers=headers,
        )

    assert chats_response.status_code == 422
    assert messages_response.status_code == 422


def test_finalized_execution_failure_never_activates_or_exposes_deployment(monkeypatch):
    wallet_address = normalize_address("0x51F2e27c6C3b3A2351726548934Dde021eaAFc7e")
    consensus_tx_id = "0x" + "fa" * 32
    leaked_address = normalize_address("0x8A4c5da6913b21251f71D0B04A799539ccEC0C1d")
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.connected_wallet_address == wallet_address).first()
        if not user:
            user = User(connected_wallet_address=wallet_address)
            db.add(user)
            db.commit()
            db.refresh(user)
        db.query(WorkflowDeployment).filter(
            WorkflowDeployment.user_id == user.id,
            WorkflowDeployment.consensus_tx_id == consensus_tx_id,
        ).delete()
        db.add(
            WorkflowDeployment(
                user_id=user.id,
                workflow_type="escrow",
                network="studionet",
                config_json="{}",
                contract_address=leaked_address,
                deploy_tx_hash="0x" + "21" * 32,
                consensus_tx_id=consensus_tx_id,
                status="submitted",
            )
        )
        db.commit()
    finally:
        db.close()

    prepared_id, intent_hash = create_confirmed_envelope(wallet_address, consensus_tx_id)

    class FakeClient:
        async def get_consensus_transaction_status(self, _consensus_tx_id):
            return {
                "status": "FINALIZED",
                "statusCode": 7,
                "final": True,
                "appealable": False,
                "terminal": True,
            }

        async def get_transaction_details(self, _consensus_tx_id):
            return {
                "execution_status": "FINISHED_WITH_ERROR",
                "transaction": {"data": {"contract_address": leaked_address}},
            }

        async def get_deployment_details(self, _consensus_tx_id, transaction=None):
            raise AssertionError("failed execution must not expose deployment addresses")

    monkeypatch.setattr(chat, "get_client", lambda network=None: FakeClient())
    token = create_access_token(wallet_address)

    with TestClient(app) as client:
        response = client.post(
            "/chat/consensus-status",
            json={
                "consensus_tx_id": consensus_tx_id,
                "network": "studionet",
                "workflow_intent": {"action": "deploy_contract"},
                "prepared_transaction_id": prepared_id,
                "intent_hash": intent_hash,
            },
            headers={"Authorization": f"Bearer {token}"},
        )

    body = response.json()
    assert response.status_code == 200
    assert body["status"] == "FINALIZED"
    assert body["executionStatus"] == "FINISHED_WITH_ERROR"
    assert body["terminal"] is True
    assert body["contractAddress"] is None
    assert body["derivedAddresses"] == []

    db = SessionLocal()
    try:
        deployment = db.query(WorkflowDeployment).filter(
            WorkflowDeployment.consensus_tx_id == consensus_tx_id
        ).first()
        assert deployment is not None
        assert deployment.status == "execution_failed"
        assert deployment.contract_address is None
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


def test_generate_contract_command_disables_unsafe_generic_escrow(monkeypatch):
    monkeypatch.setattr(chat.contract_generation_service, "client", None)

    with TestClient(app) as client:
        response = client.post(
            "/chat",
            json={"message": "/generate-contract Create an escrow contract that releases funds when both parties approve.", "network": "studionet"},
        )

    body = response.json()
    assert response.status_code == 200
    assert body["status"] == "error"
    assert body["intent"]["action"] == "generate_contract"
    assert body["capabilityCode"] == "generic_escrow_generation_rebuild_required"
    assert "guided escrow workflow" in body["content"]
    assert "generatedContract" not in body


def test_generate_counter_command_uses_deterministic_counter_template(monkeypatch):
    monkeypatch.setattr(chat.contract_generation_service, "client", None)

    with TestClient(app) as client:
        response = client.post(
            "/chat",
            json={"message": "/generate-contract Create a deterministic CounterCanary with increment and get_counter methods.", "network": "studionet"},
        )

    body = response.json()
    assert response.status_code == 200
    assert body["generatedContract"]["contractType"] == "counter"
    assert "class CounterCanary" in body["generatedContract"]["code"]
    assert "def increment" in body["generatedContract"]["code"]
    assert "def get_counter" in body["generatedContract"]["code"]


def test_screenshot_verification_generation_fails_closed(monkeypatch):
    monkeypatch.setattr(chat.contract_generation_service, "client", None)

    with TestClient(app) as client:
        response = client.post(
            "/chat",
            json={
                "message": "/generate-contract Verify a rendered website screenshot visually.",
                "network": "studionet",
            },
        )

    body = response.json()
    assert response.status_code == 200
    assert body["status"] == "error"
    assert body["validation"]["valid"] is False
    assert "Screenshot verification is unavailable" in body["content"]
    assert body["capabilityCode"] == "screenshot_verification_unproven"
    assert body["intent"]["capability_code"] == "screenshot_verification_unproven"
    assert "generatedContract" not in body


def test_generated_conditional_payment_with_code_is_not_blocked_by_amount_rule(monkeypatch):
    monkeypatch.setattr(
        chat,
        "parse_intent",
        lambda _message, _wallet_address=None: {
            "action": "conditional_payment",
            "recipient": "0x1111111111111111111111111111111111111111",
            "amount": "1",
            "condition": "AI misclassified uploaded source",
        },
    )
    code = f"""{PINNED_DEPENDENCY_HEADER}
from genlayer import *

class RainyDayPayment(gl.Contract):
    payer: Address
    recipient: Address

    def __init__(self, payer: Address, recipient: Address):
        self.payer = payer
        self.recipient = recipient

    @gl.public.view
    def payment_status(self) -> str:
        return "ready"
"""

    with TestClient(app) as client:
        response = client.post(
            "/chat",
            json={
                "message": f"Deploy this contract:\n\n{code}",
                "network": "studionet",
            },
        )

    body = response.json()
    assert response.status_code == 200
    assert body["status"] == "awaiting_confirmation"
    assert body["intent"]["action"] == "deploy_contract"


def test_uploaded_contract_uses_genlayer_aware_validation():
    code = f"""{PINNED_DEPENDENCY_HEADER}
from genlayer import *

class UnsafePayment(gl.Contract):
    amount: float

    def __init__(self):
        self.amount = 1.5

    @gl.public.view
    def payment_status(self) -> str:
        return "unsafe"
"""

    with TestClient(app) as client:
        response = client.post(
            "/chat",
            json={
                "message": f"Deploy this contract:\n\n{code}",
                "network": "studionet",
            },
        )

    body = response.json()
    assert response.status_code == 200
    assert body["status"] == "error"
    assert body["intent"]["action"] == "deploy_contract"
    assert body["validation"]["valid"] is False
    assert any("Floating-point" in error for error in body["validation"]["errors"])
    assert any("Storage field 'amount'" in error for error in body["validation"]["errors"])


def test_create_contract_language_routes_to_generation(monkeypatch):
    monkeypatch.setattr(chat.contract_generation_service, "client", None)

    with TestClient(app) as client:
        response = client.post(
            "/chat",
            json={"message": "create a contract that releases payment when I say hi", "network": "studionet"},
        )

    body = response.json()
    assert response.status_code == 200
    assert body["status"] == "error"
    assert body["capabilityCode"] == "conditional_payment_rebuild_required"
    assert "New conditional-payment deployment" in body["content"]
    assert "generatedContract" not in body


def test_consensus_status_keeps_accepted_deployment_provisional_then_finalizes(monkeypatch):
    wallet_address = normalize_address("0x29b8D6a0a43C26Ad7Cbc5848C25Df490ef42C80B")
    consensus_tx_id = "0x" + "ef" * 32
    contract_address = normalize_address("0x7D0299FBB1B3A99A780E9B795e2E25297aB60fe3")
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.connected_wallet_address == wallet_address).first()
        if not user:
            user = User(connected_wallet_address=wallet_address)
            db.add(user)
            db.commit()
            db.refresh(user)
        db.query(WorkflowDeployment).filter(
            WorkflowDeployment.user_id == user.id,
            WorkflowDeployment.consensus_tx_id == consensus_tx_id,
        ).delete()
        db.add(
            WorkflowDeployment(
                user_id=user.id,
                workflow_type="escrow",
                network="studionet",
                config_json="{}",
                deploy_tx_hash="0x" + "12" * 32,
                consensus_tx_id=consensus_tx_id,
                status="submitted",
            )
        )
        db.commit()
    finally:
        db.close()

    prepared_id, intent_hash = create_confirmed_envelope(wallet_address, consensus_tx_id)

    status_results = [
        {
            "status": "ACCEPTED",
            "statusCode": 5,
            "final": False,
            "appealable": True,
            "terminal": False,
        },
        {
            "status": "FINALIZED",
            "statusCode": 7,
            "final": True,
            "appealable": False,
            "terminal": True,
        },
    ]

    class FakeClient:
        async def get_consensus_transaction_status(self, _consensus_tx_id):
            return status_results.pop(0)

        async def get_transaction_details(self, _consensus_tx_id):
            return {
                "execution_status": "FINISHED_WITH_RETURN",
                "transaction": {"data": {"contract_address": contract_address}},
            }

        async def get_deployment_details(self, _consensus_tx_id, transaction=None):
            assert transaction == {"data": {"contract_address": contract_address}}
            return {"contract_address": contract_address, "derived_addresses": []}

    monkeypatch.setattr(chat, "get_client", lambda network=None: FakeClient())
    token = create_access_token(wallet_address)
    headers = {"Authorization": f"Bearer {token}"}
    request_body = {
        "consensus_tx_id": consensus_tx_id,
        "network": "studionet",
        "workflow_intent": {"action": "deploy_contract"},
        "prepared_transaction_id": prepared_id,
        "intent_hash": intent_hash,
    }

    with TestClient(app) as client:
        accepted_response = client.post("/chat/consensus-status", json=request_body, headers=headers)
        finalized_response = client.post("/chat/consensus-status", json=request_body, headers=headers)

    assert accepted_response.status_code == 200
    assert accepted_response.json()["status"] == "ACCEPTED"
    assert accepted_response.json()["final"] is False
    assert accepted_response.json()["contractAddress"] is None
    assert accepted_response.json()["lifecycleStatus"] == "CONSENSUS_PENDING"
    assert finalized_response.status_code == 200
    assert finalized_response.json()["status"] == "FINALIZED"
    assert finalized_response.json()["executionStatus"] == "FINISHED_WITH_RETURN"
    assert finalized_response.json()["terminal"] is True
    assert finalized_response.json()["contractAddress"] == contract_address
    assert finalized_response.json()["lifecycleStatus"] == "FINALIZED"

    db = SessionLocal()
    try:
        deployment = db.query(WorkflowDeployment).filter(
            WorkflowDeployment.consensus_tx_id == consensus_tx_id
        ).first()
        assert deployment is not None
        assert deployment.status == "active"
        assert deployment.contract_address == contract_address
        assert deployment.lifecycle_status == "FINALIZED"
        assert deployment.consensus_status == "FINALIZED"
        envelope = db.query(PreparedTransaction).filter(
            PreparedTransaction.id == prepared_id
        ).first()
        assert envelope is not None
        assert envelope.lifecycle_status == "FINALIZED"
        assert envelope.execution_status == "FINISHED_WITH_RETURN"
    finally:
        db.close()


def test_consensus_readiness_blocks_recent_zero_round_no_majority(monkeypatch):
    consensus_tx_id = "0x" + "91" * 32
    wallet_address = normalize_address("0x91E6E6D223A14D27A4CD4eDa6D240262d3B98F2d")
    db = SessionLocal()
    try:
        if not db.query(User).filter(User.connected_wallet_address == wallet_address).first():
            db.add(User(connected_wallet_address=wallet_address))
            db.commit()
    finally:
        db.close()
    create_confirmed_envelope(wallet_address, consensus_tx_id)
    class FakeClient:
        chain_id = 61999
        async def _rpc_call(self, method, params):
            return "0xf22f" if method == "eth_chainId" else "0x1"
        async def get_protocol_transaction_diagnostics(self, _consensus_tx_id):
            return {"protocol_result": "NO_MAJORITY", "num_rounds": 0, "validator_count": 0, "zero_round_no_majority": True}
    monkeypatch.setattr(chat, "get_client", lambda network=None: FakeClient())
    with TestClient(app) as client:
        response = client.get("/chat/consensus-readiness?network=studionet", headers={"Authorization": f"Bearer {create_access_token(wallet_address)}"})
    assert response.status_code == 200
    body = response.json()
    assert body["ready"] is False
    assert body["blockerCode"] == "studio_consensus_zero_round"
    assert body["protocolResult"] == "NO_MAJORITY"
    assert body["numRounds"] == 0
    assert body["validatorCount"] == 0


def test_consensus_status_recovers_consensus_id_from_confirmed_wallet_hash(monkeypatch):
    consensus_tx_id = "0x" + "92" * 32
    wallet_address = normalize_address("0x92E6E6D223A14D27A4CD4eDa6D240262d3B98F2d")
    db = SessionLocal()
    try:
        if not db.query(User).filter(User.connected_wallet_address == wallet_address).first():
            db.add(User(connected_wallet_address=wallet_address))
            db.commit()
    finally:
        db.close()
    prepared_id, intent_hash = create_confirmed_envelope(wallet_address, consensus_tx_id)
    db = SessionLocal()
    try:
        envelope = db.query(chat.PreparedTransaction).filter(chat.PreparedTransaction.id == prepared_id).first()
        tx_hash = envelope.tx_hash
        envelope.consensus_tx_id = None
        db.commit()
    finally:
        db.close()
    class FakeClient:
        async def get_consensus_transaction_id(self, value):
            assert value == tx_hash
            return consensus_tx_id
        async def get_consensus_transaction_status(self, value):
            assert value == consensus_tx_id
            return {"status": "PENDING", "statusCode": 1, "final": False, "appealable": False, "terminal": False}
    monkeypatch.setattr(chat, "get_client", lambda network=None: FakeClient())
    with TestClient(app) as client:
        response = client.post("/chat/consensus-status", json={"consensus_tx_id": tx_hash, "network": "studionet", "prepared_transaction_id": prepared_id, "intent_hash": intent_hash}, headers={"Authorization": f"Bearer {create_access_token(wallet_address)}"})
    assert response.status_code == 200
    assert response.json()["consensusTxId"] == consensus_tx_id
