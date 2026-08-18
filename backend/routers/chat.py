from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field, model_validator
from sqlalchemy.orm import Session
from web3 import Web3
import json
import os
import re
from datetime import datetime, timedelta
from typing import Any, ClassVar

from ..auth import get_current_user
from ..contract_artifacts import (
    ContractSourceIntegrityError,
    StaleContractReviewError,
    artifact_metadata,
    verify_reviewed_source,
)
from ..database import get_db
from ..genlayer_client import (
    EXECUTION_STATUS_FINISHED_WITH_ERROR,
    EXECUTION_STATUS_FINISHED_WITH_RETURN,
    EXECUTION_STATUS_NOT_VOTED,
    EXECUTION_STATUS_UNKNOWN,
    get_balance,
    get_client,
)
from ..intent_parser import merge_notary_spec_context, parse_intent
from ..logs_store import logs_store
from ..models import (
    ChatHistory,
    NotaryClaim,
    NotaryRegistry,
    PreparedTransaction,
    User,
    WorkflowDeployment,
)
from ..network_config import normalize_network
from ..rate_limit import limiter
from ..safety import normalize_intent, validate_intent
from ..services.contract_generation_service import ContractGenerationService
from ..services.contract_review_service import ContractReviewService
from ..services.notary_service import (
    NOTARY_CONTRACT_NAME,
    NOTARY_SOURCE_ORIGIN,
    NotaryValidationError,
    generate_notary_contract_code,
    notary_constructor_args,
    serialize_notary_record,
    validate_notary_action,
    validate_notary_spec,
)
from ..services.product_capabilities import (
    APPEAL_SUBMISSION,
    disabled_workflow_capability,
)
from ..services.workflow_service import (
    WorkflowValidationError,
    generate_workflow_contract_code,
    get_workflow_action_value_wei,
    get_workflow_constructor_args,
    get_workflow_contract_name,
    get_workflow_deploy_value_wei,
    get_workflow_participant_addresses,
    is_workflow_action_authorized,
    validate_workflow_action,
    validate_workflow_config,
)
from ..simulator import simulate_intent
from ..transaction_intent import (
    create_prepared_transaction,
    load_prepared_transaction,
    mark_prepared_transaction_broadcast,
    mark_prepared_transaction_confirmed,
    prepared_intent,
    prepared_transaction_response,
    verify_submitted_transaction,
)

router = APIRouter(prefix="/chat", tags=["chat"])

HELP_MESSAGE = """Available commands:

help - Show this command list.
check balance - Check the connected wallet balance on the selected GenLayer network.
send tokens - Prepare a wallet-side GEN transfer. Example: Send 10 GEN to 0x...
deploy contract - Start contract deployment. Upload a .py GenLayer Intelligent Contract file when prompted.
new chat - Start a clean chat session from the left sidebar.
switch network - Use the network selector to switch between Studionet and Bradbury.
debug tx - Debug a transaction. Example: debug tx 0x...
appeal tx - Check read-only appealability metadata. Appeal preparation and submission are currently unavailable.
notarize claim - Prepare a public-evidence AI Notary blueprint. Example: Notarize whether example shipped using https://example.com/release"""

contract_generation_service = ContractGenerationService()
contract_review_service = ContractReviewService(contract_generation_service.validator)
PHASE9_LIVE_PROOF_ENV = "GENLAYER_PHASE9_LIVE_PROOF"
MAX_REQUEST_PAYLOAD_BYTES = 256 * 1024
MAX_CHAT_MESSAGE_CHARS = 16 * 1024
MAX_CONTRACT_SOURCE_CHARS = 128 * 1024
MAX_HISTORY_PAYLOAD_BYTES = 1024 * 1024
MAX_HISTORY_CHATS = 100
MAX_HISTORY_MESSAGES_PER_CHAT = 200


class BoundedRequestModel(BaseModel):
    max_payload_bytes: ClassVar[int] = MAX_REQUEST_PAYLOAD_BYTES

    @model_validator(mode="after")
    def validate_serialized_size(self):
        serialized = json.dumps(
            self.model_dump(mode="json"),
            separators=(",", ":"),
            ensure_ascii=True,
        ).encode("utf-8")
        if len(serialized) > self.max_payload_bytes:
            raise ValueError(
                f"Request payload exceeds the {self.max_payload_bytes}-byte limit."
            )
        return self


def require_phase9_live_proof() -> None:
    if os.getenv(PHASE9_LIVE_PROOF_ENV) != "1":
        raise HTTPException(status_code=404, detail="Phase 9 live proof harness is not enabled.")


def require_phase9_conditional_config(workflow_config: dict[str, Any]) -> None:
    workflow_type = str(
        workflow_config.get("workflowType")
        or workflow_config.get("workflow_type")
        or ""
    ).strip().lower()
    if workflow_type != "conditional_payment":
        raise HTTPException(status_code=400, detail="Phase 9 proof only supports conditional payment.")

class ChatRequest(BoundedRequestModel):
    message: str = Field(max_length=MAX_CHAT_MESSAGE_CHARS)
    wallet_address: str | None = Field(default=None, max_length=64)
    network: str | None = Field(default=None, max_length=32)
    notary_spec: dict[str, Any] | None = None

class ConfirmRequest(BoundedRequestModel):
    intent: dict
    wallet_address: str | None = None
    signed_transaction: str | None = None
    tx_hash: str | None = None  # Transaction hash from wallet-side broadcast
    network: str | None = None
    prepared_transaction_id: str | None = None
    intent_hash: str | None = None


class TxParamsResponse(BaseModel):
    chain_id: int
    gas_price: str  # In hex
    nonce: int
    gas_limit: int
    rpc_url: str


class DeployTxRequest(BoundedRequestModel):
    address: str
    code: str = Field(min_length=1, max_length=MAX_CONTRACT_SOURCE_CHARS)
    intent: dict[str, Any] | None = None
    constructor_args: list[Any] = Field(default_factory=list, max_length=64)
    constructor_kwargs: dict[str, Any] = Field(default_factory=dict, max_length=64)
    value_wei: str = "0"
    gas_limit: int | None = None
    consensus_max_rotations: int | None = None
    leader_only: bool = False
    network: str | None = None
    source_hash: str | None = None
    source_origin: str = "uploaded"
    py_genlayer_dependency: str | None = None
    generator_version: str | None = None
    validator_version: str | None = None


class DeployTxResponse(BaseModel):
    chain_id: int
    to: str
    data: str
    value: str
    nonce: int
    gas_limit: int
    rpc_url: str
    gas_price: str | None = None
    max_fee_per_gas: str | None = None
    max_priority_fee_per_gas: str | None = None
    prepared_transaction_id: str
    intent_hash: str
    prepared_intent: dict[str, Any]
    expires_at: str
    source_hash: str | None = None
    source_origin: str | None = None
    py_genlayer_dependency: str | None = None
    genlayer_sdk_version: str | None = None
    generator_version: str | None = None
    validator_version: str | None = None
    compiler_version: str | None = None
    artifact_version: int | None = None


class TransferTxRequest(BoundedRequestModel):
    address: str
    recipient: str
    amount_wei: str
    gas_limit: int | None = None
    intent: dict[str, Any] | None = None
    network: str | None = None


class WorkflowDeployTxRequest(BoundedRequestModel):
    address: str
    workflow_config: dict[str, Any]
    intent: dict[str, Any] | None = None
    value_wei: str = "0"
    gas_limit: int | None = None
    consensus_max_rotations: int | None = None
    leader_only: bool = False
    network: str | None = None
    source_hash: str | None = None
    py_genlayer_dependency: str | None = None
    generator_version: str | None = None
    validator_version: str | None = None


class WorkflowDeployTxResponse(DeployTxResponse):
    code: str
    contract_name: str
    constructor_args: list[Any]
    constructor_kwargs: dict[str, Any] = Field(default_factory=dict)
    workflow_config: dict[str, Any]


class WorkflowContractRequest(BoundedRequestModel):
    workflow_config: dict[str, Any]


class WorkflowContractResponse(BaseModel):
    code: str
    contract_name: str
    contract_type: str
    file_name: str
    explanation: str
    workflow_config: dict[str, Any]
    constructor_args: list[Any]
    constructor_kwargs: dict[str, Any] = Field(default_factory=dict)
    validation: dict[str, Any]
    source_hash: str
    source_origin: str
    py_genlayer_dependency: str
    genlayer_sdk_version: str
    generator_version: str
    validator_version: str
    compiler_version: str
    artifact_version: int


class NotaryBlueprintRequest(BoundedRequestModel):
    notary_spec: dict[str, Any]


class NotaryBlueprintResponse(BaseModel):
    code: str
    contract_name: str
    contract_type: str = "ai_notary"
    file_name: str
    explanation: str
    notary_spec: dict[str, Any]
    constructor_args: list[Any]
    constructor_kwargs: dict[str, Any] = Field(default_factory=dict)
    validation: dict[str, Any]
    evidence_policy: str
    equivalence_rule: str
    authorization: str
    source_hash: str
    source_origin: str
    py_genlayer_dependency: str
    genlayer_sdk_version: str
    generator_version: str
    validator_version: str
    compiler_version: str
    artifact_version: int


class NotaryDeployTxRequest(BoundedRequestModel):
    address: str
    notary_spec: dict[str, Any]
    intent: dict[str, Any] | None = None
    gas_limit: int | None = None
    consensus_max_rotations: int | None = None
    leader_only: bool = False
    network: str | None = None
    source_hash: str
    py_genlayer_dependency: str
    generator_version: str
    validator_version: str


class NotaryDeployTxResponse(DeployTxResponse):
    code: str
    contract_name: str
    constructor_args: list[Any]
    constructor_kwargs: dict[str, Any] = Field(default_factory=dict)
    notary_spec: dict[str, Any]


class NotaryCallTxRequest(BoundedRequestModel):
    address: str
    contract_address: str
    notary_action: str
    claim_id: str
    notary_spec: dict[str, Any] | None = None
    intent: dict[str, Any] | None = None
    gas_limit: int | None = None
    consensus_max_rotations: int | None = None
    leader_only: bool = False
    network: str | None = None


class NotaryRecordResponse(BaseModel):
    contract_address: str
    network: str
    record: dict[str, Any]
    transaction_hash_variant: str = "latest-final"


class ContractCallTxRequest(BoundedRequestModel):
    address: str
    contract_address: str
    method: str
    intent: dict[str, Any] | None = None
    args: list[Any] = Field(default_factory=list, max_length=64)
    kwargs: dict[str, Any] = Field(default_factory=dict, max_length=64)
    value_wei: str = "0"
    gas_limit: int | None = None
    consensus_max_rotations: int | None = None
    leader_only: bool = False
    network: str | None = None
    workflow_type: str | None = None


class AppealTxRequest(BoundedRequestModel):
    address: str
    consensus_tx_id: str
    bond_wei: str | None = None
    gas_limit: int | None = None
    intent: dict[str, Any] | None = None
    network: str | None = None


class AppealTxResponse(DeployTxResponse):
    consensus_tx_id: str
    consensus_status: str
    appeal_window_open: bool
    appeal_window_status: str
    minimum_appeal_bond_wei: str
    appeal_bond_wei: str
    appeal_round: int | None = None
    appeal_status_code: int | None = None
    appeal_window_source: str | None = None
    minimum_appeal_bond_source: str | None = None


class WorkflowStateResponse(BaseModel):
    workflow_type: str
    contract_address: str
    network: str
    state: dict[str, Any]
    transaction_hash_variant: str = "latest-final"


class ConsensusStatusRequest(BoundedRequestModel):
    consensus_tx_id: str
    network: str | None = None
    workflow_intent: dict[str, Any] | None = None
    prepared_transaction_id: str | None = None
    intent_hash: str | None = None


class ContractValidationRequest(BoundedRequestModel):
    code: str = Field(min_length=1, max_length=MAX_CONTRACT_SOURCE_CHARS)
    file_name: str | None = Field(default=None, max_length=255)


class GenerateContractRequest(BoundedRequestModel):
    intent: dict
    network: str | None = None


class ContractValidationResponse(BaseModel):
    valid: bool
    message: str
    errors: list[str]
    warnings: list[str]
    contract_names: list[str] = Field(default_factory=list)
    source_hash: str | None = None
    source_origin: str | None = None
    py_genlayer_dependency: str | None = None
    genlayer_sdk_version: str | None = None
    generator_version: str | None = None
    validator_version: str | None = None
    compiler_version: str | None = None
    artifact_version: int | None = None


class ChatHistoryPayload(BoundedRequestModel):
    max_payload_bytes: ClassVar[int] = MAX_HISTORY_PAYLOAD_BYTES
    chats: list[dict[str, Any]] = Field(default_factory=list, max_length=MAX_HISTORY_CHATS)
    currentChatId: str | None = Field(default=None, max_length=128)

    @model_validator(mode="after")
    def validate_history_shape(self):
        for chat in self.chats:
            messages = chat.get("messages")
            if messages is None:
                continue
            if not isinstance(messages, list):
                raise ValueError("Each chat messages field must be a list.")
            if len(messages) > MAX_HISTORY_MESSAGES_PER_CHAT:
                raise ValueError(
                    f"Each chat may contain at most {MAX_HISTORY_MESSAGES_PER_CHAT} messages."
                )
        return self


def persist_workflow_deployment(
    db: Session,
    user: User | None,
    intent: dict[str, Any],
    network: str,
    tx_hash: str,
    consensus_tx_id: str | None,
    contract_address: str | None,
) -> None:
    workflow_config = intent.get("workflow_config")
    if not user or not isinstance(workflow_config, dict):
        return

    try:
        validated_config = validate_workflow_config(workflow_config, user.connected_wallet_address)
    except WorkflowValidationError:
        return

    deployment = WorkflowDeployment(
        user_id=user.id,
        workflow_type=validated_config["workflowType"],
        network=network,
        config_json=json.dumps(validated_config, separators=(",", ":")),
        contract_address=contract_address,
        deploy_tx_hash=tx_hash,
        consensus_tx_id=consensus_tx_id,
        status="submitted",
        lifecycle_status="CONSENSUS_PENDING" if consensus_tx_id else "CHAIN_ACCEPTED",
        evm_status="SUCCESS",
        consensus_status="CONSENSUS_PENDING" if consensus_tx_id else "UNINITIALIZED",
    )
    db.add(deployment)
    db.commit()


def update_workflow_consensus_state(
    db: Session,
    user: User | None,
    consensus_tx_id: str,
    workflow_intent: dict[str, Any] | None,
    consensus_status: str,
    execution_status: str,
    contract_address: str | None,
    network: str | None = None,
    diagnostics: dict[str, Any] | None = None,
) -> None:
    if not user or not isinstance(workflow_intent, dict):
        return

    if workflow_intent.get("action") == "deploy_contract":
        deployment = (
            db.query(WorkflowDeployment)
            .filter(
                WorkflowDeployment.user_id == user.id,
                WorkflowDeployment.consensus_tx_id == consensus_tx_id,
            )
            .order_by(WorkflowDeployment.created_at.desc())
            .first()
        )
        if not deployment:
            return
        _update_lifecycle_record(
            deployment,
            consensus_status=consensus_status,
            execution_status=execution_status,
            final=consensus_status == "FINALIZED",
            terminal=consensus_status in {"FINALIZED", "UNDETERMINED", "CANCELED", "VALIDATORS_TIMEOUT", "LEADER_TIMEOUT"},
            appealable=consensus_status in {"ACCEPTED", "UNDETERMINED"},
            diagnostics=diagnostics,
        )
        if consensus_status == "FINALIZED":
            if execution_status == EXECUTION_STATUS_FINISHED_WITH_RETURN:
                if contract_address:
                    deployment.contract_address = Web3.to_checksum_address(contract_address)
                deployment.status = "active" if deployment.contract_address else "finalized"
            else:
                deployment.contract_address = None
                deployment.status = (
                    "execution_failed"
                    if execution_status == EXECUTION_STATUS_FINISHED_WITH_ERROR
                    else "finalized"
                )
        else:
            if consensus_status in {"UNDETERMINED", "CANCELED", "VALIDATORS_TIMEOUT", "LEADER_TIMEOUT"}:
                deployment.contract_address = None
            deployment.status = consensus_status.lower()
        db.commit()
        return

    if (
        workflow_intent.get("action") == "contract_call"
        and consensus_status == "FINALIZED"
        and execution_status == EXECUTION_STATUS_FINISHED_WITH_RETURN
    ):
        persist_workflow_action(
            db=db,
            user=user,
            intent=workflow_intent,
            tx_hash=str(workflow_intent.get("tx_hash") or consensus_tx_id),
            network=network,
        )


def _update_lifecycle_record(
    record: Any,
    *,
    consensus_status: str,
    execution_status: str,
    final: bool,
    terminal: bool,
    appealable: bool,
    diagnostics: dict[str, Any] | None,
) -> None:
    record.consensus_status = consensus_status
    record.execution_status = execution_status
    record.final = final
    record.terminal = terminal
    record.appealable = appealable
    record.lifecycle_status = "FINALIZED" if final else (
        consensus_status if terminal else "CONSENSUS_PENDING"
    )
    if diagnostics:
        record.protocol_result = diagnostics.get("protocol_result")
        record.num_rounds = diagnostics.get("num_rounds")
        record.validator_count = diagnostics.get("validator_count")
        record.vote_count = diagnostics.get("vote_count")
        record.zero_round_no_majority = bool(diagnostics.get("zero_round_no_majority"))
        record.diagnostic_json = json.dumps(
            {
                key: value
                for key, value in diagnostics.items()
                if key != "transaction"
            },
            separators=(",", ":"),
            default=str,
        )
    record.last_polled_at = datetime.utcnow()


def update_prepared_consensus_state(
    db: Session,
    envelope: PreparedTransaction,
    status_result: dict[str, Any],
    execution_status: str,
    diagnostics: dict[str, Any],
) -> None:
    _update_lifecycle_record(
        envelope,
        consensus_status=str(status_result.get("status") or "UNKNOWN"),
        execution_status=execution_status,
        final=bool(status_result.get("final")),
        terminal=bool(status_result.get("terminal")),
        appealable=bool(status_result.get("appealable")),
        diagnostics=diagnostics,
    )
    envelope.consensus_tx_id = envelope.consensus_tx_id or status_result.get("consensusTxId")
    if envelope.tx_hash:
        envelope.evm_status = "SUCCESS"
    db.commit()


def persist_workflow_action(
    db: Session,
    user: User | None,
    intent: dict[str, Any],
    tx_hash: str,
    network: str | None = None,
) -> None:
    if not user:
        return
    contract_address = intent.get("contract_address")
    if not isinstance(contract_address, str):
        return
    deployment_query = db.query(WorkflowDeployment).filter(
        WorkflowDeployment.contract_address == Web3.to_checksum_address(contract_address),
    )
    if network:
        deployment_query = deployment_query.filter(WorkflowDeployment.network == network)
    deployment = deployment_query.order_by(WorkflowDeployment.created_at.desc()).first()
    if not deployment:
        return
    config = json.loads(deployment.config_json)
    owner_address = deployment.user.connected_wallet_address
    method = str(intent.get("method") or "")
    if not is_workflow_action_authorized(
        config,
        owner_address,
        user.connected_wallet_address,
        method,
    ):
        return
    deployment.last_action = str(intent.get("method") or "")
    deployment.last_action_tx_hash = tx_hash
    db.commit()


def serialize_workflow_state(state: Any) -> dict[str, Any]:
    if not isinstance(state, dict):
        raise WorkflowValidationError("Workflow get_state must return an object.")
    return {
        str(key): str(value) if str(key).endswith("_wei") and isinstance(value, int) else value
        for key, value in state.items()
    }


def find_workflow_deployment(
    db: Session,
    contract_address: str,
    network: str,
) -> WorkflowDeployment | None:
    return (
        db.query(WorkflowDeployment)
        .filter(
            WorkflowDeployment.contract_address == contract_address,
            WorkflowDeployment.network == network,
        )
        .order_by(WorkflowDeployment.created_at.desc())
        .first()
    )


def authorize_workflow_participant(
    deployment: WorkflowDeployment,
    actor_address: str,
) -> dict[str, Any]:
    config = json.loads(deployment.config_json)
    owner_address = deployment.user.connected_wallet_address
    participants = get_workflow_participant_addresses(config, owner_address)
    if Web3.to_checksum_address(actor_address) not in participants:
        raise HTTPException(status_code=403, detail="Wallet is not a participant in this workflow.")
    return config


def find_notary_registry(
    db: Session,
    contract_address: str,
    network: str,
) -> NotaryRegistry | None:
    return (
        db.query(NotaryRegistry)
        .filter(
            NotaryRegistry.contract_address == contract_address,
            NotaryRegistry.network == network,
        )
        .order_by(NotaryRegistry.created_at.desc())
        .first()
    )


def find_notary_claim(
    db: Session,
    registry: NotaryRegistry,
    claim_id: str,
) -> NotaryClaim | None:
    return (
        db.query(NotaryClaim)
        .filter(
            NotaryClaim.registry_id == registry.id,
            NotaryClaim.claim_id == claim_id,
        )
        .first()
    )


def persist_notary_registry(
    db: Session,
    user: User,
    intent: dict[str, Any],
    network: str,
    tx_hash: str,
    consensus_tx_id: str | None,
) -> None:
    if intent.get("notary_operation") != "deploy_registry":
        return
    source_hash = str(intent.get("source_hash") or "")
    if not source_hash:
        return
    existing = (
        db.query(NotaryRegistry)
        .filter(
            NotaryRegistry.user_id == user.id,
            NotaryRegistry.network == network,
            NotaryRegistry.consensus_tx_id == consensus_tx_id,
        )
        .first()
    )
    if existing:
        return
    db.add(
        NotaryRegistry(
            user_id=user.id,
            network=network,
            deploy_tx_hash=tx_hash,
            consensus_tx_id=consensus_tx_id,
            status="submitted",
            source_hash=source_hash,
        )
    )
    db.commit()


def persist_notary_call(
    db: Session,
    user: User,
    intent: dict[str, Any],
    network: str,
    tx_hash: str,
    consensus_tx_id: str | None,
) -> None:
    operation = str(intent.get("notary_operation") or "")
    if operation not in {"submit_claim", "evaluate_claim"}:
        return
    contract_address = Web3.to_checksum_address(str(intent.get("contract_address") or ""))
    registry = find_notary_registry(db, contract_address, network)
    if not registry:
        return
    claim_id = str(intent.get("claim_id") or "")
    claim = find_notary_claim(db, registry, claim_id)
    if operation == "submit_claim":
        spec = intent.get("notary_spec")
        if not isinstance(spec, dict):
            return
        if not claim:
            claim = NotaryClaim(
                registry_id=registry.id,
                user_id=user.id,
                claim_id=claim_id,
                spec_json=json.dumps(spec, separators=(",", ":")),
            )
            db.add(claim)
        claim.submit_tx_hash = tx_hash
        claim.submit_consensus_tx_id = consensus_tx_id
        claim.status = "submitted"
        claim.verdict = "PENDING"
    elif claim and claim.user_id == user.id:
        claim.evaluate_tx_hash = tx_hash
        claim.evaluate_consensus_tx_id = consensus_tx_id
        claim.status = "evaluating"
    db.commit()


def update_notary_consensus_state(
    db: Session,
    user: User,
    consensus_tx_id: str,
    intent: dict[str, Any] | None,
    consensus_status: str,
    execution_status: str,
    contract_address: str | None,
    network: str,
) -> None:
    if not isinstance(intent, dict):
        return
    operation = str(intent.get("notary_operation") or "")
    if operation == "deploy_registry":
        registry = (
            db.query(NotaryRegistry)
            .filter(
                NotaryRegistry.user_id == user.id,
                NotaryRegistry.consensus_tx_id == consensus_tx_id,
            )
            .first()
        )
        if not registry:
            return
        if consensus_status == "FINALIZED" and execution_status == EXECUTION_STATUS_FINISHED_WITH_RETURN:
            if contract_address:
                registry.contract_address = Web3.to_checksum_address(contract_address)
            registry.status = "active" if registry.contract_address else "finalized"
        elif consensus_status == "FINALIZED":
            registry.contract_address = None
            registry.status = (
                "execution_failed"
                if execution_status == EXECUTION_STATUS_FINISHED_WITH_ERROR
                else "finalized"
            )
        else:
            registry.status = consensus_status.lower()
        db.commit()
        return
    if operation not in {"submit_claim", "evaluate_claim"}:
        return
    checksum_contract = Web3.to_checksum_address(str(intent.get("contract_address") or ""))
    registry = find_notary_registry(db, checksum_contract, network)
    if not registry:
        return
    claim = find_notary_claim(db, registry, str(intent.get("claim_id") or ""))
    if not claim or claim.user_id != user.id:
        return
    if consensus_status == "FINALIZED" and execution_status == EXECUTION_STATUS_FINISHED_WITH_RETURN:
        claim.status = "pending" if operation == "submit_claim" else "evaluated"
    elif consensus_status == "FINALIZED":
        claim.status = (
            "execution_failed"
            if execution_status == EXECUTION_STATUS_FINISHED_WITH_ERROR
            else "finalized"
        )
    else:
        claim.status = consensus_status.lower()
    db.commit()


def resolve_network_or_400(network: str | None) -> str:
    try:
        return normalize_network(network)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


def require_authenticated_wallet(current_user: User, claimed_address: str | None) -> str:
    wallet_address = Web3.to_checksum_address(current_user.connected_wallet_address)
    if claimed_address is not None:
        try:
            claimed_wallet = Web3.to_checksum_address(claimed_address)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail="Invalid wallet address") from exc
        if claimed_wallet != wallet_address:
            raise HTTPException(
                status_code=403,
                detail="Authenticated wallet does not match the requested transaction wallet.",
            )
    return wallet_address


def build_transfer_intent(
    request: TransferTxRequest,
    recipient: str,
    value_wei: int,
) -> dict[str, Any]:
    intent = normalize_intent(
        request.intent
        or {
            "action": "transfer",
            "recipient": recipient,
            "amount": float(Web3.from_wei(value_wei, "ether")),
            "token": "GEN",
        }
    )
    intent.update(
        {
            "action": "transfer",
            "recipient": recipient,
            "amount_wei": str(value_wei),
            "gas_limit": request.gas_limit or 21000,
        }
    )
    return intent


def build_deploy_intent(
    request: DeployTxRequest,
    value_wei: int,
) -> dict[str, Any]:
    intent = normalize_intent(
        request.intent
        or {
            "action": "deploy_contract",
            "code": request.code,
            "constructor_args": request.constructor_args,
            "constructor_kwargs": request.constructor_kwargs,
            "deploy_value": float(Web3.from_wei(value_wei, "ether")),
            "gas_limit": request.gas_limit,
            "consensus_max_rotations": request.consensus_max_rotations,
            "leader_only": request.leader_only,
            "source_hash": request.source_hash,
            "source_origin": request.source_origin,
            "py_genlayer_dependency": request.py_genlayer_dependency,
            "generator_version": request.generator_version,
            "validator_version": request.validator_version,
        }
    )
    intent.update(
        {
            "action": "deploy_contract",
            "code": request.code,
            "constructor_args": request.constructor_args,
            "constructor_kwargs": request.constructor_kwargs,
            "deploy_value_wei": str(value_wei),
            "gas_limit": request.gas_limit,
            "consensus_max_rotations": request.consensus_max_rotations,
            "leader_only": request.leader_only,
        }
    )
    return intent


def build_workflow_deploy_intent(
    request: WorkflowDeployTxRequest,
    validated_config: dict[str, Any],
    code: str,
    contract_name: str,
    constructor_args: list[Any],
    value_wei: int,
) -> dict[str, Any]:
    intent = normalize_intent(
        {
            **(request.intent or {}),
            "action": "deploy_contract",
            "code": code,
            "contract_name": contract_name,
            "contract_type": validated_config["workflowType"],
            "constructor_args": constructor_args,
            "constructor_kwargs": {},
            "deploy_value": float(Web3.from_wei(value_wei, "ether")),
            "gas_limit": request.gas_limit,
            "consensus_max_rotations": request.consensus_max_rotations,
            "leader_only": request.leader_only,
            "workflow_config": validated_config,
            "source_hash": request.source_hash,
            "source_origin": "workflow",
            "py_genlayer_dependency": request.py_genlayer_dependency,
            "generator_version": request.generator_version,
            "validator_version": request.validator_version,
        }
    )
    intent["deploy_value_wei"] = str(value_wei)
    return intent


def build_notary_deploy_intent(
    request: NotaryDeployTxRequest,
    notary_spec: dict[str, Any],
    code: str,
    constructor_args: list[Any],
) -> dict[str, Any]:
    intent = normalize_intent(
        {
            **(request.intent or {}),
            "action": "deploy_contract",
            "code": code,
            "contract_name": NOTARY_CONTRACT_NAME,
            "contract_type": "ai_notary",
            "constructor_args": constructor_args,
            "constructor_kwargs": {},
            "deploy_value": 0,
            "gas_limit": request.gas_limit,
            "consensus_max_rotations": request.consensus_max_rotations,
            "leader_only": request.leader_only,
            "source_hash": request.source_hash,
            "source_origin": NOTARY_SOURCE_ORIGIN,
            "py_genlayer_dependency": request.py_genlayer_dependency,
            "generator_version": request.generator_version,
            "validator_version": request.validator_version,
            "notary_operation": "deploy_registry",
            "notary_spec": notary_spec,
            "claim_id": notary_spec["claim_id"],
        }
    )
    intent["deploy_value_wei"] = "0"
    return intent


def build_notary_call_intent(
    request: NotaryCallTxRequest,
    contract_address: str,
    method: str,
    args: list[Any],
    notary_spec: dict[str, Any] | None,
) -> dict[str, Any]:
    intent = normalize_intent(
        {
            **(request.intent or {}),
            "action": "contract_call",
            "contract_address": contract_address,
            "method": method,
            "args": args,
            "kwargs": {},
            "notary_operation": method,
            "notary_spec": notary_spec,
            "claim_id": request.claim_id,
        }
    )
    intent.update(
        {
            "value_wei": "0",
            "gas_limit": request.gas_limit,
            "consensus_max_rotations": request.consensus_max_rotations,
            "leader_only": request.leader_only,
        }
    )
    return intent


def build_contract_call_intent(
    request: ContractCallTxRequest,
    contract_address: str,
    method: str,
    value_wei: int,
) -> dict[str, Any]:
    intent = normalize_intent(
        {
            **(request.intent or {}),
            "action": "contract_call",
            "contract_address": contract_address,
            "method": method,
            "args": request.args,
            "kwargs": request.kwargs,
            "workflow_type": request.workflow_type,
        }
    )
    intent.update(
        {
            "value_wei": str(value_wei),
            "gas_limit": request.gas_limit,
            "consensus_max_rotations": request.consensus_max_rotations,
            "leader_only": request.leader_only,
        }
    )
    return intent


def build_appeal_intent(
    request: AppealTxRequest,
    requirements: dict[str, Any],
    bond_wei: int,
) -> dict[str, Any]:
    intent = normalize_intent(
        {
            **(request.intent or {}),
            'action': 'appeal_transaction',
            'consensus_tx_id': request.consensus_tx_id,
        }
    )
    intent.update(
        {
            'action': 'appeal_transaction',
            'consensus_tx_id': requirements['consensus_tx_id'],
            'consensus_status': requirements['consensus_status'],
            'appeal_window_open': requirements['appeal_window_open'],
            'appeal_window_status': requirements['appeal_window_status'],
            'minimum_appeal_bond_wei': str(requirements['minimum_appeal_bond_wei']),
            'appeal_bond_wei': str(bond_wei),
            'appeal_round': requirements.get('appeal_round'),
            'appeal_status_code': requirements.get('appeal_status_code'),
            'appeal_window_source': requirements.get('appeal_window_source'),
            'minimum_appeal_bond_source': requirements.get('minimum_appeal_bond_source'),
            'gas_limit': request.gas_limit,
        }
    )
    return intent


def is_deploy_contract_request(message: str) -> bool:
    normalized = " ".join(message.lower().strip().split())
    # Match explicit commands first
    if normalized.startswith((
        "deploy contract",
        "deploy a contract",
        "deploy this contract",
        "deploy an intelligent contract",
        "upload contract",
        "upload a contract",
        "submit contract",
        "submit a contract",
    )):
        return True

    # Also accept natural language variants like "deploy this contract" or
    # "please deploy contract" by checking that both keywords are present.
    if "deploy" in normalized and "contract" in normalized:
        return True

    return False


def extract_code_from_message(message: str) -> str:
    """Try to extract Python contract code from a chat message.

    - Prefer fenced code blocks (```python or ```),
    - Otherwise, take the portion after the first blank line (typical "Deploy this contract:\n\n<code>").
    """
    import re
    if not message:
        return ""

    # Fenced code block
    m = re.search(r'```(?:python\n)?(.*?)```', message, re.S | re.I)
    if m:
        return m.group(1).strip()

    # If message contains a double-newline separator, assume code follows
    parts = message.split('\n\n', 1)
    if len(parts) > 1 and parts[1].strip():
        return parts[1].strip()

    return ""


def extract_deploy_contract_code(message: str) -> str:
    if "\n" not in message:
        return ""
    code = message.split("\n", 1)[1].strip()
    fenced_match = re.fullmatch(r"```(?:python)?\s*(.*?)\s*```", code, flags=re.IGNORECASE | re.DOTALL)
    return fenced_match.group(1).strip() if fenced_match else code


def is_help_request(message: str) -> bool:
    normalized = " ".join(message.lower().strip().split())
    return normalized in {"help", "/help", "?", "commands", "show commands", "what can you do"}


def is_generate_contract_request(message: str) -> bool:
    normalized = " ".join(message.lower().strip().split())
    generation_verbs = ("create", "generate", "build", "write", "make", "draft")
    explicit_generation = normalized.startswith((
        "/generate-contract",
        "generate contract",
        "generate a contract",
        "generate an intelligent contract",
    ))
    natural_generation = any(
        normalized.startswith(f"{verb} ") and "contract" in normalized
        for verb in generation_verbs
    )
    return explicit_generation or natural_generation


def is_contract_review_request(message: str) -> bool:
    normalized = " ".join(message.lower().strip().split())
    return normalized.startswith("/contract-review")


def parse_generate_contract_request(message: str) -> tuple[str, bool]:
    stripped = message.strip()
    advanced = stripped.lower().startswith("/generate-contract advanced")
    for prefix in ("/generate-contract advanced", "/generate-contract"):
        if stripped.lower().startswith(prefix):
            return stripped[len(prefix):].strip(), advanced
    return stripped, advanced


@router.get("/history", response_model=ChatHistoryPayload)
def get_chat_history(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ChatHistoryPayload:
    history = db.query(ChatHistory).filter(ChatHistory.user_id == current_user.id).first()
    if not history:
        return ChatHistoryPayload()

    try:
        payload = json.loads(history.payload)
    except json.JSONDecodeError:
        return ChatHistoryPayload()

    return ChatHistoryPayload(
        chats=payload.get("chats") if isinstance(payload.get("chats"), list) else [],
        currentChatId=payload.get("currentChatId") if isinstance(payload.get("currentChatId"), str) else None,
    )


@router.put("/history", response_model=ChatHistoryPayload)
def save_chat_history(
    payload: ChatHistoryPayload,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ChatHistoryPayload:
    history = db.query(ChatHistory).filter(ChatHistory.user_id == current_user.id).first()
    serialized_payload = json.dumps(payload.model_dump(), separators=(",", ":"))

    if history:
        history.payload = serialized_payload
    else:
        history = ChatHistory(user_id=current_user.id, payload=serialized_payload)
        db.add(history)

    db.commit()
    return payload


@router.get("/workflows")
def get_workflows(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    actor_address = Web3.to_checksum_address(current_user.connected_wallet_address)
    deployments = (
        db.query(WorkflowDeployment)
        .order_by(WorkflowDeployment.updated_at.desc())
        .all()
    )
    visible_deployments = []
    for deployment in deployments:
        try:
            config = json.loads(deployment.config_json)
            owner_address = deployment.user.connected_wallet_address
            if actor_address in get_workflow_participant_addresses(config, owner_address):
                visible_deployments.append(deployment)
        except (json.JSONDecodeError, WorkflowValidationError):
            continue
    return {
        "workflows": [
            {
                "id": deployment.id,
                "workflowType": deployment.workflow_type,
                "network": deployment.network,
                "config": json.loads(deployment.config_json),
                "contractAddress": deployment.contract_address,
                "deployTxHash": deployment.deploy_tx_hash,
                "consensusTxId": deployment.consensus_tx_id,
                "status": deployment.status,
                "lastAction": deployment.last_action,
                "lastActionTxHash": deployment.last_action_tx_hash,
                "createdAt": deployment.created_at.isoformat() if deployment.created_at else None,
                "updatedAt": deployment.updated_at.isoformat() if deployment.updated_at else None,
            }
            for deployment in visible_deployments
        ]
    }


@router.get("/workflows/{contract_address}/state", response_model=WorkflowStateResponse)
async def get_workflow_state(
    contract_address: str,
    network: str | None = Query(default=None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> WorkflowStateResponse:
    try:
        resolved_network = resolve_network_or_400(network)
        checksum_contract = Web3.to_checksum_address(contract_address)
        actor_address = Web3.to_checksum_address(current_user.connected_wallet_address)
        deployment = find_workflow_deployment(db, checksum_contract, resolved_network)
        if not deployment:
            raise HTTPException(status_code=404, detail="Workflow deployment was not found.")
        config = authorize_workflow_participant(deployment, actor_address)
        client = get_client(network=resolved_network)
        state = serialize_workflow_state(
            await client.read_contract(
                caller_address=actor_address,
                contract_address=checksum_contract,
                method="get_state",
            )
        )
        state_workflow_type = str(state.get("workflow_type") or "")
        if state_workflow_type != config["workflowType"]:
            raise HTTPException(status_code=502, detail="Workflow state type does not match the persisted deployment.")
        return WorkflowStateResponse(
            workflow_type=config["workflowType"],
            contract_address=checksum_contract,
            network=resolved_network,
            state=state,
        )
    except HTTPException:
        raise
    except (ValueError, WorkflowValidationError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        await logs_store.append(
            "ERROR",
            "WORKFLOW_STATE_READ_FAILED",
            "Failed to read finalized workflow state.",
            {"contract": contract_address, "network": network, "error": str(exc)},
        )
        raise HTTPException(status_code=502, detail=f"Failed to read finalized workflow state: {str(exc)}") from exc


@router.get("/notary-registries")
def get_notary_registries(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    registries = (
        db.query(NotaryRegistry)
        .filter(NotaryRegistry.user_id == current_user.id)
        .order_by(NotaryRegistry.updated_at.desc())
        .all()
    )
    return {
        "registries": [
            {
                "id": registry.id,
                "network": registry.network,
                "contractAddress": registry.contract_address,
                "deployTxHash": registry.deploy_tx_hash,
                "consensusTxId": registry.consensus_tx_id,
                "status": registry.status,
                "sourceHash": registry.source_hash,
                "claims": [
                    {
                        "claimId": claim.claim_id,
                        "status": claim.status,
                        "verdict": claim.verdict,
                        "claimant": claim.user.connected_wallet_address,
                    }
                    for claim in registry.claims
                ],
            }
            for registry in registries
        ]
    }


@router.get(
    "/notary-registries/{contract_address}/claims/{claim_id}",
    response_model=NotaryRecordResponse,
)
async def get_notary_record(
    contract_address: str,
    claim_id: str,
    network: str | None = Query(default=None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> NotaryRecordResponse:
    try:
        resolved_network = resolve_network_or_400(network)
        checksum_contract = Web3.to_checksum_address(contract_address)
        registry = find_notary_registry(db, checksum_contract, resolved_network)
        if not registry:
            raise HTTPException(status_code=404, detail="AI Notary registry was not found.")
        claim = find_notary_claim(db, registry, claim_id)
        if not claim:
            raise HTTPException(status_code=404, detail="AI Notary claim reference was not found.")
        if claim.user_id != current_user.id and registry.user_id != current_user.id:
            raise HTTPException(status_code=403, detail="Wallet is not authorized to read this cached claim reference.")
        caller = Web3.to_checksum_address(current_user.connected_wallet_address)
        client = get_client(network=resolved_network)
        record = serialize_notary_record(
            await client.read_contract(
                caller_address=caller,
                contract_address=checksum_contract,
                method="get_claim",
                args=[claim_id],
            )
        )
        if record["claim_id"] != claim_id:
            raise HTTPException(status_code=502, detail="Notary contract returned the wrong claim record.")
        claim.verdict = record["verdict"]
        claim.status = "evaluated" if record["evaluated"] else "pending"
        db.commit()
        return NotaryRecordResponse(
            contract_address=checksum_contract,
            network=resolved_network,
            record=record,
        )
    except HTTPException:
        raise
    except (ValueError, NotaryValidationError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        await logs_store.append(
            "ERROR",
            "NOTARY_RECORD_READ_FAILED",
            "Failed to read finalized AI Notary claim state.",
            {"contract": contract_address, "claimId": claim_id, "error": str(exc)},
        )
        raise HTTPException(status_code=502, detail=f"Failed to read AI Notary claim: {str(exc)}") from exc


@router.post("")
@limiter.limit("10/minute")
async def handle_chat(request: Request, chat_request: ChatRequest):
    network = resolve_network_or_400(chat_request.network)
    await logs_store.append(
        "INFO",
        "CHAT_RECEIVED",
        "User message received.",
        {"message": chat_request.message, "wallet_address": chat_request.wallet_address, "network": network},
    )

    if is_help_request(chat_request.message):
        await logs_store.append("INFO", "HELP_REQUESTED", "Help command shown.")
        return {
            "content": HELP_MESSAGE,
            "intent": {"action": "help"},
            "status": "success",
        }

    if is_contract_review_request(chat_request.message):
        source = chat_request.message[len("/contract-review"):].strip()
        if not source:
            return {
                "content": "Paste a GenLayer Intelligent Contract after /contract-review so I can run automated preflight checks.",
                "intent": {"action": "contract_review"},
                "status": "awaiting_input",
            }
        review = contract_review_service.review(source)
        await logs_store.append(
            "INFO",
            "CONTRACT_REVIEW_COMPLETED",
            "Automated contract preflight completed.",
            {"verdict": review["verdict"], "contractNames": review["structural"]["contractNames"]},
        )
        return {
            "content": f"Automated contract preflight verdict: {review['verdict']}. Review the findings before considering deployment.",
            "intent": {"action": "contract_review", "status": review["verdict"]},
            "contractReview": review,
            "status": "success" if review["deploymentReady"] else "error",
        }

    if is_generate_contract_request(chat_request.message):
        generation_prompt, advanced = parse_generate_contract_request(chat_request.message)
        if not generation_prompt:
            return {
                "content": "Tell me what Intelligent Contract you want to generate. Example: /generate-contract Create an escrow contract that releases funds when both parties approve.",
                "intent": {"action": "generate_contract", "advanced": advanced},
                "status": "awaiting_input",
            }
        result = contract_generation_service.generate(generation_prompt, advanced=advanced)
        if not result["ok"]:
            await logs_store.append("ERROR", "CONTRACT_GENERATION_FAILED", "Contract generation failed validation.", {"errors": result.get("errors", [])})
            capability_code = result.get("capabilityCode")
            return {
                "content": result.get("message") or "Unable to generate a valid GenLayer contract.",
                "intent": {
                    "action": "generate_contract",
                    "logic_description": generation_prompt,
                    "advanced": advanced,
                    **({"capability_code": capability_code} if capability_code else {}),
                },
                "status": "error",
                "validation": {
                    "valid": False,
                    "errors": result.get("errors", []),
                    "warnings": result.get("warnings", []),
                },
                **({"capabilityCode": capability_code} if capability_code else {}),
            }
        await logs_store.append("SUCCESS", "CONTRACT_GENERATED", "Generated contract from natural language.", {"contractType": result["contractType"], "contractName": result["contractName"]})
        return {
            "content": f"Generated {result['contractName']} from your request. Review the code below, then copy, download, or deploy it.",
            "intent": {
                "action": "deploy_contract",
                "contract_name": result["contractName"],
                "contract_type": result["contractType"],
                "code": result["code"],
                "source_file_name": result["fileName"],
                "constructor_args": [],
                "constructor_kwargs": {},
                "constructor_args_text": "[]",
                "constructor_kwargs_text": "{}",
                "deploy_value_text": "0",
                "gas_limit_text": "",
                "consensus_max_rotations_text": "",
                "deploy_value": 0,
                "leader_only": False,
                "logic_description": generation_prompt,
                "source_hash": result["source_hash"],
                "source_origin": result["source_origin"],
                "py_genlayer_dependency": result["py_genlayer_dependency"],
                "genlayer_sdk_version": result["genlayer_sdk_version"],
                "generator_version": result["generator_version"],
                "validator_version": result["validator_version"],
                "compiler_version": result["compiler_version"],
                "artifact_version": result["artifact_version"],
            },
            "status": "awaiting_confirmation",
            "generatedContract": {
                "contractName": result["contractName"],
                "contractType": result["contractType"],
                "explanation": result["explanation"],
                "code": result["code"],
                "fileName": result["fileName"],
                "specification": result["specification"],
                "validation": result["validation"],
                "sourceHash": result["source_hash"],
                "sourceOrigin": result["source_origin"],
                "pyGenlayerDependency": result["py_genlayer_dependency"],
                "genlayerSdkVersion": result["genlayer_sdk_version"],
                "generatorVersion": result["generator_version"],
                "validatorVersion": result["validator_version"],
                "compilerVersion": result["compiler_version"],
                "artifactVersion": result["artifact_version"],
            },
        }

    if chat_request.notary_spec is not None:
        intent = normalize_intent(
            {
                "action": "notarize_claim",
                "claimant_address": chat_request.wallet_address,
                "notary_spec": merge_notary_spec_context(
                    chat_request.notary_spec,
                    chat_request.message,
                ),
            }
        )
    elif is_deploy_contract_request(chat_request.message):
        intent = normalize_intent(
            {
                "action": "deploy_contract",
                "code": extract_code_from_message(chat_request.message),
            }
        )
    else:
        intent = normalize_intent(parse_intent(chat_request.message, chat_request.wallet_address))

    if intent.get("action") == "deploy_contract" and intent.get("code"):
        validation = contract_generation_service.validator.validate(str(intent["code"]))
        if not validation["valid"]:
            await logs_store.append("ERROR", "DEPLOY_CONTRACT_INVALID", "Uploaded contract failed validation.", {"errors": validation["errors"]})
            return {
                "content": validation["message"],
                "intent": intent,
                "status": "error",
                "validation": validation,
            }
            
    # Contextualize intent for the connected user
    if chat_request.wallet_address:
        # If user asks "what's my balance", ensure we use their connected address
        if intent["action"] == "check_balance" and not intent.get("address"):
            intent["address"] = chat_request.wallet_address
        if intent["action"] == "notarize_claim":
            intent["claimant_address"] = chat_request.wallet_address

    if intent["action"] == "notarize_claim":
        raw_spec = intent.get("notary_spec") if isinstance(intent.get("notary_spec"), dict) else {}
        if not chat_request.wallet_address:
            return {
                "content": "Connect the claimant wallet before reviewing an AI Notary blueprint.",
                "intent": intent,
                "notaryBlueprint": raw_spec,
                "status": "awaiting_input",
            }
        try:
            reviewed_spec = validate_notary_spec(raw_spec, chat_request.wallet_address)
        except NotaryValidationError as exc:
            return {
                "content": f"Notary blueprint needs more information: {str(exc)}",
                "intent": intent,
                "notaryBlueprint": raw_spec,
                "status": "awaiting_input",
            }
        intent["notary_spec"] = reviewed_spec.as_dict()
        intent["claimant_address"] = Web3.to_checksum_address(chat_request.wallet_address)
        await logs_store.append(
            "INFO",
            "NOTARY_BLUEPRINT_PARSED",
            "Public-evidence Notary blueprint parsed.",
            {
                "claimId": reviewed_spec.claim_id,
                "sourceCount": len(reviewed_spec.source_urls),
                "network": network,
            },
        )
        return {
            "content": (
                "AI Notary blueprint ready. Review the claim, evidence policy, freshness rule, "
                "and canonical registry source before deploying."
            ),
            "intent": intent,
            "notaryBlueprint": reviewed_spec.as_dict(),
            "status": "awaiting_confirmation",
        }
            
    await logs_store.append("INFO", "INTENT_PARSED", "Intent parsed.", {"intent": intent})

    if intent["action"] == "unknown":
        await logs_store.append("WARN", "INTENT_UNKNOWN", "Unable to parse user intent.")
        return {
            "content": "I couldn't understand that. You can say something like 'Send 10 GEN to alex' or 'Check my balance'.",
            "intent": intent,
        }

    is_safe, error_msg = validate_intent(intent)
    if not is_safe:
        await logs_store.append("ERROR", "SAFETY_BLOCK", "Safety validation failed.", {"reason": error_msg, "intent": intent})
        return {
            "content": f"Safety check failed: {error_msg}",
            "intent": intent,
            "status": "error",
        }

    simulation = simulate_intent(intent)
    await logs_store.append("INFO", "SIMULATION_READY", "Simulation generated.", {"action": intent.get("action")})

    if intent["action"] == "check_balance":
        await logs_store.append("INFO", "AWAIT_READ_CONFIRMATION", "Awaiting approval for read-only balance check.")
        return {
            "content": "I can run a read-only balance lookup. This does not submit a transaction or use gas. Do you want me to proceed?",
            "intent": intent,
            "status": "awaiting_confirmation",
        }

    if intent["action"] == "debug_trace":
        tx_hash = intent.get("tx_hash")
        if not tx_hash:
            return {
                "content": "Please provide a transaction hash to debug. Example: debug tx 0x...",
                "intent": intent,
                "status": "awaiting_input",
            }
        try:
            client = get_client(network=network)
            trace = await client.debug_trace_transaction(tx_hash)
            trace_summary = json.dumps(trace, indent=2, default=str)[:3000]
            await logs_store.append("SUCCESS", "DEBUG_TRACE_SUCCESS", "Debug trace retrieved.", {"txHash": tx_hash})
            return {
                "content": f"Debug trace for `{tx_hash}`:\n\n```json\n{trace_summary}\n```",
                "intent": intent,
                "status": "success",
            }
        except Exception as e:
            await logs_store.append("ERROR", "DEBUG_TRACE_FAILED", "Debug trace failed.", {"error": str(e)})
            return {
                "content": f"Failed to get debug trace: {str(e)}",
                "intent": intent,
                "status": "error",
            }

    if intent["action"] == "appeal_transaction":
        reference = intent.get('consensus_tx_id') or intent.get('tx_hash')
        try:
            client = get_client(network=network)
            requirements = await client.get_appeal_requirements(reference)
            if requirements['consensus_status'] == 'UNINITIALIZED':
                resolved_id = await client.get_consensus_transaction_id(reference)
                if resolved_id:
                    requirements = await client.get_appeal_requirements(resolved_id)

            reviewed_intent = {
                **intent,
                'consensus_tx_id': requirements['consensus_tx_id'],
                'consensus_status': requirements['consensus_status'],
                'appeal_window_open': requirements['appeal_window_open'],
                'appeal_window_status': requirements['appeal_window_status'],
                'minimum_appeal_bond_wei': str(requirements['minimum_appeal_bond_wei']),
                'appeal_bond_wei': str(requirements['minimum_appeal_bond_wei']),
                'appeal_round': requirements.get('appeal_round'),
                'appeal_status_code': requirements.get('appeal_status_code'),
                'appeal_window_source': requirements.get('appeal_window_source'),
                'minimum_appeal_bond_source': requirements.get('minimum_appeal_bond_source'),
            }
            if not requirements['appeal_window_open']:
                await logs_store.append(
                    'INFO',
                    'APPEAL_WINDOW_CLOSED',
                    'Protocol reports that the transaction is not currently appealable.',
                    {
                        'consensusTxId': requirements['consensus_tx_id'],
                        'status': requirements['consensus_status'],
                    },
                )
                return {
                    'content': (
                        f"The protocol reports that the appeal window is closed for "
                        f"{requirements['consensus_tx_id']} in status "
                        f"{requirements['consensus_status']}."
                    ),
                    'intent': reviewed_intent,
                    'status': 'error',
                }

            bond_gen = Web3.from_wei(requirements['minimum_appeal_bond_wei'], 'ether')
            await logs_store.append(
                'INFO',
                'APPEAL_ELIGIBLE_READ_ONLY',
                'Protocol appeal requirements loaded in read-only mode.',
                {
                    'consensusTxId': requirements['consensus_tx_id'],
                    'minimumBondWei': str(requirements['minimum_appeal_bond_wei']),
                },
            )
            return {
                'content': (
                    f"The protocol reports that the appeal window is open for {requirements['consensus_tx_id']}. "
                    f"The current minimum bond is {bond_gen} GEN "
                    f"({requirements['minimum_appeal_bond_wei']} wei). "
                    f"{APPEAL_SUBMISSION.message}"
                ),
                'intent': reviewed_intent,
                'status': 'unavailable',
            }
        except Exception as exc:
            await logs_store.append(
                'ERROR',
                'APPEAL_READINESS_FAILED',
                'Failed to read protocol appeal requirements.',
                {'reference': reference, 'error': str(exc)},
            )
            return {
                'content': f'Unable to verify appeal readiness: {str(exc)}',
                'intent': intent,
                'status': 'error',
            }

    if intent["action"] == "deploy_contract":
        if not intent.get("code"):
            return {
                "content": "Please upload a .py GenLayer Intelligent Contract file for deployment. I will validate it, collect any constructor parameters, and prepare the Studionet deployment transaction for your wallet.",
                "intent": intent,
                "status": "awaiting_input",
            }
        await logs_store.append("INFO", "AWAIT_CONFIRMATION", "Awaiting confirmation for contract deployment.")
        return {
            "content": f"I'm ready to deploy your contract '{intent.get('contract_name', 'MyContract')}'. Do you want me to proceed?",
            "intent": intent,
            "status": "awaiting_confirmation",
        }

    await logs_store.append("INFO", "AWAIT_CONFIRMATION", "Awaiting confirmation for transfer.", {"intent": intent})
    return {
        "content": "I have parsed your intent and simulated the outcome. Please review and confirm execution.",
        "intent": intent,
        "simulation": simulation,
        "status": "awaiting_confirmation",
    }

@router.post("/confirm")
async def confirm_action(
    request: ConfirmRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    requested_intent = normalize_intent(request.intent)
    network = resolve_network_or_400(request.network)
    wallet_address = require_authenticated_wallet(current_user, request.wallet_address)

    if requested_intent["action"] == "check_balance":
        try:
            balance = await get_balance(wallet_address, network=network)
            await logs_store.append("SUCCESS", "BALANCE_SUCCESS", "Balance read succeeded.", {"balance": balance})
            return {"balance": balance}
        except Exception as e:
            await logs_store.append("ERROR", "BALANCE_FAILED", "Balance fetch failed.", {"error": str(e)})
            raise HTTPException(status_code=502, detail=f"Balance fetch failed: {str(e)}")

    if request.signed_transaction:
        raise HTTPException(
            status_code=400,
            detail="Raw signed transactions are not accepted. Broadcast with the connected wallet and submit its transaction hash.",
        )

    action = requested_intent.get("action")
    if action not in {"transfer", "deploy_contract", "contract_call", "appeal_transaction"}:
        raise HTTPException(status_code=400, detail="Unsupported action for execution")
    if action == "appeal_transaction":
        raise HTTPException(
            status_code=503,
            detail={"code": APPEAL_SUBMISSION.code, "message": APPEAL_SUBMISSION.message},
        )

    envelope = load_prepared_transaction(
        db=db,
        user=current_user,
        prepared_transaction_id=request.prepared_transaction_id,
        intent_hash=request.intent_hash,
        action=action,
        network=network,
        allow_expired_reconciliation=bool(request.tx_hash),
        allow_confirmed_reconciliation=action in {"transfer", "deploy_contract", "contract_call"} and bool(request.tx_hash),
    )
    if envelope.status == "confirmed":
        if envelope.tx_hash and request.tx_hash and envelope.tx_hash.lower() == request.tx_hash.lower():
            return {
                "txHash": envelope.tx_hash,
                "preparedTransactionId": envelope.id,
                "intentHash": envelope.intent_hash,
                "consensusTxId": envelope.consensus_tx_id,
                "lifecycleStatus": envelope.lifecycle_status,
                "evmStatus": envelope.evm_status,
                "consensusStatus": envelope.consensus_status,
                "executionStatus": envelope.execution_status,
                "content": "This wallet transaction was already verified; its canonical lifecycle record was reused.",
            }
        raise HTTPException(status_code=409, detail="Prepared transaction has already been consumed.")

    reused_transaction = (
        db.query(PreparedTransaction)
        .filter(
            PreparedTransaction.user_id == current_user.id,
            PreparedTransaction.tx_hash == request.tx_hash,
            PreparedTransaction.status == "confirmed",
            PreparedTransaction.id != envelope.id,
        )
        .first()
    )
    if reused_transaction:
        raise HTTPException(status_code=409, detail="Submitted transaction hash has already been consumed.")
    intent = prepared_intent(envelope)
    is_safe, error_msg = validate_intent(intent)
    if not is_safe:
        await logs_store.append(
            "ERROR",
            "SAFETY_BLOCK_CONFIRM",
            "Confirmation blocked by safety checks.",
            {"reason": error_msg, "intentHash": envelope.intent_hash},
        )
        raise HTTPException(status_code=400, detail=f"Safety check failed: {error_msg}")

    client = get_client(network=network)
    tx_hash = await verify_submitted_transaction(
        client=client,
        envelope=envelope,
        tx_hash=request.tx_hash,
    )
    mark_prepared_transaction_broadcast(db=db, envelope=envelope, tx_hash=tx_hash)
    await logs_store.append(
        "INFO",
        "CONFIRM_RECEIVED",
        "Authenticated prepared transaction confirmed by user.",
        {
            "action": action,
            "network": network,
            "intentHash": envelope.intent_hash,
            "preparedTransactionId": envelope.id,
            "txHash": tx_hash,
        },
    )

    try:
        await client._wait_for_receipt_or_raise(tx_hash)

        if action == "transfer":
            mark_prepared_transaction_confirmed(db=db, envelope=envelope, tx_hash=tx_hash)
            await logs_store.append("SUCCESS", "TRANSFER_SUCCESS", "Transfer receipt confirmed.", {"txHash": tx_hash})
            return {
                "txHash": tx_hash,
                "preparedTransactionId": envelope.id,
                "intentHash": envelope.intent_hash,
            }

        if action == "deploy_contract":
            consensus_tx_id = await client.get_consensus_transaction_id(tx_hash)
            persist_workflow_deployment(
                db=db,
                user=current_user,
                intent=intent,
                network=network,
                tx_hash=tx_hash,
                consensus_tx_id=consensus_tx_id,
                contract_address=None,
            )
            persist_notary_registry(
                db=db,
                user=current_user,
                intent=intent,
                network=network,
                tx_hash=tx_hash,
                consensus_tx_id=consensus_tx_id,
            )
            mark_prepared_transaction_confirmed(
                db=db,
                envelope=envelope,
                tx_hash=tx_hash,
                consensus_tx_id=consensus_tx_id,
            )
            await logs_store.append(
                "SUCCESS",
                "DEPLOY_SUBMITTED",
                "Contract deployment transaction submitted to GenLayer.",
                {
                    "txHash": tx_hash,
                    "consensusTxId": consensus_tx_id,
                },
            )
            return {
                "txHash": tx_hash,
                "consensusTxId": consensus_tx_id,
                "consensusStatus": "PENDING" if consensus_tx_id else "UNINITIALIZED",
                "lifecycleStatus": "CONSENSUS_PENDING" if consensus_tx_id else "CHAIN_ACCEPTED",
                "preparedTransactionId": envelope.id,
                "intentHash": envelope.intent_hash,
                "content": "Intelligent Contract deployment submitted to GenLayer Studionet.",
            }

        if action == "contract_call":
            consensus_tx_id = await client.get_consensus_transaction_id(tx_hash)
            persist_notary_call(
                db=db,
                user=current_user,
                intent=intent,
                network=network,
                tx_hash=tx_hash,
                consensus_tx_id=consensus_tx_id,
            )
            mark_prepared_transaction_confirmed(
                db=db,
                envelope=envelope,
                tx_hash=tx_hash,
                consensus_tx_id=consensus_tx_id,
            )
            await logs_store.append(
                "SUCCESS",
                "CONTRACT_CALL_SUBMITTED",
                "Contract method transaction submitted to GenLayer.",
                {"txHash": tx_hash, "consensusTxId": consensus_tx_id, "method": intent.get("method")},
            )
            return {
                "txHash": tx_hash,
                "consensusTxId": consensus_tx_id,
                "consensusStatus": "PENDING" if consensus_tx_id else "UNINITIALIZED",
                "lifecycleStatus": "CONSENSUS_PENDING" if consensus_tx_id else "CHAIN_ACCEPTED",
                "preparedTransactionId": envelope.id,
                "intentHash": envelope.intent_hash,
                "content": "Workflow action submitted to GenLayer.",
            }

    except HTTPException:
        raise
    except Exception as exc:
        await logs_store.append(
            "ERROR",
            "CONFIRM_FAILED",
            "Prepared transaction confirmation failed.",
            {
                "action": action,
                "preparedTransactionId": envelope.id,
                "txHash": tx_hash,
                "error": str(exc),
            },
        )
        raise HTTPException(status_code=502, detail=f"Transaction confirmation failed: {str(exc)}") from exc


@router.get("/consensus-readiness")
async def get_consensus_readiness(
    network: str | None = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Read-only safety gate for consensus-bound wallet retries."""
    resolved_network = resolve_network_or_400(network)
    client = get_client(network=resolved_network)
    try:
        chain_id = await client._rpc_call("eth_chainId", [])
        if isinstance(chain_id, str):
            chain_id = int(chain_id, 16) if chain_id.startswith("0x") else int(chain_id)
        if chain_id != client.chain_id:
            return {"ready": False, "blockerCode": "chain_id_mismatch", "message": "RPC chain ID does not match the selected network.", "chainId": chain_id, "expectedChainId": client.chain_id}
        await client._rpc_call("eth_blockNumber", [])
    except Exception as exc:
        return {"ready": False, "blockerCode": "rpc_unavailable", "message": "The selected network RPC is unavailable for a safe retry.", "error": str(exc)}
    if resolved_network != "studionet":
        return {"ready": True, "network": resolved_network}
    cutoff = datetime.utcnow() - timedelta(minutes=15)
    envelope = (
        db.query(PreparedTransaction)
        .filter(
            PreparedTransaction.user_id == current_user.id,
            PreparedTransaction.network == resolved_network,
            PreparedTransaction.status == "confirmed",
            PreparedTransaction.action.in_(["deploy_contract", "contract_call"]),
            PreparedTransaction.created_at >= cutoff,
        )
        .order_by(PreparedTransaction.created_at.desc())
        .first()
    )
    if not envelope:
        return {"ready": True, "network": resolved_network}
    if not envelope.consensus_tx_id and envelope.tx_hash:
        envelope.consensus_tx_id = await client.get_consensus_transaction_id(envelope.tx_hash)
        if envelope.consensus_tx_id:
            db.commit()
        else:
            return {"ready": False, "blockerCode": "consensus_tracking_pending", "message": "The previous wallet transaction is still waiting for its consensus identifier.", "network": resolved_network, "lastTxHash": envelope.tx_hash}
    if not envelope.consensus_tx_id:
        return {"ready": False, "blockerCode": "consensus_tracking_pending", "message": "The previous consensus transaction is not trackable yet.", "network": resolved_network, "lastTxHash": envelope.tx_hash}
    try:
        diagnostics = await client.get_protocol_transaction_diagnostics(envelope.consensus_tx_id)
    except Exception:
        return {"ready": True, "network": resolved_network}
    if diagnostics.get("zero_round_no_majority"):
        return {
            "ready": False,
            "blockerCode": "studio_consensus_zero_round",
            "message": "Studionet finalized the last transaction without assigning validators. Wallet retry is blocked.",
            "network": resolved_network,
            "lastTxHash": envelope.tx_hash,
            "protocolResult": diagnostics.get("protocol_result"),
            "numRounds": diagnostics.get("num_rounds"),
            "validatorCount": diagnostics.get("validator_count"),
            "retryAfterSeconds": max(0, int((envelope.created_at + timedelta(minutes=15) - datetime.utcnow()).total_seconds())),
        }
    return {"ready": True, "network": resolved_network}


@router.post("/consensus-status")
async def get_consensus_status(
    request: ConsensusStatusRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Read GenLayer consensus progress without inferring finality from an EVM receipt."""
    try:
        network = resolve_network_or_400(request.network)
        bound_intent: dict[str, Any] | None = None
        envelope: PreparedTransaction | None = None
        effective_consensus_tx_id = request.consensus_tx_id
        if request.prepared_transaction_id:
            envelope = (
                db.query(PreparedTransaction)
                .filter(
                    PreparedTransaction.id == request.prepared_transaction_id,
                    PreparedTransaction.user_id == current_user.id,
                )
                .first()
            )
            if not envelope:
                raise HTTPException(status_code=404, detail="Prepared transaction was not found.")
            if envelope.status != "confirmed":
                raise HTTPException(status_code=409, detail="Prepared transaction is not confirmed.")
            if not request.intent_hash or envelope.intent_hash != request.intent_hash:
                raise HTTPException(status_code=400, detail="Prepared transaction intent hash does not match.")
            if envelope.network != network:
                raise HTTPException(status_code=400, detail="Prepared transaction network does not match.")
            if envelope.tx_hash == request.consensus_tx_id:
                if envelope.consensus_tx_id is None:
                    resolved_consensus_tx_id = await get_client(network=network).get_consensus_transaction_id(envelope.tx_hash)
                    if resolved_consensus_tx_id:
                        envelope.consensus_tx_id = resolved_consensus_tx_id
                        db.commit()
                    else:
                        raise HTTPException(status_code=409, detail="Consensus transaction ID is not available yet for the confirmed wallet transaction.")
                effective_consensus_tx_id = envelope.consensus_tx_id
            elif envelope.consensus_tx_id != request.consensus_tx_id:
                raise HTTPException(status_code=400, detail="Consensus transaction does not match the prepared transaction.")
            if envelope.consensus_tx_id:
                effective_consensus_tx_id = envelope.consensus_tx_id
            bound_intent = {
                **prepared_intent(envelope),
                **({"tx_hash": envelope.tx_hash} if envelope.tx_hash else {}),
            }

        if envelope is None and effective_consensus_tx_id:
            envelope = (
                db.query(PreparedTransaction)
                .filter(
                    PreparedTransaction.user_id == current_user.id,
                    PreparedTransaction.network == network,
                    PreparedTransaction.consensus_tx_id == effective_consensus_tx_id,
                )
                .order_by(PreparedTransaction.updated_at.desc())
                .first()
            )
            if envelope:
                bound_intent = {
                    **prepared_intent(envelope),
                    **({"tx_hash": envelope.tx_hash} if envelope.tx_hash else {}),
                }

        display_intent = bound_intent or request.workflow_intent
        client = get_client(network=network)
        status_result = await client.get_consensus_transaction_status(effective_consensus_tx_id)
        appeal_window_open = False
        appeal_window_status = 'closed'
        minimum_appeal_bond_wei = None
        appeal_readiness_error = None
        if status_result['appealable']:
            try:
                appeal_requirements = await client.get_appeal_requirements(
                    effective_consensus_tx_id
                )
                appeal_window_open = appeal_requirements['appeal_window_open']
                appeal_window_status = appeal_requirements['appeal_window_status']
                minimum_appeal_bond_wei = str(
                    appeal_requirements['minimum_appeal_bond_wei']
                )
                status_result = {
                    **status_result,
                    'appealable': appeal_window_open,
                }
            except Exception as exc:
                appeal_window_status = 'unavailable'
                appeal_readiness_error = str(exc)
                status_result = {
                    **status_result,
                    'appealable': False,
                }
        deployment_details = {"contract_address": None, "derived_addresses": []}
        execution_status = EXECUTION_STATUS_NOT_VOTED
        transaction_details = {"transaction": None}
        protocol_diagnostics = {"protocol_result": None, "num_rounds": None, "validator_count": None, "vote_count": None, "zero_round_no_majority": False}

        if status_result["final"]:
            try:
                protocol_diagnostics = await client.get_protocol_transaction_diagnostics(effective_consensus_tx_id)
            except Exception as exc:
                protocol_diagnostics["diagnostics_error"] = str(exc)
            transaction_details = await client.get_transaction_details(effective_consensus_tx_id)
            execution_status = transaction_details["execution_status"]
            if (
                execution_status == EXECUTION_STATUS_FINISHED_WITH_RETURN
                and isinstance(display_intent, dict)
                and display_intent.get("action") == "deploy_contract"
            ):
                deployment_details = await client.get_deployment_details(
                    effective_consensus_tx_id,
                    transaction=transaction_details["transaction"],
                )
            if (
                execution_status in {EXECUTION_STATUS_NOT_VOTED, EXECUTION_STATUS_UNKNOWN}
                and not protocol_diagnostics.get("zero_round_no_majority")
            ):
                status_result = {**status_result, "terminal": False}

        update_workflow_consensus_state(
            db=db,
            user=current_user,
            consensus_tx_id=effective_consensus_tx_id,
            workflow_intent=bound_intent,
            consensus_status=status_result["status"],
            execution_status=execution_status,
            contract_address=deployment_details["contract_address"],
            network=network,
            diagnostics=protocol_diagnostics,
        )
        if envelope:
            update_prepared_consensus_state(
                db=db,
                envelope=envelope,
                status_result={**status_result, "consensusTxId": effective_consensus_tx_id},
                execution_status=execution_status,
                diagnostics=protocol_diagnostics,
            )
        update_notary_consensus_state(
            db=db,
            user=current_user,
            consensus_tx_id=effective_consensus_tx_id,
            intent=bound_intent,
            consensus_status=status_result["status"],
            execution_status=execution_status,
            contract_address=deployment_details["contract_address"],
            network=network,
        )
        log_level = "INFO"
        if execution_status == EXECUTION_STATUS_FINISHED_WITH_RETURN:
            log_level = "SUCCESS"
        elif (
            execution_status == EXECUTION_STATUS_FINISHED_WITH_ERROR
            or (status_result["terminal"] and not status_result["final"])
        ):
            log_level = "ERROR"
        await logs_store.append(
            log_level,
            "CONSENSUS_STATUS",
            f"Consensus transaction is {status_result['status'].lower()}.",
            {
                "consensusTxId": effective_consensus_tx_id,
                "network": network,
                "status": status_result["status"],
                "executionStatus": execution_status,
            },
        )
        return {
            "consensusTxId": effective_consensus_tx_id,
            **status_result,
            'appealWindowOpen': appeal_window_open,
            'appealWindowStatus': appeal_window_status,
            'minimumAppealBondWei': minimum_appeal_bond_wei,
            'appealReadinessError': appeal_readiness_error,
            "executionStatus": execution_status,
            "contractAddress": deployment_details["contract_address"],
            "derivedAddresses": deployment_details["derived_addresses"],
            "protocolResult": protocol_diagnostics.get("protocol_result"),
            "numRounds": protocol_diagnostics.get("num_rounds"),
            "validatorCount": protocol_diagnostics.get("validator_count"),
            "voteCount": protocol_diagnostics.get("vote_count"),
            "zeroRoundNoMajority": protocol_diagnostics.get("zero_round_no_majority", False),
            "lifecycleStatus": envelope.lifecycle_status if envelope else (
                "FINALIZED" if status_result["final"] else "CONSENSUS_PENDING"
            ),
            "evmStatus": envelope.evm_status if envelope else None,
        }
    except HTTPException:
        raise
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        await logs_store.append(
            "ERROR",
            "CONSENSUS_STATUS_FAILED",
            "Failed to read GenLayer consensus status.",
            {"consensusTxId": request.consensus_tx_id, "error": str(exc)},
        )
        raise HTTPException(status_code=502, detail=f"Failed to read consensus status: {str(exc)}") from exc


@router.post("/transfer-tx")
async def build_transfer_tx(
    request: TransferTxRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> DeployTxResponse:
    """Build and persist an authenticated wallet-reviewed GEN transfer."""
    try:
        network = resolve_network_or_400(request.network)
        sender = require_authenticated_wallet(current_user, request.address)
        recipient = Web3.to_checksum_address(request.recipient)
        value = int(request.amount_wei)
        if value <= 0:
            raise ValueError("Transfer amount must be greater than zero")
        gas_limit = request.gas_limit or 21000
        if gas_limit < 21000:
            raise ValueError("Gas limit is too low")

        client = get_client(network=network)
        tx = await client._build_wallet_transaction(
            sender_address=sender,
            to_address=recipient,
            encoded_data="0x",
            value=value,
            gas_limit=gas_limit,
        )
        intent = build_transfer_intent(request, recipient, value)
        envelope = create_prepared_transaction(
            db=db,
            user=current_user,
            action="transfer",
            network=network,
            sender_address=sender,
            tx=tx,
            intent=intent,
        )
        await logs_store.append(
            "INFO",
            "TRANSFER_TX_BUILD",
            "Prepared authenticated GEN transfer transaction.",
            {"network": network, "from": sender, "to": recipient, "intentHash": envelope.intent_hash},
        )
        return DeployTxResponse(
            chain_id=tx["chain_id"],
            to=tx["to"],
            data=tx["data"],
            value=str(tx["value"]),
            nonce=tx["nonce"],
            gas_limit=tx["gas_limit"],
            rpc_url=client.rpc_url,
            gas_price=str(tx["gasPrice"]) if "gasPrice" in tx else None,
            max_fee_per_gas=str(tx["maxFeePerGas"]) if "maxFeePerGas" in tx else None,
            max_priority_fee_per_gas=str(tx["maxPriorityFeePerGas"]) if "maxPriorityFeePerGas" in tx else None,
            **prepared_transaction_response(envelope),
        )
    except HTTPException:
        raise
    except Exception as exc:
        await logs_store.append("ERROR", "TRANSFER_TX_BUILD_FAILED", "Failed to prepare transfer.", {"error": str(exc)})
        raise HTTPException(status_code=400, detail=f"Failed to prepare transfer transaction: {str(exc)}") from exc


@router.post("/deploy-tx")
async def build_deploy_tx(
    request: DeployTxRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> DeployTxResponse:
    """Build the Studionet consensus-contract transaction for wallet-side deployment."""
    try:
        network = resolve_network_or_400(request.network)
        checksum_address = require_authenticated_wallet(current_user, request.address)
        value = int(request.value_wei or "0")
        if value < 0:
            raise ValueError("Deployment value cannot be negative")
        if request.gas_limit is not None and request.gas_limit < 21000:
            raise ValueError("Gas limit is too low")
        if request.source_origin not in {"generated", "uploaded"}:
            raise HTTPException(status_code=400, detail="Unsupported contract source origin.")
        validation = contract_generation_service.validator.validate(request.code)
        if not validation["valid"]:
            raise HTTPException(
                status_code=400,
                detail="Contract source failed validation: " + "; ".join(validation["errors"]),
            )
        source_metadata = verify_reviewed_source(
            code=request.code,
            origin=request.source_origin,
            reviewed_source_hash=request.source_hash,
            reviewed_py_genlayer_dependency=request.py_genlayer_dependency,
            reviewed_generator_version=request.generator_version,
            reviewed_validator_version=request.validator_version,
        )
        client = get_client(network=network)

        await logs_store.append(
            "INFO",
            "DEPLOY_TX_BUILD",
            "Preparing GenLayer deployment transaction.",
            {
                "network": network,
                "from": checksum_address,
                "argsCount": len(request.constructor_args),
                "valueWei": str(value),
            },
        )
        tx = await client.build_deploy_transaction(
            sender_address=checksum_address,
            code=request.code,
            args=request.constructor_args,
            kwargs=request.constructor_kwargs,
            value=value,
            gas_limit=request.gas_limit,
            consensus_max_rotations=request.consensus_max_rotations,
            leader_only=request.leader_only,
        )
        intent = build_deploy_intent(request, value)
        intent.update(source_metadata)
        envelope = create_prepared_transaction(
            db=db,
            user=current_user,
            action="deploy_contract",
            network=network,
            sender_address=checksum_address,
            tx=tx,
            intent=intent,
            consensus_max_rotations=request.consensus_max_rotations,
            leader_only=request.leader_only,
        )
        return DeployTxResponse(
            chain_id=tx["chain_id"],
            to=tx["to"],
            data=tx["data"],
            value=str(tx["value"]),
            nonce=tx["nonce"],
            gas_limit=tx["gas_limit"],
            rpc_url=client.rpc_url,
            gas_price=str(tx["gasPrice"]) if "gasPrice" in tx else None,
            max_fee_per_gas=str(tx["maxFeePerGas"]) if "maxFeePerGas" in tx else None,
            max_priority_fee_per_gas=str(tx["maxPriorityFeePerGas"]) if "maxPriorityFeePerGas" in tx else None,
            **prepared_transaction_response(envelope),
            **source_metadata,
        )
    except HTTPException:
        raise
    except StaleContractReviewError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except ContractSourceIntegrityError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as e:
        await logs_store.append("ERROR", "DEPLOY_TX_BUILD_FAILED", "Failed to prepare deployment transaction.", {"error": str(e)})
        raise HTTPException(status_code=502, detail=f"Failed to prepare deployment transaction: {str(e)}")


@router.post("/notary-blueprint", response_model=NotaryBlueprintResponse)
async def review_notary_blueprint(
    request: NotaryBlueprintRequest,
    current_user: User = Depends(get_current_user),
) -> NotaryBlueprintResponse:
    try:
        wallet_address = Web3.to_checksum_address(current_user.connected_wallet_address)
        spec = validate_notary_spec(request.notary_spec, wallet_address)
        code = generate_notary_contract_code()
        validation = contract_generation_service.validator.validate(code)
        if not validation["valid"]:
            raise HTTPException(status_code=500, detail="The canonical AI Notary template failed validation.")
        metadata = artifact_metadata(code, NOTARY_SOURCE_ORIGIN)
        return NotaryBlueprintResponse(
            code=code,
            contract_name=NOTARY_CONTRACT_NAME,
            file_name=f"{NOTARY_CONTRACT_NAME}.py",
            explanation=(
                "Backend-generated reusable AI Notary registry. The exact source hash is bound "
                "to deployment, while claim submission and evaluation remain separate zero-value calls."
            ),
            notary_spec=spec.as_dict(),
            constructor_args=notary_constructor_args(wallet_address),
            constructor_kwargs={},
            validation=validation,
            evidence_policy=(
                "One to three allowlisted public HTTPS sources; credentials, local hosts, private "
                "documents, duplicate URLs, and oversized inputs are rejected."
            ),
            equivalence_rule=(
                "Validators independently fetch and evaluate evidence, then compare verdict, source "
                "usability, and normalized material facts. Rationale wording may differ."
            ),
            authorization=(
                "The authenticated claimant submits and evaluates the claim. Protocol appeals remain "
                "available to eligible wallets while the network appeal window is open."
            ),
            **metadata,
        )
    except HTTPException:
        raise
    except NotaryValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/notary-deploy-tx", response_model=NotaryDeployTxResponse)
async def build_notary_deploy_tx(
    request: NotaryDeployTxRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> NotaryDeployTxResponse:
    try:
        network = resolve_network_or_400(request.network)
        wallet_address = require_authenticated_wallet(current_user, request.address)
        if request.gas_limit is not None and request.gas_limit < 21000:
            raise NotaryValidationError("Gas limit is too low.")
        spec = validate_notary_spec(request.notary_spec, wallet_address)
        code = generate_notary_contract_code()
        constructor_args = notary_constructor_args(wallet_address)
        validation = contract_generation_service.validator.validate(code)
        if not validation["valid"]:
            raise HTTPException(status_code=500, detail="The canonical AI Notary template failed validation.")
        source_metadata = verify_reviewed_source(
            code=code,
            origin=NOTARY_SOURCE_ORIGIN,
            reviewed_source_hash=request.source_hash,
            reviewed_py_genlayer_dependency=request.py_genlayer_dependency,
            reviewed_generator_version=request.generator_version,
            reviewed_validator_version=request.validator_version,
        )
        client = get_client(network=network)
        tx = await client.build_deploy_transaction(
            sender_address=wallet_address,
            code=code,
            args=constructor_args,
            kwargs={},
            value=0,
            gas_limit=request.gas_limit,
            consensus_max_rotations=request.consensus_max_rotations,
            leader_only=request.leader_only,
        )
        intent = build_notary_deploy_intent(
            request,
            spec.as_dict(),
            code,
            constructor_args,
        )
        intent.update(source_metadata)
        envelope = create_prepared_transaction(
            db=db,
            user=current_user,
            action="deploy_contract",
            network=network,
            sender_address=wallet_address,
            tx=tx,
            intent=intent,
            consensus_max_rotations=request.consensus_max_rotations,
            leader_only=request.leader_only,
        )
        await logs_store.append(
            "INFO",
            "NOTARY_DEPLOY_TX_BUILD",
            "Prepared authenticated AI Notary registry deployment.",
            {"network": network, "claimId": spec.claim_id, "intentHash": envelope.intent_hash},
        )
        return NotaryDeployTxResponse(
            chain_id=tx["chain_id"],
            to=tx["to"],
            data=tx["data"],
            value=str(tx["value"]),
            nonce=tx["nonce"],
            gas_limit=tx["gas_limit"],
            rpc_url=client.rpc_url,
            gas_price=str(tx["gasPrice"]) if "gasPrice" in tx else None,
            max_fee_per_gas=str(tx["maxFeePerGas"]) if "maxFeePerGas" in tx else None,
            max_priority_fee_per_gas=str(tx["maxPriorityFeePerGas"]) if "maxPriorityFeePerGas" in tx else None,
            code=code,
            contract_name=NOTARY_CONTRACT_NAME,
            constructor_args=constructor_args,
            constructor_kwargs={},
            notary_spec=spec.as_dict(),
            **prepared_transaction_response(envelope),
            **source_metadata,
        )
    except HTTPException:
        raise
    except StaleContractReviewError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except (ContractSourceIntegrityError, NotaryValidationError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        await logs_store.append(
            "ERROR",
            "NOTARY_DEPLOY_TX_BUILD_FAILED",
            "Failed to prepare AI Notary registry deployment.",
            {"error": str(exc)},
        )
        raise HTTPException(status_code=502, detail=f"Failed to prepare AI Notary deployment: {str(exc)}") from exc


@router.post("/notary-call-tx", response_model=DeployTxResponse)
async def build_notary_call_tx(
    request: NotaryCallTxRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> DeployTxResponse:
    try:
        network = resolve_network_or_400(request.network)
        wallet_address = require_authenticated_wallet(current_user, request.address)
        contract_address = Web3.to_checksum_address(request.contract_address)
        if request.gas_limit is not None and request.gas_limit < 21000:
            raise NotaryValidationError("Gas limit is too low.")
        registry = find_notary_registry(db, contract_address, network)
        if not registry or registry.status not in {"active", "finalized"}:
            raise HTTPException(status_code=404, detail="Active AI Notary registry was not found.")

        spec = None
        if request.notary_action.strip().lower() == "submit_claim":
            spec = validate_notary_spec(request.notary_spec or {}, wallet_address)
            if find_notary_claim(db, registry, spec.claim_id):
                raise HTTPException(status_code=409, detail="Claim reference was already submitted to this registry.")
        else:
            claim = find_notary_claim(db, registry, request.claim_id)
            if not claim:
                raise HTTPException(status_code=404, detail="AI Notary claim reference was not found.")
            if claim.user_id != current_user.id:
                raise HTTPException(status_code=403, detail="Only the claimant can evaluate this claim.")
            if claim.status not in {"pending", "evaluated"}:
                raise HTTPException(status_code=409, detail="Claim submission is not finalized.")
            if claim.verdict != "PENDING" or claim.status == "evaluated":
                raise HTTPException(status_code=409, detail="Claim was already evaluated.")

        method, args = validate_notary_action(request.notary_action, request.claim_id, spec)
        client = get_client(network=network)
        tx = await client.build_contract_call_transaction(
            sender_address=wallet_address,
            contract_address=contract_address,
            method=method,
            args=args,
            kwargs={},
            value=0,
            gas_limit=request.gas_limit,
            consensus_max_rotations=request.consensus_max_rotations,
            leader_only=request.leader_only,
        )
        intent = build_notary_call_intent(
            request,
            contract_address,
            method,
            args,
            spec.as_dict() if spec else None,
        )
        envelope = create_prepared_transaction(
            db=db,
            user=current_user,
            action="contract_call",
            network=network,
            sender_address=wallet_address,
            tx=tx,
            intent=intent,
            consensus_max_rotations=request.consensus_max_rotations,
            leader_only=request.leader_only,
        )
        await logs_store.append(
            "INFO",
            "NOTARY_CALL_TX_BUILD",
            "Prepared authenticated AI Notary contract call.",
            {
                "network": network,
                "contract": contract_address,
                "claimId": request.claim_id,
                "method": method,
                "intentHash": envelope.intent_hash,
            },
        )
        return DeployTxResponse(
            chain_id=tx["chain_id"],
            to=tx["to"],
            data=tx["data"],
            value=str(tx["value"]),
            nonce=tx["nonce"],
            gas_limit=tx["gas_limit"],
            rpc_url=client.rpc_url,
            gas_price=str(tx["gasPrice"]) if "gasPrice" in tx else None,
            max_fee_per_gas=str(tx["maxFeePerGas"]) if "maxFeePerGas" in tx else None,
            max_priority_fee_per_gas=str(tx["maxPriorityFeePerGas"]) if "maxPriorityFeePerGas" in tx else None,
            **prepared_transaction_response(envelope),
        )
    except HTTPException:
        raise
    except NotaryValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        await logs_store.append(
            "ERROR",
            "NOTARY_CALL_TX_BUILD_FAILED",
            "Failed to prepare AI Notary contract call.",
            {"claimId": request.claim_id, "error": str(exc)},
        )
        raise HTTPException(status_code=502, detail=f"Failed to prepare AI Notary call: {str(exc)}") from exc


@router.post("/workflow-contract", response_model=WorkflowContractResponse)
async def review_workflow_contract(
    request: WorkflowContractRequest,
    current_user: User = Depends(get_current_user),
) -> WorkflowContractResponse:
    try:
        workflow_type = str(
            request.workflow_config.get("workflowType")
            or request.workflow_config.get("workflow_type")
            or ""
        ).strip().lower()
        disabled = disabled_workflow_capability(workflow_type)
        if disabled:
            raise HTTPException(
                status_code=503,
                detail={"code": disabled.code, "message": disabled.message},
            )
        wallet_address = Web3.to_checksum_address(current_user.connected_wallet_address)
        validated_config = validate_workflow_config(request.workflow_config, wallet_address)
        code = generate_workflow_contract_code(validated_config)
        validation = contract_generation_service.validator.validate(code)
        if not validation["valid"]:
            raise HTTPException(status_code=500, detail="The canonical workflow template failed validation.")
        contract_name = get_workflow_contract_name(validated_config)
        metadata = artifact_metadata(code, "workflow")
        workflow_label = validated_config["workflowType"].replace("_", " ")
        return WorkflowContractResponse(
            code=code,
            contract_name=contract_name,
            contract_type=validated_config["workflowType"],
            file_name=f"{contract_name}.py",
            explanation=(
                f"Backend-generated {workflow_label} template. "
                "The displayed source hash must still match when the deployment transaction is prepared."
            ),
            workflow_config=validated_config,
            constructor_args=get_workflow_constructor_args(validated_config, wallet_address),
            constructor_kwargs={},
            validation=validation,
            **metadata,
        )
    except HTTPException:
        raise
    except WorkflowValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/phase9/conditional-artifact", response_model=WorkflowContractResponse)
async def review_phase9_conditional_contract(
    request: WorkflowContractRequest,
    current_user: User = Depends(get_current_user),
) -> WorkflowContractResponse:
    require_phase9_live_proof()
    require_phase9_conditional_config(request.workflow_config)
    try:
        wallet_address = Web3.to_checksum_address(current_user.connected_wallet_address)
        validated_config = validate_workflow_config(request.workflow_config, wallet_address)
        code = generate_workflow_contract_code(validated_config)
        validation = contract_generation_service.validator.validate(code)
        if not validation["valid"]:
            raise HTTPException(status_code=500, detail="The canonical workflow template failed validation.")
        contract_name = get_workflow_contract_name(validated_config)
        metadata = artifact_metadata(code, "workflow")
        return WorkflowContractResponse(
            code=code,
            contract_name=contract_name,
            contract_type=validated_config["workflowType"],
            file_name=f"{contract_name}.py",
            explanation=(
                "Local-only Phase 9 proof artifact generated from the canonical backend workflow template. "
                "The public conditional-payment capability remains disabled."
            ),
            workflow_config=validated_config,
            constructor_args=get_workflow_constructor_args(validated_config, wallet_address),
            constructor_kwargs={},
            validation=validation,
            **metadata,
        )
    except HTTPException:
        raise
    except WorkflowValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


async def _build_workflow_deploy_tx_response(
    request: WorkflowDeployTxRequest,
    current_user: User,
    db: Session,
    *,
    allow_disabled_workflow: bool,
) -> WorkflowDeployTxResponse:
    """Build a deploy transaction from a trusted backend workflow template."""
    try:
        workflow_type = str(
            request.workflow_config.get("workflowType")
            or request.workflow_config.get("workflow_type")
            or ""
        ).strip().lower()
        disabled = disabled_workflow_capability(workflow_type)
        if disabled and not allow_disabled_workflow:
            raise HTTPException(
                status_code=503,
                detail={"code": disabled.code, "message": disabled.message},
            )
        network = resolve_network_or_400(request.network)
        checksum_address = require_authenticated_wallet(current_user, request.address)
        validated_config = validate_workflow_config(request.workflow_config, checksum_address)
        code = generate_workflow_contract_code(validated_config)
        constructor_args = get_workflow_constructor_args(validated_config, checksum_address)
        contract_name = get_workflow_contract_name(validated_config)
        validation = contract_generation_service.validator.validate(code)
        if not validation["valid"]:
            raise HTTPException(status_code=500, detail="The canonical workflow template failed validation.")
        source_metadata = verify_reviewed_source(
            code=code,
            origin="workflow",
            reviewed_source_hash=request.source_hash,
            reviewed_py_genlayer_dependency=request.py_genlayer_dependency,
            reviewed_generator_version=request.generator_version,
            reviewed_validator_version=request.validator_version,
        )
        requested_value = int(request.value_wei or "0")
        value = get_workflow_deploy_value_wei(validated_config)
        if requested_value not in {0, value}:
            raise HTTPException(
                status_code=400,
                detail="Workflow deployment value does not match the validated GEN amount.",
            )

        client = get_client(network=network)
        tx = await client.build_deploy_transaction(
            sender_address=checksum_address,
            code=code,
            args=constructor_args,
            kwargs={},
            value=value,
            gas_limit=request.gas_limit,
            consensus_max_rotations=request.consensus_max_rotations,
            leader_only=request.leader_only,
        )
        intent = build_workflow_deploy_intent(
            request,
            validated_config,
            code,
            contract_name,
            constructor_args,
            value,
        )
        intent.update(source_metadata)
        envelope = create_prepared_transaction(
            db=db,
            user=current_user,
            action="deploy_contract",
            network=network,
            sender_address=checksum_address,
            tx=tx,
            intent=intent,
            consensus_max_rotations=request.consensus_max_rotations,
            leader_only=request.leader_only,
        )
        await logs_store.append(
            "INFO",
            "WORKFLOW_DEPLOY_TX_BUILD",
            "Preparing trusted workflow deployment transaction.",
            {"network": network, "workflowType": validated_config["workflowType"], "from": checksum_address},
        )
        return WorkflowDeployTxResponse(
            chain_id=tx["chain_id"],
            to=tx["to"],
            data=tx["data"],
            value=str(tx["value"]),
            nonce=tx["nonce"],
            gas_limit=tx["gas_limit"],
            rpc_url=client.rpc_url,
            gas_price=str(tx["gasPrice"]) if "gasPrice" in tx else None,
            max_fee_per_gas=str(tx["maxFeePerGas"]) if "maxFeePerGas" in tx else None,
            max_priority_fee_per_gas=str(tx["maxPriorityFeePerGas"]) if "maxPriorityFeePerGas" in tx else None,
            code=code,
            contract_name=contract_name,
            constructor_args=constructor_args,
            constructor_kwargs={},
            workflow_config=validated_config,
            **prepared_transaction_response(envelope),
            **source_metadata,
        )
    except HTTPException:
        raise
    except StaleContractReviewError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except ContractSourceIntegrityError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except WorkflowValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as e:
        await logs_store.append("ERROR", "WORKFLOW_DEPLOY_TX_BUILD_FAILED", "Failed to prepare workflow deployment.", {"error": str(e)})
        raise HTTPException(status_code=502, detail=f"Failed to prepare workflow deployment: {str(e)}")


@router.post("/workflow-deploy-tx")
async def build_workflow_deploy_tx(
    request: WorkflowDeployTxRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> WorkflowDeployTxResponse:
    return await _build_workflow_deploy_tx_response(
        request,
        current_user,
        db,
        allow_disabled_workflow=False,
    )


@router.post("/phase9/conditional-deploy-tx")
async def build_phase9_conditional_deploy_tx(
    request: WorkflowDeployTxRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> WorkflowDeployTxResponse:
    require_phase9_live_proof()
    require_phase9_conditional_config(request.workflow_config)
    return await _build_workflow_deploy_tx_response(
        request,
        current_user,
        db,
        allow_disabled_workflow=True,
    )


async def _build_contract_call_tx_response(
    request: ContractCallTxRequest,
    current_user: User,
    db: Session,
    *,
    allow_disabled_workflow: bool,
) -> DeployTxResponse:
    """Build a GenLayer consensus transaction for a deployed contract method call."""
    try:
        network = resolve_network_or_400(request.network)
        checksum_address = require_authenticated_wallet(current_user, request.address)
        checksum_contract = Web3.to_checksum_address(request.contract_address)
        method = request.method.strip()
        if not method:
            raise ValueError("Method is required")
        if request.workflow_type:
            disabled = disabled_workflow_capability(request.workflow_type)
            if disabled and not allow_disabled_workflow:
                raise HTTPException(
                    status_code=503,
                    detail={"code": disabled.code, "message": disabled.message},
                )
            validate_workflow_action(request.workflow_type, method, request.args)
        value = int(request.value_wei or "0")
        if request.workflow_type:
            deployment = find_workflow_deployment(db, checksum_contract, network)
            if not deployment:
                raise HTTPException(status_code=404, detail="Workflow deployment was not found.")
            if deployment.workflow_type != request.workflow_type:
                raise HTTPException(status_code=400, detail="Workflow type does not match the deployed contract.")
            workflow_config = json.loads(deployment.config_json)
            owner_address = deployment.user.connected_wallet_address
            if not is_workflow_action_authorized(
                workflow_config,
                owner_address,
                checksum_address,
                method,
            ):
                raise HTTPException(status_code=403, detail="Wallet is not authorized for this workflow action.")
            expected_value = get_workflow_action_value_wei(workflow_config, method)
            if value not in {0, expected_value}:
                raise HTTPException(status_code=400, detail="Workflow action value does not match the configured GEN amount.")
            value = expected_value
        if value < 0:
            raise ValueError("Contract call value cannot be negative")

        client = get_client(network=network)
        tx = await client.build_contract_call_transaction(
            sender_address=checksum_address,
            contract_address=checksum_contract,
            method=method,
            args=request.args,
            kwargs=request.kwargs,
            value=value,
            gas_limit=request.gas_limit,
            consensus_max_rotations=request.consensus_max_rotations,
            leader_only=request.leader_only,
        )
        intent = build_contract_call_intent(request, checksum_contract, method, value)
        envelope = create_prepared_transaction(
            db=db,
            user=current_user,
            action="contract_call",
            network=network,
            sender_address=checksum_address,
            tx=tx,
            intent=intent,
            consensus_max_rotations=request.consensus_max_rotations,
            leader_only=request.leader_only,
        )
        await logs_store.append(
            "INFO",
            "CONTRACT_CALL_TX_BUILD",
            "Preparing GenLayer contract method transaction.",
            {"network": network, "from": checksum_address, "contract": checksum_contract, "method": method},
        )
        return DeployTxResponse(
            chain_id=tx["chain_id"],
            to=tx["to"],
            data=tx["data"],
            value=str(tx["value"]),
            nonce=tx["nonce"],
            gas_limit=tx["gas_limit"],
            rpc_url=client.rpc_url,
            gas_price=str(tx["gasPrice"]) if "gasPrice" in tx else None,
            max_fee_per_gas=str(tx["maxFeePerGas"]) if "maxFeePerGas" in tx else None,
            max_priority_fee_per_gas=str(tx["maxPriorityFeePerGas"]) if "maxPriorityFeePerGas" in tx else None,
            **prepared_transaction_response(envelope),
        )
    except HTTPException:
        raise
    except WorkflowValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as e:
        await logs_store.append("ERROR", "CONTRACT_CALL_TX_BUILD_FAILED", "Failed to prepare contract call.", {"error": str(e)})
        raise HTTPException(status_code=502, detail=f"Failed to prepare contract call: {str(e)}")


@router.post("/contract-call-tx")
async def build_contract_call_tx(
    request: ContractCallTxRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> DeployTxResponse:
    return await _build_contract_call_tx_response(
        request,
        current_user,
        db,
        allow_disabled_workflow=False,
    )


@router.post("/phase9/conditional-call-tx")
async def build_phase9_conditional_call_tx(
    request: ContractCallTxRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> DeployTxResponse:
    require_phase9_live_proof()
    if str(request.workflow_type or "").strip().lower() != "conditional_payment":
        raise HTTPException(status_code=400, detail="Phase 9 proof calls require conditional_payment workflow type.")
    return await _build_contract_call_tx_response(
        request,
        current_user,
        db,
        allow_disabled_workflow=True,
    )


@router.post('/appeal-tx', response_model=AppealTxResponse)
async def build_appeal_tx(
    request: AppealTxRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> AppealTxResponse:
    """Fail closed until an end-to-end protocol appeal is proven."""
    raise HTTPException(
        status_code=503,
        detail={"code": APPEAL_SUBMISSION.code, "message": APPEAL_SUBMISSION.message},
    )

    # Preserved for Phase 16 implementation and verification. This code remains
    # unreachable until appeal submission has authoritative live proof.
    try:
        network = resolve_network_or_400(request.network)
        appellant = require_authenticated_wallet(current_user, request.address)
        requested_bond = int(request.bond_wei) if request.bond_wei is not None else None
        if requested_bond is not None and requested_bond < 0:
            raise ValueError('Appeal bond cannot be negative')
        if request.gas_limit is not None and request.gas_limit < 21000:
            raise ValueError('Gas limit is too low')

        client = get_client(network=network)
        tx = await client.build_appeal_transaction(
            sender_address=appellant,
            consensus_tx_id=request.consensus_tx_id,
            bond_wei=requested_bond,
            gas_limit=request.gas_limit,
        )
        requirements = tx['appeal_requirements']
        appeal_bond = int(tx['value'])
        intent = build_appeal_intent(request, requirements, appeal_bond)
        intent['gas_limit'] = tx['gas_limit']
        envelope = create_prepared_transaction(
            db=db,
            user=current_user,
            action='appeal_transaction',
            network=network,
            sender_address=appellant,
            tx=tx,
            intent=intent,
        )
        await logs_store.append(
            'INFO',
            'APPEAL_TX_BUILD',
            'Prepared authenticated protocol appeal transaction.',
            {
                'network': network,
                'appellant': appellant,
                'consensusTxId': requirements['consensus_tx_id'],
                'appealBondWei': str(appeal_bond),
                'gasLimit': tx['gas_limit'],
                'intentHash': envelope.intent_hash,
            },
        )
        return AppealTxResponse(
            chain_id=tx['chain_id'],
            to=tx['to'],
            data=tx['data'],
            value=str(tx['value']),
            nonce=tx['nonce'],
            gas_limit=tx['gas_limit'],
            rpc_url=client.rpc_url,
            gas_price=str(tx['gasPrice']) if 'gasPrice' in tx else None,
            max_fee_per_gas=str(tx['maxFeePerGas']) if 'maxFeePerGas' in tx else None,
            max_priority_fee_per_gas=(
                str(tx['maxPriorityFeePerGas'])
                if 'maxPriorityFeePerGas' in tx
                else None
            ),
            consensus_tx_id=requirements['consensus_tx_id'],
            consensus_status=requirements['consensus_status'],
            appeal_window_open=requirements['appeal_window_open'],
            appeal_window_status=requirements['appeal_window_status'],
            minimum_appeal_bond_wei=str(requirements['minimum_appeal_bond_wei']),
            appeal_bond_wei=str(appeal_bond),
            appeal_round=requirements.get('appeal_round'),
            appeal_status_code=requirements.get('appeal_status_code'),
            appeal_window_source=requirements.get('appeal_window_source'),
            minimum_appeal_bond_source=requirements.get('minimum_appeal_bond_source'),
            **prepared_transaction_response(envelope),
        )
    except HTTPException:
        raise
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        await logs_store.append(
            'ERROR',
            'APPEAL_TX_BUILD_FAILED',
            'Failed to prepare protocol appeal transaction.',
            {'consensusTxId': request.consensus_tx_id, 'error': str(exc)},
        )
        error_text = str(exc)
        lowered_error = error_text.lower()
        if any(marker in lowered_error for marker in (
            'insufficient funds',
            'insufficient balance',
            'insufficient gas',
            'gas limit is too low',
        )):
            raise HTTPException(
                status_code=400,
                detail=f'Failed to prepare appeal transaction: {error_text}',
            ) from exc
        raise HTTPException(
            status_code=502,
            detail=f'Failed to prepare appeal transaction: {error_text}',
        ) from exc


@router.post("/validate-contract")
async def validate_contract(request: ContractValidationRequest) -> ContractValidationResponse:
    if request.file_name and not request.file_name.lower().endswith(".py"):
        return ContractValidationResponse(
            valid=False,
            message="Only Python contract files with a .py extension can be deployed.",
            errors=["Upload a Python .py file written as a GenLayer Intelligent Contract."],
            warnings=[],
            contract_names=[],
        )

    validation = contract_generation_service.validator.validate(request.code)
    if validation["valid"]:
        validation = {
            **validation,
            **artifact_metadata(request.code, "uploaded"),
        }
    await logs_store.append(
        "INFO" if validation["valid"] else "ERROR",
        "CONTRACT_VALIDATION",
        validation["message"],
        {"file_name": request.file_name, "errors": validation["errors"], "warnings": validation["warnings"]},
    )
    return ContractValidationResponse(**validation)


@router.post("/contract-review")
async def review_contract(request: ContractValidationRequest) -> dict[str, Any]:
    review = contract_review_service.review(request.code)
    await logs_store.append(
        "INFO",
        "CONTRACT_REVIEW_COMPLETED",
        "Automated contract preflight completed.",
        {"verdict": review["verdict"], "contractNames": review["structural"]["contractNames"]},
    )
    return review


@router.post("/generate-contract")
@limiter.limit("5/minute")
async def generate_contract_endpoint(
    request: Request,
    body: GenerateContractRequest,
    current_user: User = Depends(get_current_user),
):
    intent = body.intent
    request_text = str(
        intent.get("logic_description")
        or intent.get("condition")
        or intent.get("contract_type")
        or "Generate a GenLayer Intelligent Contract"
    )
    result = contract_generation_service.generate(request_text, advanced=bool(intent.get("advanced")))
    if not result["ok"]:
        return {
            "code": "",
            "contract_name": intent.get("contract_name") or "GeneratedContract",
            "valid": False,
            "errors": result.get("errors", []),
            "warnings": result.get("warnings", []),
            "message": result.get("message", "Unable to generate a valid GenLayer contract."),
        }

    validation = result["validation"]
    return {
        "code": result["code"],
        "contract_name": result["contractName"],
        "valid": validation["valid"],
        "errors": validation["errors"],
        "warnings": validation["warnings"],
        "message": validation["message"],
        "source_hash": result["source_hash"],
        "source_origin": result["source_origin"],
        "py_genlayer_dependency": result["py_genlayer_dependency"],
        "genlayer_sdk_version": result["genlayer_sdk_version"],
        "generator_version": result["generator_version"],
        "validator_version": result["validator_version"],
        "compiler_version": result["compiler_version"],
        "artifact_version": result["artifact_version"],
    }


@router.get("/tx-params")
async def get_tx_params(
    address: str = Query(...),
    network: str | None = Query(default=None),
    current_user: User = Depends(get_current_user),
) -> TxParamsResponse:
    """Get transaction parameters needed for client-side signing"""
    try:
        selected_network = resolve_network_or_400(network)
        client = get_client(network=selected_network)
        checksum_address = require_authenticated_wallet(current_user, address)

        # Get current nonce
        nonce_hex = await client._rpc_call("eth_getTransactionCount", [checksum_address, "pending"])
        nonce = int(nonce_hex, 16)
        
        # Get gas price
        gas_price_hex = await client._rpc_call("eth_gasPrice", [])
        
        rpc_url = client.rpc_url
        chain_id = client.chain_id
        
        return TxParamsResponse(
            chain_id=chain_id,
            gas_price=gas_price_hex,
            nonce=nonce,
            gas_limit=21000,
            rpc_url=rpc_url
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Failed to get transaction parameters: {str(e)}")
