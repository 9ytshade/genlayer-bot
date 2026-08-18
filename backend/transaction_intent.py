from __future__ import annotations

import asyncio
from datetime import datetime, timedelta
import hashlib
import json
import logging
import re
import secrets
from typing import Any

import rlp
from eth_account import Account
from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from web3 import Web3

from .models import PreparedTransaction, User


PREPARED_TRANSACTION_EXPIRE_MINUTES = 10
TRANSACTION_HASH_PATTERN = re.compile(r"^0x[a-fA-F0-9]{64}$")
INTENT_HASH_VERSION = 2
logger = logging.getLogger(__name__)


def _verification_detail(
    *,
    code: str,
    message: str,
    envelope: PreparedTransaction,
    tx_hash: str | None,
    **diagnostics: Any,
) -> dict[str, Any]:
    return {
        "code": code,
        "message": message,
        "tx_hash": tx_hash,
        "prepared_transaction_id": getattr(envelope, "id", None),
        "intent_hash": getattr(envelope, "intent_hash", None),
        **diagnostics,
    }


def _raise_verification_error(
    *,
    status_code: int,
    code: str,
    message: str,
    envelope: PreparedTransaction,
    tx_hash: str | None,
    **diagnostics: Any,
) -> None:
    detail = _verification_detail(
        code=code,
        message=message,
        envelope=envelope,
        tx_hash=tx_hash,
        **diagnostics,
    )
    logger.warning(
        "Submitted transaction verification failed",
        extra={
            "transaction_verification": {
                key: value
                for key, value in detail.items()
                if key not in {"expected", "actual"}
            }
        },
    )
    raise HTTPException(status_code=status_code, detail=detail)


def _canonical_json(value: Any) -> str:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    )


def _optional_integer_string(value: Any) -> str | None:
    if value is None:
        return None
    return str(int(value))


def _calldata_hash(data: str) -> str:
    return "0x" + hashlib.sha256(data.lower().encode("ascii")).hexdigest()


def _intent_hash(
    *,
    version: int,
    intent_id: str,
    action: str,
    network: str,
    intent: dict[str, Any],
    transaction: dict[str, Any],
    calldata_hash: str,
    expires_at: datetime,
) -> str:
    if version == 1:
        hash_payload = {
            "version": 1,
            "action": action,
            "network": network,
            "intent": intent,
            "transaction": transaction,
        }
    elif version == 2:
        hash_payload = {
            "version": 2,
            "intent_id": intent_id,
            "action": action,
            "network": network,
            "intent": intent,
            "transaction": transaction,
            "calldata_hash": calldata_hash,
            "expires_at": expires_at.isoformat(),
        }
    else:
        raise ValueError("Unsupported prepared transaction intent version.")
    return "0x" + hashlib.sha256(_canonical_json(hash_payload).encode("utf-8")).hexdigest()


def _recompute_intent_hash(envelope: PreparedTransaction) -> str:
    intent = json.loads(envelope.intent_json)
    if not isinstance(intent, dict):
        raise ValueError("Prepared transaction intent is invalid.")
    data = str(envelope.data or "0x").lower()
    calldata_hash = getattr(envelope, "calldata_hash", None) or _calldata_hash(data)
    transaction = {
        "chain_id": int(envelope.chain_id),
        "from": envelope.sender_address,
        "to": envelope.to_address,
        "data": data,
        "value_wei": str(envelope.value_wei),
        "gas_limit": int(envelope.gas_limit),
        "nonce": int(envelope.nonce),
        "gas_price": envelope.gas_price,
        "max_fee_per_gas": envelope.max_fee_per_gas,
        "max_priority_fee_per_gas": envelope.max_priority_fee_per_gas,
        "consensus_max_rotations": envelope.consensus_max_rotations,
        "leader_only": bool(envelope.leader_only),
    }
    return _intent_hash(
        version=int(getattr(envelope, "intent_version", 1) or 1),
        intent_id=envelope.id,
        action=envelope.action,
        network=envelope.network,
        intent=intent,
        transaction=transaction,
        calldata_hash=calldata_hash,
        expires_at=envelope.expires_at,
    )


def create_prepared_transaction(
    *,
    db: Session,
    user: User,
    action: str,
    network: str,
    sender_address: str,
    tx: dict[str, Any],
    intent: dict[str, Any],
    consensus_max_rotations: int | None = None,
    leader_only: bool = False,
) -> PreparedTransaction:
    sender = Web3.to_checksum_address(sender_address)
    destination = Web3.to_checksum_address(tx["to"])
    transaction_payload = {
        "chain_id": int(tx["chain_id"]),
        "from": sender,
        "to": destination,
        "data": str(tx.get("data") or "0x").lower(),
        "value_wei": str(int(tx.get("value") or 0)),
        "gas_limit": int(tx["gas_limit"]),
        "nonce": int(tx["nonce"]),
        "gas_price": _optional_integer_string(tx.get("gasPrice")),
        "max_fee_per_gas": _optional_integer_string(tx.get("maxFeePerGas")),
        "max_priority_fee_per_gas": _optional_integer_string(tx.get("maxPriorityFeePerGas")),
        "consensus_max_rotations": consensus_max_rotations,
        "leader_only": bool(leader_only),
    }
    prepared_id = secrets.token_urlsafe(24)
    expires_at = datetime.utcnow() + timedelta(minutes=PREPARED_TRANSACTION_EXPIRE_MINUTES)
    calldata_hash = _calldata_hash(transaction_payload["data"])
    intent_hash = _intent_hash(
        version=INTENT_HASH_VERSION,
        intent_id=prepared_id,
        action=action,
        network=network,
        intent=intent,
        transaction=transaction_payload,
        calldata_hash=calldata_hash,
        expires_at=expires_at,
    )
    envelope = PreparedTransaction(
        id=prepared_id,
        user_id=user.id,
        action=action,
        network=network,
        chain_id=transaction_payload["chain_id"],
        sender_address=sender,
        to_address=destination,
        data=transaction_payload["data"],
        calldata_hash=calldata_hash,
        value_wei=transaction_payload["value_wei"],
        gas_limit=transaction_payload["gas_limit"],
        nonce=transaction_payload["nonce"],
        gas_price=transaction_payload["gas_price"],
        max_fee_per_gas=transaction_payload["max_fee_per_gas"],
        max_priority_fee_per_gas=transaction_payload["max_priority_fee_per_gas"],
        consensus_max_rotations=consensus_max_rotations,
        leader_only=bool(leader_only),
        intent_json=_canonical_json(intent),
        intent_hash=intent_hash,
        intent_version=INTENT_HASH_VERSION,
        status="prepared",
        lifecycle_status="PREPARED",
        evm_status="NOT_BROADCAST",
        consensus_status="UNINITIALIZED",
        execution_status="UNKNOWN",
        final=False,
        terminal=False,
        appealable=False,
        zero_round_no_majority=False,
        diagnostic_json="{}",
        expires_at=expires_at,
    )
    db.add(envelope)
    db.commit()
    db.refresh(envelope)
    return envelope


def prepared_transaction_response(envelope: PreparedTransaction) -> dict[str, Any]:
    return {
        "prepared_transaction_id": envelope.id,
        "intent_hash": envelope.intent_hash,
        "calldata_hash": envelope.calldata_hash,
        "intent_version": envelope.intent_version,
        "prepared_intent": json.loads(envelope.intent_json),
        "expires_at": envelope.expires_at.isoformat() if envelope.expires_at else None,
    }


def load_prepared_transaction(
    *,
    db: Session,
    user: User,
    prepared_transaction_id: str | None,
    intent_hash: str | None,
    action: str,
    network: str,
    allow_expired_reconciliation: bool = False,
    allow_confirmed_reconciliation: bool = False,
) -> PreparedTransaction:
    if not prepared_transaction_id or not intent_hash:
        raise HTTPException(
            status_code=400,
            detail="Confirmation requires the prepared transaction id and intent hash.",
        )
    envelope = (
        db.query(PreparedTransaction)
        .filter(
            PreparedTransaction.id == prepared_transaction_id,
            PreparedTransaction.user_id == user.id,
        )
        .first()
    )
    if not envelope:
        raise HTTPException(status_code=404, detail="Prepared transaction was not found.")
    if envelope.intent_hash != intent_hash:
        raise HTTPException(status_code=400, detail="Prepared transaction intent hash does not match.")
    if envelope.action != action:
        raise HTTPException(status_code=400, detail="Prepared transaction action does not match.")
    if envelope.network != network:
        raise HTTPException(status_code=400, detail="Prepared transaction network does not match.")
    try:
        if envelope.intent_version >= 2 and envelope.calldata_hash != _calldata_hash(envelope.data):
            raise ValueError("calldata hash mismatch")
        if _recompute_intent_hash(envelope) != envelope.intent_hash:
            raise ValueError("intent hash mismatch")
    except (TypeError, ValueError, json.JSONDecodeError) as exc:
        raise HTTPException(
            status_code=409,
            detail={
                "code": "prepared_intent_integrity_failure",
                "message": "Prepared transaction integrity verification failed.",
                "prepared_transaction_id": envelope.id,
            },
        ) from exc
    if envelope.status != "prepared":
        if not (
            (allow_expired_reconciliation and envelope.status == "expired")
            or (allow_confirmed_reconciliation and envelope.status == "confirmed")
        ):
            raise HTTPException(status_code=409, detail="Prepared transaction has already been consumed.")
    if (
        envelope.expires_at
        and datetime.utcnow() >= envelope.expires_at
        and not allow_expired_reconciliation
    ):
        envelope.status = "expired"
        db.commit()
        raise HTTPException(status_code=410, detail="Prepared transaction has expired.")
    return envelope


def prepared_intent(envelope: PreparedTransaction) -> dict[str, Any]:
    try:
        intent = json.loads(envelope.intent_json)
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=500, detail="Prepared transaction intent is invalid.") from exc
    if not isinstance(intent, dict):
        raise HTTPException(status_code=500, detail="Prepared transaction intent is invalid.")
    return intent


def _rpc_integer(value: Any) -> int:
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        return int(value, 16) if value.lower().startswith("0x") else int(value)
    raise ValueError("Transaction field is not an integer.")


def _rpc_data(transaction: dict[str, Any]) -> str:
    return str(transaction.get("input") or transaction.get("data") or "0x").lower()


def _decode_studio_signed_transaction(transaction: dict[str, Any]) -> dict[str, Any] | None:
    sim_config = transaction.get("sim_config")
    raw_transaction = sim_config.get("signed_rollup_transaction") if isinstance(sim_config, dict) else None
    if not isinstance(raw_transaction, str) or not raw_transaction.startswith("0x"):
        return None
    try:
        raw_bytes = Web3.to_bytes(hexstr=raw_transaction)
        decoded = rlp.decode(raw_bytes)
        if len(decoded) != 9 or not all(isinstance(value, bytes) for value in decoded):
            return None
        nonce, gas_price, gas_limit, destination, value, calldata, signature_v, _, _ = decoded
        signature_v_int = int.from_bytes(signature_v, "big")
        chain_id = (signature_v_int - 35) // 2 if signature_v_int >= 35 else None
        decoded_transaction: dict[str, Any] = {
            "from": Account.recover_transaction(raw_transaction),
            "to": Web3.to_checksum_address(destination.hex()) if len(destination) == 20 else None,
            "input": "0x" + calldata.hex(),
            "value": int.from_bytes(value, "big"),
            "nonce": int.from_bytes(nonce, "big"),
            "gas": int.from_bytes(gas_limit, "big"),
            "gasPrice": int.from_bytes(gas_price, "big"),
            "_studio_signed_transaction": True,
        }
        if chain_id is not None:
            decoded_transaction["chainId"] = chain_id
        return decoded_transaction
    except (TypeError, ValueError, IndexError, rlp.exceptions.DecodingError):
        return None


def _normalize_rpc_transaction(transaction: dict[str, Any]) -> dict[str, Any]:
    normalized = dict(transaction)
    normalized.setdefault("from", transaction.get("from_address") or transaction.get("origin_address"))
    normalized.setdefault("to", transaction.get("to_address") or transaction.get("recipient"))
    normalized.setdefault("input", transaction.get("input") or (transaction.get("data") if isinstance(transaction.get("data"), str) else None))
    normalized.setdefault("gas", transaction.get("gaslimit"))
    normalized.setdefault("chainId", transaction.get("chain_id"))
    studio_transaction = _decode_studio_signed_transaction(transaction)
    if studio_transaction:
        normalized.update(studio_transaction)
    return normalized


async def _get_transaction_by_hash(
    client: Any,
    tx_hash: str,
    envelope: PreparedTransaction,
) -> dict[str, Any]:
    last_error: Exception | None = None
    for delay in (0.0, 0.25, 0.75, 1.5, 2.5):
        if delay:
            await asyncio.sleep(delay)
        try:
            transaction = await client._rpc_call("eth_getTransactionByHash", [tx_hash])
        except Exception as exc:
            last_error = exc
            continue
        if isinstance(transaction, dict):
            return transaction
    try:
        _raise_verification_error(
            status_code=502,
            code="transaction_not_visible",
            message="Submitted transaction is not visible on the configured network.",
            envelope=envelope,
            tx_hash=tx_hash,
            retriable=True,
            retry_attempts=5,
        )
    except HTTPException as exc:
        raise exc from last_error


async def verify_submitted_transaction(
    *,
    client: Any,
    envelope: PreparedTransaction,
    tx_hash: str | None,
) -> str:
    if not isinstance(tx_hash, str) or not TRANSACTION_HASH_PATTERN.fullmatch(tx_hash):
        _raise_verification_error(
            status_code=400,
            code="invalid_transaction_hash",
            message="Confirmation requires a valid wallet transaction hash.",
            envelope=envelope,
            tx_hash=tx_hash,
        )
    configured_chain_id = int(getattr(client, "chain_id", envelope.chain_id))
    if configured_chain_id != envelope.chain_id:
        _raise_verification_error(
            status_code=400,
            code="configured_chain_mismatch",
            message="Configured network does not match the prepared chain.",
            envelope=envelope,
            tx_hash=tx_hash,
            field="chain",
            expected=envelope.chain_id,
            actual=configured_chain_id,
        )

    transaction = _normalize_rpc_transaction(await _get_transaction_by_hash(client, tx_hash, envelope))
    sender = transaction.get("from")
    destination = transaction.get("to")
    returned_hash = transaction.get("hash")
    if isinstance(returned_hash, str) and returned_hash.lower() != tx_hash.lower():
        _raise_verification_error(
            status_code=400,
            code="rpc_transaction_hash_mismatch",
            message="RPC returned a different transaction hash.",
            envelope=envelope,
            tx_hash=tx_hash,
        )
    try:
        sender_matches = (
            isinstance(sender, str)
            and Web3.to_checksum_address(sender) == envelope.sender_address
        )
        destination_matches = (
            isinstance(destination, str)
            and Web3.to_checksum_address(destination) == envelope.to_address
        )
    except ValueError:
        sender_matches = False
        destination_matches = False
    if not sender_matches:
        _raise_verification_error(
            status_code=400,
            code="wallet_mismatch",
            message="Submitted transaction wallet does not match the reviewed wallet.",
            envelope=envelope,
            tx_hash=tx_hash,
            field="wallet",
            expected=envelope.sender_address,
            actual=sender if isinstance(sender, str) else None,
        )
    if not destination_matches:
        _raise_verification_error(
            status_code=400,
            code="destination_mismatch",
            message="Submitted transaction destination does not match the reviewed destination.",
            envelope=envelope,
            tx_hash=tx_hash,
            field="destination",
            expected=envelope.to_address,
            actual=destination if isinstance(destination, str) else None,
        )

    try:
        comparisons = (
            ("calldata", _rpc_data(transaction), envelope.data.lower()),
            ("value", _rpc_integer(transaction.get("value", 0)), int(envelope.value_wei)),
            ("nonce", _rpc_integer(transaction.get("nonce")), envelope.nonce),
        )
        actual_gas = _rpc_integer(transaction.get("gas"))
    except (TypeError, ValueError):
        _raise_verification_error(
            status_code=400,
            code="malformed_transaction_fields",
            message="Submitted transaction fields are malformed.",
            envelope=envelope,
            tx_hash=tx_hash,
        )
    for label, actual, expected in comparisons:
        if actual != expected:
            _raise_verification_error(
                status_code=400,
                code="transaction_field_mismatch",
                message=f"Submitted transaction {label} does not match the reviewed transaction.",
                envelope=envelope,
                tx_hash=tx_hash,
                field=label,
            )
    allowed_gas_limits = {envelope.gas_limit}
    bounded_wallet_normalization = (
        transaction.get("_studio_signed_transaction")
        or (
            getattr(envelope, "network", None) in {"studionet", "bradbury"}
            and getattr(envelope, "action", None) in {"deploy_contract", "contract_call"}
        )
    )
    if bounded_wallet_normalization:
        allowed_gas_limits.add((envelope.gas_limit * 3 + 1) // 2)
    gas_matches = actual_gas in allowed_gas_limits
    if not gas_matches:
        _raise_verification_error(
            status_code=400,
            code="transaction_field_mismatch",
            message="Submitted transaction gas limit does not match the reviewed transaction.",
            envelope=envelope,
            tx_hash=tx_hash,
            field="gas limit",
            expected=envelope.gas_limit,
            actual=actual_gas,
            accepted_gas_limits=sorted(allowed_gas_limits),
        )

    chain_id = transaction.get("chainId")
    if chain_id is None:
        _raise_verification_error(
            status_code=400,
            code="missing_transaction_chain",
            message="Submitted transaction does not provide verifiable chain identity.",
            envelope=envelope,
            tx_hash=tx_hash,
            field="chain",
        )
    try:
        actual_chain_id = _rpc_integer(chain_id)
    except (TypeError, ValueError):
        _raise_verification_error(
            status_code=400,
            code="malformed_transaction_chain",
            message="Submitted transaction chain is malformed.",
            envelope=envelope,
            tx_hash=tx_hash,
            field="chain",
        )
    if actual_chain_id != envelope.chain_id:
        _raise_verification_error(
            status_code=400,
            code="transaction_field_mismatch",
            message="Submitted transaction chain does not match the reviewed chain.",
            envelope=envelope,
            tx_hash=tx_hash,
            field="chain",
            expected=envelope.chain_id,
            actual=actual_chain_id,
        )

    expected_fee_mode = (
        "legacy" if envelope.gas_price is not None else "eip1559"
        if envelope.max_fee_per_gas is not None or envelope.max_priority_fee_per_gas is not None
        else "none"
    )
    actual_fee_mode = "eip1559" if (
        transaction.get("maxFeePerGas") is not None or transaction.get("maxPriorityFeePerGas") is not None
    ) else "legacy" if transaction.get("gasPrice") is not None else "none"
    studio_zero_fee_normalization = False
    wallet_legacy_fee_normalization = False
    if actual_fee_mode == "legacy" and transaction.get("_studio_signed_transaction"):
        try:
            expected_zero_fee = (
                envelope.gas_price is None
                and all(
                    value is None or int(value) == 0
                    for value in (envelope.max_fee_per_gas, envelope.max_priority_fee_per_gas)
                )
            )
            studio_zero_fee_normalization = (
                expected_fee_mode in {"none", "eip1559"}
                and expected_zero_fee
                and _rpc_integer(transaction.get("gasPrice")) == 0
            )
        except (TypeError, ValueError):
            studio_zero_fee_normalization = False
    if actual_fee_mode == "legacy" and expected_fee_mode == "eip1559":
        wallet_legacy_fee_normalization = (
            getattr(envelope, "network", None) in {"studionet", "bradbury"}
            and getattr(envelope, "action", None) in {"deploy_contract", "contract_call"}
            and envelope.max_fee_per_gas is not None
            and envelope.max_priority_fee_per_gas is not None
            and int(envelope.max_priority_fee_per_gas) == 0
        )
        if wallet_legacy_fee_normalization:
            try:
                wallet_legacy_fee_normalization = (
                    transaction.get("gasPrice") is not None
                    and _rpc_integer(transaction.get("gasPrice")) == int(envelope.max_fee_per_gas)
                )
            except (TypeError, ValueError):
                wallet_legacy_fee_normalization = False
    if actual_fee_mode != expected_fee_mode and not (
        studio_zero_fee_normalization or wallet_legacy_fee_normalization
    ):
        _raise_verification_error(
            status_code=400,
            code="transaction_fee_mode_mismatch",
            message="Submitted transaction fee model does not match the reviewed transaction.",
            envelope=envelope,
            tx_hash=tx_hash,
            field="fee model",
            expected=expected_fee_mode,
            actual=actual_fee_mode,
        )

    fee_fields = (
        ("gasPrice", envelope.gas_price),
        ("maxFeePerGas", envelope.max_fee_per_gas),
        ("maxPriorityFeePerGas", envelope.max_priority_fee_per_gas),
    )
    for field, expected in fee_fields:
        if (
            (studio_zero_fee_normalization and field in {"maxFeePerGas", "maxPriorityFeePerGas"})
            or (wallet_legacy_fee_normalization and field in {"maxFeePerGas", "maxPriorityFeePerGas"})
        ):
            continue
        if expected is not None:
            actual = transaction.get(field)
            try:
                fee_matches = actual is not None and _rpc_integer(actual) == int(expected)
            except (TypeError, ValueError):
                _raise_verification_error(
                    status_code=400,
                    code="malformed_transaction_fee",
                    message=f"Submitted transaction {field} is malformed.",
                    envelope=envelope,
                    tx_hash=tx_hash,
                    field=field,
                )
            if not fee_matches:
                _raise_verification_error(
                    status_code=400,
                    code="transaction_field_mismatch",
                    message=f"Submitted transaction {field} does not match the reviewed transaction.",
                    envelope=envelope,
                    tx_hash=tx_hash,
                    field=field,
                )
    return tx_hash


def mark_prepared_transaction_confirmed(
    *,
    db: Session,
    envelope: PreparedTransaction,
    tx_hash: str,
    consensus_tx_id: str | None = None,
) -> None:
    envelope.tx_hash = tx_hash
    envelope.consensus_tx_id = consensus_tx_id
    envelope.status = "confirmed"
    envelope.evm_status = "SUCCESS"
    envelope.consensus_status = "CONSENSUS_PENDING" if consensus_tx_id else "UNINITIALIZED"
    envelope.lifecycle_status = "CONSENSUS_PENDING" if consensus_tx_id else "CHAIN_ACCEPTED"
    envelope.final = False
    envelope.terminal = not bool(consensus_tx_id)
    envelope.confirmed_at = datetime.utcnow()
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail={
                "code": "transaction_hash_already_consumed",
                "message": "Submitted transaction hash has already been consumed.",
                "tx_hash": tx_hash,
                "prepared_transaction_id": envelope.id,
                "intent_hash": envelope.intent_hash,
            },
        ) from exc


def mark_prepared_transaction_broadcast(
    *,
    db: Session,
    envelope: PreparedTransaction,
    tx_hash: str,
) -> None:
    envelope.tx_hash = tx_hash
    envelope.evm_status = "BROADCAST"
    envelope.lifecycle_status = "BROADCAST"
    db.commit()
