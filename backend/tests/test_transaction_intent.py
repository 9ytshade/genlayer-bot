from datetime import datetime, timedelta
import hashlib
from types import SimpleNamespace

import pytest
from eth_account import Account
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from web3 import Web3

from backend.database import Base
from backend.models import PreparedTransaction, User
from backend.transaction_intent import (
    _recompute_intent_hash,
    create_prepared_transaction,
    load_prepared_transaction,
    mark_prepared_transaction_confirmed,
    prepared_transaction_response,
    verify_submitted_transaction,
)


TX_HASH = "0x" + "ab" * 32
SENDER = Web3.to_checksum_address("0x32725d0b10fd24bf6439d5ec4b14d763c33fdef4")
DESTINATION = "0x2222222222222222222222222222222222222222"
STUDIO_PRIVATE_KEY = "0x" + "11" * 32
STUDIO_SENDER = Account.from_key(STUDIO_PRIVATE_KEY).address


def prepared_envelope():
    return SimpleNamespace(
        id="prepared-transaction-1",
        intent_hash="0x" + "cd" * 32,
        chain_id=61999,
        sender_address=SENDER,
        to_address=DESTINATION,
        data="0x1234",
        value_wei="9",
        nonce=7,
        gas_limit=1500000,
        gas_price="1",
        max_fee_per_gas=None,
        max_priority_fee_per_gas=None,
    )


def submitted_transaction(**overrides):
    return {
        "hash": TX_HASH,
        "from": SENDER,
        "to": DESTINATION,
        "input": "0x1234",
        "value": "0x9",
        "nonce": "0x7",
        "gas": hex(1500000),
        "gasPrice": "0x1",
        "chainId": hex(61999),
        **overrides,
    }


def studio_submitted_transaction(*, gas=2250000, gas_price=1, data="0x1234"):
    signed = Account.sign_transaction(
        {
            "chainId": 61999,
            "nonce": 7,
            "gasPrice": gas_price,
            "gas": gas,
            "to": DESTINATION,
            "value": 9,
            "data": data,
        },
        STUDIO_PRIVATE_KEY,
    )
    return {
        "hash": TX_HASH,
        "from_address": STUDIO_SENDER,
        "to_address": DESTINATION,
        "data": {},
        "sim_config": {
            "signed_rollup_transaction": "0x" + signed.raw_transaction.hex(),
        },
    }


def studio_prepared_envelope():
    envelope = prepared_envelope()
    envelope.sender_address = STUDIO_SENDER
    return envelope


class FakeClient:
    chain_id = 61999

    def __init__(self, transaction):
        self.transaction = transaction

    async def _rpc_call(self, method, params):
        assert method == "eth_getTransactionByHash"
        assert params == [TX_HASH]
        return self.transaction


@pytest.mark.asyncio
async def test_submitted_transaction_accepts_exact_reviewed_fields():
    result = await verify_submitted_transaction(
        client=FakeClient(submitted_transaction()),
        envelope=prepared_envelope(),
        tx_hash=TX_HASH,
    )

    assert result == TX_HASH


@pytest.mark.asyncio
async def test_bradbury_deployment_accepts_bounded_wallet_gas_normalization():
    envelope = prepared_envelope()
    envelope.network = "bradbury"
    envelope.action = "deploy_contract"

    result = await verify_submitted_transaction(
        client=FakeClient(submitted_transaction(gas=2250000)),
        envelope=envelope,
        tx_hash=TX_HASH,
    )

    assert result == TX_HASH


@pytest.mark.asyncio
async def test_bradbury_deployment_accepts_exact_legacy_fee_from_zero_tip_review():
    envelope = prepared_envelope()
    envelope.network = "bradbury"
    envelope.action = "deploy_contract"
    envelope.gas_price = None
    envelope.max_fee_per_gas = "2"
    envelope.max_priority_fee_per_gas = "0"

    result = await verify_submitted_transaction(
        client=FakeClient(submitted_transaction(gasPrice="0x2")),
        envelope=envelope,
        tx_hash=TX_HASH,
    )

    assert result == TX_HASH


@pytest.mark.asyncio
async def test_studionet_contract_call_accepts_exact_legacy_fee_from_zero_tip_review():
    envelope = prepared_envelope()
    envelope.network = "studionet"
    envelope.action = "contract_call"
    envelope.gas_price = None
    envelope.max_fee_per_gas = "2"
    envelope.max_priority_fee_per_gas = "0"

    result = await verify_submitted_transaction(
        client=FakeClient(submitted_transaction(gasPrice="0x2")),
        envelope=envelope,
        tx_hash=TX_HASH,
    )

    assert result == TX_HASH


@pytest.mark.asyncio
async def test_legacy_fee_normalization_rejects_changed_fee_amount():
    envelope = prepared_envelope()
    envelope.network = "bradbury"
    envelope.action = "deploy_contract"
    envelope.gas_price = None
    envelope.max_fee_per_gas = "2"
    envelope.max_priority_fee_per_gas = "0"

    with pytest.raises(HTTPException) as exc_info:
        await verify_submitted_transaction(
            client=FakeClient(submitted_transaction(gasPrice="0x3")),
            envelope=envelope,
            tx_hash=TX_HASH,
        )

    assert exc_info.value.detail["code"] == "transaction_fee_mode_mismatch"


@pytest.mark.asyncio
async def test_legacy_fee_normalization_rejects_nonzero_reviewed_tip():
    envelope = prepared_envelope()
    envelope.network = "bradbury"
    envelope.action = "deploy_contract"
    envelope.gas_price = None
    envelope.max_fee_per_gas = "2"
    envelope.max_priority_fee_per_gas = "1"

    with pytest.raises(HTTPException) as exc_info:
        await verify_submitted_transaction(
            client=FakeClient(submitted_transaction(gasPrice="0x2")),
            envelope=envelope,
            tx_hash=TX_HASH,
        )

    assert exc_info.value.detail["code"] == "transaction_fee_mode_mismatch"


@pytest.mark.asyncio
async def test_bradbury_transfer_rejects_unreviewed_gas_normalization():
    envelope = prepared_envelope()
    envelope.network = "bradbury"
    envelope.action = "transfer"

    with pytest.raises(HTTPException) as exc_info:
        await verify_submitted_transaction(
            client=FakeClient(submitted_transaction(gas=2250000)),
            envelope=envelope,
            tx_hash=TX_HASH,
        )

    assert exc_info.value.detail["field"] == "gas limit"
    assert exc_info.value.detail["accepted_gas_limits"] == [1500000]


@pytest.mark.asyncio
async def test_studio_signed_transaction_accepts_exact_intent_with_safety_buffer():
    result = await verify_submitted_transaction(
        client=FakeClient(studio_submitted_transaction()),
        envelope=studio_prepared_envelope(),
        tx_hash=TX_HASH,
    )

    assert result == TX_HASH


@pytest.mark.asyncio
async def test_studio_signed_transaction_accepts_zero_fee_eip1559_wallet_normalization():
    envelope = studio_prepared_envelope()
    envelope.gas_price = None
    envelope.max_fee_per_gas = "0"
    envelope.max_priority_fee_per_gas = "0"

    result = await verify_submitted_transaction(
        client=FakeClient(studio_submitted_transaction(gas_price=0)),
        envelope=envelope,
        tx_hash=TX_HASH,
    )

    assert result == TX_HASH


@pytest.mark.asyncio
async def test_regular_transaction_rejects_unreviewed_zero_fee_model():
    envelope = prepared_envelope()
    envelope.gas_price = None

    with pytest.raises(HTTPException) as exc_info:
        await verify_submitted_transaction(
            client=FakeClient(submitted_transaction(gasPrice="0x0")),
            envelope=envelope,
            tx_hash=TX_HASH,
        )

    assert exc_info.value.status_code == 400
    assert exc_info.value.detail["code"] == "transaction_fee_mode_mismatch"


@pytest.mark.asyncio
async def test_studio_signed_transfer_rejects_unreviewed_rabby_gas_estimate():
    envelope = studio_prepared_envelope()
    envelope.action = "transfer"
    envelope.gas_limit = 21000
    with pytest.raises(HTTPException) as exc_info:
        await verify_submitted_transaction(
            client=FakeClient(studio_submitted_transaction(gas=750000)),
            envelope=envelope,
            tx_hash=TX_HASH,
        )

    assert exc_info.value.status_code == 400
    assert exc_info.value.detail["field"] == "gas limit"
    assert exc_info.value.detail["accepted_gas_limits"] == [21000, 31500]


@pytest.mark.asyncio
async def test_studio_signed_transaction_rejects_tampered_calldata():
    with pytest.raises(HTTPException) as exc_info:
        await verify_submitted_transaction(
            client=FakeClient(studio_submitted_transaction(data="0xdeadbeef")),
            envelope=studio_prepared_envelope(),
            tx_hash=TX_HASH,
        )

    assert exc_info.value.status_code == 400
    assert exc_info.value.detail["code"] == "transaction_field_mismatch"
    assert exc_info.value.detail["field"] == "calldata"
    assert "calldata" not in exc_info.value.detail


@pytest.mark.asyncio
async def test_studio_signed_transaction_rejects_unreviewed_gas_buffer():
    with pytest.raises(HTTPException) as exc_info:
        await verify_submitted_transaction(
            client=FakeClient(studio_submitted_transaction(gas=2250001)),
            envelope=studio_prepared_envelope(),
            tx_hash=TX_HASH,
        )

    assert exc_info.value.status_code == 400
    assert exc_info.value.detail["code"] == "transaction_field_mismatch"
    assert exc_info.value.detail["field"] == "gas limit"
    assert exc_info.value.detail["accepted_gas_limits"] == [1500000, 2250000]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("overrides", "message", "code", "field"),
    [
        ({"from": "0x51F2e27c6C3b3A2351726548934Dde021eaAFc7e"}, "wallet", "wallet_mismatch", "wallet"),
        ({"to": "0x1111111111111111111111111111111111111111"}, "destination", "destination_mismatch", "destination"),
        ({"input": "0xdeadbeef"}, "calldata", "transaction_field_mismatch", "calldata"),
        ({"value": "0xa"}, "value", "transaction_field_mismatch", "value"),
        ({"gas": hex(1500001)}, "gas limit", "transaction_field_mismatch", "gas limit"),
        ({"chainId": hex(4221)}, "chain", "transaction_field_mismatch", "chain"),
    ],
)
async def test_submitted_transaction_rejects_security_field_mismatches(overrides, message, code, field):
    envelope = prepared_envelope()
    with pytest.raises(HTTPException) as exc_info:
        await verify_submitted_transaction(
            client=FakeClient(submitted_transaction(**overrides)),
            envelope=envelope,
            tx_hash=TX_HASH,
        )

    assert exc_info.value.status_code == 400
    detail = exc_info.value.detail
    assert detail["code"] == code
    assert message in detail["message"]
    assert detail["field"] == field
    assert detail["tx_hash"] == TX_HASH
    assert detail["prepared_transaction_id"] == envelope.id
    assert detail["intent_hash"] == envelope.intent_hash
    assert "calldata" not in detail


@pytest.mark.asyncio
async def test_wallet_mismatch_diagnostic_includes_expected_and_actual_wallets():
    actual_wallet = "0x51F2e27c6C3b3A2351726548934Dde021eaAFc7e"
    envelope = prepared_envelope()

    with pytest.raises(HTTPException) as exc_info:
        await verify_submitted_transaction(
            client=FakeClient(submitted_transaction(**{"from": actual_wallet})),
            envelope=envelope,
            tx_hash=TX_HASH,
        )

    detail = exc_info.value.detail
    assert detail["expected"] == envelope.sender_address
    assert detail["actual"] == actual_wallet


@pytest.mark.asyncio
async def test_submitted_transaction_rejects_missing_chain_proof():
    transaction = submitted_transaction()
    transaction.pop("chainId")
    with pytest.raises(HTTPException) as exc_info:
        await verify_submitted_transaction(
            client=FakeClient(transaction),
            envelope=prepared_envelope(),
            tx_hash=TX_HASH,
        )

    assert exc_info.value.status_code == 400
    assert exc_info.value.detail["code"] == "missing_transaction_chain"


@pytest.mark.asyncio
async def test_submitted_transaction_rejects_fee_model_swap():
    envelope = prepared_envelope()
    envelope.gas_price = None
    envelope.max_fee_per_gas = "2"
    envelope.max_priority_fee_per_gas = "1"
    with pytest.raises(HTTPException) as exc_info:
        await verify_submitted_transaction(
            client=FakeClient(submitted_transaction()),
            envelope=envelope,
            tx_hash=TX_HASH,
        )

    assert exc_info.value.status_code == 400
    assert exc_info.value.detail["code"] == "transaction_fee_mode_mismatch"


@pytest.fixture
def intent_db():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    session = sessionmaker(bind=engine)()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


def create_intent_envelope(db, *, wallet=SENDER):
    user = User(connected_wallet_address=wallet.lower())
    db.add(user)
    db.commit()
    db.refresh(user)
    envelope = create_prepared_transaction(
        db=db,
        user=user,
        action="transfer",
        network="studionet",
        sender_address=wallet,
        tx={
            "chain_id": 61999,
            "to": DESTINATION,
            "data": "0x1234",
            "value": 9,
            "gas_limit": 21000,
            "nonce": 7,
            "gasPrice": 1,
        },
        intent={
            "action": "transfer",
            "to_address": DESTINATION,
            "amount_wei": "9",
        },
    )
    return user, envelope


def test_version_two_intent_binds_id_expiry_and_calldata_hash(intent_db):
    user, envelope = create_intent_envelope(intent_db)
    response = prepared_transaction_response(envelope)

    assert envelope.intent_version == 2
    assert response["intent_version"] == 2
    assert response["calldata_hash"] == "0x" + hashlib.sha256(b"0x1234").hexdigest()

    original_hash = envelope.intent_hash
    envelope.id = "different-id"
    with pytest.raises(HTTPException) as id_error:
        load_prepared_transaction(
            db=intent_db,
            user=user,
            prepared_transaction_id=envelope.id,
            intent_hash=original_hash,
            action="transfer",
            network="studionet",
        )
    assert id_error.value.detail["code"] == "prepared_intent_integrity_failure"

    envelope.id = response["prepared_transaction_id"]
    envelope.expires_at += timedelta(seconds=1)
    with pytest.raises(HTTPException) as expiry_error:
        load_prepared_transaction(
            db=intent_db,
            user=user,
            prepared_transaction_id=envelope.id,
            intent_hash=original_hash,
            action="transfer",
            network="studionet",
        )
    assert expiry_error.value.detail["code"] == "prepared_intent_integrity_failure"


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("data", "0xdeadbeef"),
        ("value_wei", "10"),
        ("network", "testnet"),
        ("action", "contract_call"),
        ("intent_json", '{"action":"contract_call"}'),
    ],
)
def test_persisted_intent_tampering_fails_closed(intent_db, field, value):
    user, envelope = create_intent_envelope(intent_db)
    setattr(envelope, field, value)
    intent_db.commit()

    with pytest.raises(HTTPException) as exc_info:
        load_prepared_transaction(
            db=intent_db,
            user=user,
            prepared_transaction_id=envelope.id,
            intent_hash=envelope.intent_hash,
            action=envelope.action,
            network=envelope.network,
        )

    assert exc_info.value.status_code == 409
    assert exc_info.value.detail["code"] == "prepared_intent_integrity_failure"


def test_prepared_intent_is_wallet_scoped_and_rejects_wrong_request_binding(intent_db):
    user, envelope = create_intent_envelope(intent_db)
    other = User(connected_wallet_address="0x1111111111111111111111111111111111111111")
    intent_db.add(other)
    intent_db.commit()
    with pytest.raises(HTTPException) as owner_error:
        load_prepared_transaction(
            db=intent_db,
            user=other,
            prepared_transaction_id=envelope.id,
            intent_hash=envelope.intent_hash,
            action="transfer",
            network="studionet",
        )
    assert owner_error.value.status_code == 404

    with pytest.raises(HTTPException) as network_error:
        load_prepared_transaction(
            db=intent_db,
            user=user,
            prepared_transaction_id=envelope.id,
            intent_hash=envelope.intent_hash,
            action="transfer",
            network="testnet",
        )
    assert network_error.value.status_code == 400

    with pytest.raises(HTTPException) as action_error:
        load_prepared_transaction(
            db=intent_db,
            user=user,
            prepared_transaction_id=envelope.id,
            intent_hash=envelope.intent_hash,
            action="contract_call",
            network="studionet",
        )
    assert action_error.value.status_code == 400


def test_stale_and_consumed_intents_fail_closed(intent_db):
    user, envelope = create_intent_envelope(intent_db)
    envelope.expires_at = datetime.utcnow() - timedelta(seconds=1)
    envelope.intent_hash = _recompute_intent_hash(envelope)
    intent_db.commit()
    with pytest.raises(HTTPException) as expired_error:
        load_prepared_transaction(
            db=intent_db,
            user=user,
            prepared_transaction_id=envelope.id,
            intent_hash=envelope.intent_hash,
            action="transfer",
            network="studionet",
        )
    assert expired_error.value.status_code == 410
    intent_db.refresh(envelope)
    assert envelope.status == "expired"

    user, envelope = create_intent_envelope(intent_db, wallet="0x3333333333333333333333333333333333333333")
    envelope.status = "confirmed"
    intent_db.commit()
    with pytest.raises(HTTPException) as consumed_error:
        load_prepared_transaction(
            db=intent_db,
            user=user,
            prepared_transaction_id=envelope.id,
            intent_hash=envelope.intent_hash,
            action="transfer",
            network="studionet",
        )
    assert consumed_error.value.status_code == 409


def test_duplicate_transaction_hash_is_rejected_at_persistence_boundary(intent_db):
    _, first = create_intent_envelope(intent_db)
    _, second = create_intent_envelope(
        intent_db,
        wallet="0x4444444444444444444444444444444444444444",
    )
    mark_prepared_transaction_confirmed(db=intent_db, envelope=first, tx_hash=TX_HASH)

    with pytest.raises(HTTPException) as exc_info:
        mark_prepared_transaction_confirmed(db=intent_db, envelope=second, tx_hash=TX_HASH)

    assert exc_info.value.status_code == 409
    assert exc_info.value.detail["code"] == "transaction_hash_already_consumed"


class UnavailableClient:
    chain_id = 61999

    def __init__(self):
        self.attempts = 0

    async def _rpc_call(self, method, params):
        self.attempts += 1
        raise RuntimeError("RPC unavailable")


@pytest.mark.asyncio
async def test_rpc_outage_returns_retriable_diagnostic(monkeypatch):
    async def no_sleep(_delay):
        return None

    monkeypatch.setattr("backend.transaction_intent.asyncio.sleep", no_sleep)
    client = UnavailableClient()
    envelope = prepared_envelope()

    with pytest.raises(HTTPException) as exc_info:
        await verify_submitted_transaction(
            client=client,
            envelope=envelope,
            tx_hash=TX_HASH,
        )

    assert client.attempts == 5
    assert exc_info.value.status_code == 502
    assert exc_info.value.detail == {
        "code": "transaction_not_visible",
        "message": "Submitted transaction is not visible on the configured network.",
        "tx_hash": TX_HASH,
        "prepared_transaction_id": envelope.id,
        "intent_hash": envelope.intent_hash,
        "retriable": True,
        "retry_attempts": 5,
    }
