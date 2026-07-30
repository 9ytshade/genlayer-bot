from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from web3 import Web3
import json
import os
from typing import Any

from ..auth import get_current_user, get_wallet_address_from_authorization
from ..contract_validation import validate_python_contract
from ..database import get_db
from ..genlayer_client import get_balance, get_client
from ..intent_parser import parse_intent
from ..logs_store import logs_store
from ..models import ChatHistory, User, WorkflowDeployment
from ..network_config import normalize_network
from ..rate_limit import limiter
from ..safety import normalize_intent, validate_intent
from ..services.contract_generation_service import ContractGenerationService
from ..services.workflow_service import (
    WorkflowValidationError,
    generate_workflow_contract_code,
    get_workflow_constructor_args,
    get_workflow_contract_name,
    validate_workflow_action,
    validate_workflow_config,
)
from ..simulator import simulate_intent

router = APIRouter(prefix="/chat", tags=["chat"])

HELP_MESSAGE = """Available commands:

help - Show this command list.
check balance - Check the connected wallet balance on the selected GenLayer network.
send tokens - Prepare a wallet-side GEN transfer. Example: Send 10 GEN to 0x...
deploy contract - Start contract deployment. Upload a .py GenLayer Intelligent Contract file when prompted.
new chat - Start a clean chat session from the left sidebar.
switch network - Use the network selector to switch between Studionet and Bradbury."""

contract_generation_service = ContractGenerationService()

class ChatRequest(BaseModel):
    message: str
    wallet_address: str | None = None
    network: str | None = None

class ConfirmRequest(BaseModel):
    intent: dict
    wallet_address: str | None = None
    signed_transaction: str | None = None  # Pre-signed raw transaction from user wallet
    tx_hash: str | None = None  # Transaction hash from wallet-side broadcast
    network: str | None = None


class TxParamsResponse(BaseModel):
    chain_id: int
    gas_price: str  # In hex
    nonce: int
    gas_limit: int
    rpc_url: str


class DeployTxRequest(BaseModel):
    address: str
    code: str
    constructor_args: list[Any] = Field(default_factory=list)
    constructor_kwargs: dict[str, Any] = Field(default_factory=dict)
    value_wei: str = "0"
    gas_limit: int | None = None
    consensus_max_rotations: int | None = None
    leader_only: bool = False
    network: str | None = None


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


class WorkflowDeployTxRequest(BaseModel):
    address: str
    workflow_config: dict[str, Any]
    value_wei: str = "0"
    gas_limit: int | None = None
    consensus_max_rotations: int | None = None
    leader_only: bool = False
    network: str | None = None


class WorkflowDeployTxResponse(DeployTxResponse):
    code: str
    contract_name: str
    constructor_args: list[Any]
    constructor_kwargs: dict[str, Any] = Field(default_factory=dict)
    workflow_config: dict[str, Any]


class ContractCallTxRequest(BaseModel):
    address: str
    contract_address: str
    method: str
    args: list[Any] = Field(default_factory=list)
    kwargs: dict[str, Any] = Field(default_factory=dict)
    value_wei: str = "0"
    gas_limit: int | None = None
    consensus_max_rotations: int | None = None
    leader_only: bool = False
    network: str | None = None
    workflow_type: str | None = None


class ContractValidationRequest(BaseModel):
    code: str
    file_name: str | None = None


class GenerateContractRequest(BaseModel):
    intent: dict
    network: str | None = None


class ContractValidationResponse(BaseModel):
    valid: bool
    message: str
    errors: list[str]
    warnings: list[str]
    contract_names: list[str] = Field(default_factory=list)


class ChatHistoryPayload(BaseModel):
    chats: list[dict[str, Any]] = Field(default_factory=list)
    currentChatId: str | None = None


def get_wallet_address(authorization: str | None = Header(None)) -> str | None:
    return get_wallet_address_from_authorization(authorization)


def get_optional_user_from_authorization(authorization: str | None, db: Session) -> User | None:
    wallet_address = get_wallet_address_from_authorization(authorization)
    if not wallet_address:
        return None
    return db.query(User).filter(User.connected_wallet_address == wallet_address).first()


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
        status="active" if contract_address else "deployed",
    )
    db.add(deployment)
    db.commit()


def persist_workflow_action(
    db: Session,
    user: User | None,
    intent: dict[str, Any],
    tx_hash: str,
) -> None:
    if not user:
        return
    contract_address = intent.get("contract_address")
    if not isinstance(contract_address, str):
        return
    deployment = (
        db.query(WorkflowDeployment)
        .filter(
            WorkflowDeployment.user_id == user.id,
            WorkflowDeployment.contract_address == Web3.to_checksum_address(contract_address),
        )
        .order_by(WorkflowDeployment.created_at.desc())
        .first()
    )
    if not deployment:
        return
    deployment.last_action = str(intent.get("method") or "")
    deployment.last_action_tx_hash = tx_hash
    deployment.status = str(intent.get("next_status") or deployment.status)
    db.commit()


def resolve_balance_address(header_address: str | None) -> str:
    if header_address:
        return header_address
    raise HTTPException(status_code=400, detail="No wallet address provided for balance lookup")


def resolve_network_or_400(network: str | None) -> str:
    try:
        return normalize_network(network)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


def is_deploy_contract_request(message: str) -> bool:
    normalized = " ".join(message.lower().strip().split())
    return normalized.startswith((
        "deploy contract",
        "deploy a contract",
        "deploy an intelligent contract",
        "upload contract",
        "upload a contract",
        "submit contract",
        "submit a contract",
    ))


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
    deployments = (
        db.query(WorkflowDeployment)
        .filter(WorkflowDeployment.user_id == current_user.id)
        .order_by(WorkflowDeployment.updated_at.desc())
        .all()
    )
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
            for deployment in deployments
        ]
    }


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
        await logs_store.append("INFO", "CONTRACT_REVIEW_PLACEHOLDER", "Contract review command requested.")
        return {
            "content": "Contract review is reserved for a future release. For now, you can generate a contract with /generate-contract or upload a .py file for deployment.",
            "intent": {"action": "contract_review", "status": "reserved"},
            "status": "awaiting_input",
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
            return {
                "content": "Unable to generate a valid GenLayer contract.",
                "intent": {"action": "generate_contract", "logic_description": generation_prompt, "advanced": advanced},
                "status": "error",
                "validation": {
                    "valid": False,
                    "errors": result.get("errors", []),
                    "warnings": result.get("warnings", []),
                },
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
            },
        }

    intent = normalize_intent(parse_intent(chat_request.message, chat_request.wallet_address))
    if intent.get("action") == "unknown" and is_deploy_contract_request(chat_request.message):
        intent = {"action": "deploy_contract"}

    if intent.get("action") == "deploy_contract" and intent.get("code"):
        validation = validate_python_contract(str(intent["code"]))
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
        await logs_store.append("INFO", "AWAIT_CONFIRMATION", "Awaiting confirmation for balance check.")
        return {
            "content": "I can check your wallet balance. Do you want me to proceed?",
            "intent": intent,
            "status": "awaiting_confirmation",
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
    authorization: str | None = Header(None),
    db: Session = Depends(get_db),
):
    intent = normalize_intent(request.intent)
    network = resolve_network_or_400(request.network)
    current_user = get_optional_user_from_authorization(authorization, db)
    await logs_store.append("INFO", "CONFIRM_RECEIVED", "Execution confirmed by user.", {"intent": intent, "network": network})

    is_safe, error_msg = validate_intent(intent)
    if intent.get("action") != "check_balance" and not is_safe:
        await logs_store.append("ERROR", "SAFETY_BLOCK_CONFIRM", "Confirmation blocked by safety checks.", {"reason": error_msg, "intent": intent})
        raise HTTPException(status_code=400, detail=f"Safety check failed: {error_msg}")

    if intent["action"] == "check_balance":
        balance_address = resolve_balance_address(request.wallet_address or get_wallet_address(authorization))
        try:
            balance = await get_balance(balance_address, network=network)
            await logs_store.append("SUCCESS", "BALANCE_SUCCESS", "Balance read succeeded.", {"balance": balance})
            return {"balance": balance}
        except Exception as e:
            await logs_store.append("ERROR", "BALANCE_FAILED", "Balance fetch failed.", {"error": str(e)})
            raise HTTPException(status_code=502, detail=f"Balance fetch failed: {str(e)}")

    if intent["action"] == "transfer":
        # Transfers are signed or broadcast by the connected user wallet on the frontend.
        # The backend only verifies a tx hash/raw signed transaction and never signs with a server key.
        if not request.signed_transaction and not request.tx_hash:
            raise HTTPException(status_code=400, detail="Transfer requires tx_hash or signed_transaction from user wallet")
        try:
            client = get_client(network=network)
            tx_hash = request.tx_hash or await client._rpc_call("eth_sendRawTransaction", [request.signed_transaction])
            await client._wait_for_receipt_or_raise(tx_hash)
            await logs_store.append("SUCCESS", "TRANSFER_SUCCESS", "Transfer broadcast succeeded.", {"txHash": tx_hash})
            return {"txHash": tx_hash}
        except Exception as e:
            await logs_store.append("ERROR", "TRANSFER_FAILED", "Transfer failed.", {"error": str(e), "intent": intent})
            raise HTTPException(status_code=502, detail=f"Transfer failed: {str(e)}")

    if intent["action"] == "deploy_contract":
        if not request.signed_transaction and not request.tx_hash:
            raise HTTPException(status_code=400, detail="Deploy requires tx_hash or signed_transaction from user wallet")
        try:
            await logs_store.append("INFO", "DEPLOY_START", "Starting contract deployment process...", {"contract_name": intent.get("contract_name", "MyContract")})
            await logs_store.append("INFO", "DEPLOY_COMPILING", "Compiling intelligent contract code...")
            await logs_store.append("INFO", "DEPLOY_ESTIMATING", "Estimating gas for deployment...")
            client = get_client(network=network)
            tx_hash = request.tx_hash or await client._rpc_call("eth_sendRawTransaction", [request.signed_transaction])
            await client._wait_for_receipt_or_raise(tx_hash)
            consensus_tx_id = await client.get_consensus_transaction_id(tx_hash)
            deployment_details = await client.get_deployment_details(consensus_tx_id)
            persist_workflow_deployment(
                db=db,
                user=current_user,
                intent=intent,
                network=network,
                tx_hash=tx_hash,
                consensus_tx_id=consensus_tx_id,
                contract_address=deployment_details["contract_address"],
            )
            await logs_store.append(
                "SUCCESS",
                "DEPLOY_SUCCESS",
                "Contract deployment transaction accepted by Studionet.",
                {
                    "txHash": tx_hash,
                    "consensusTxId": consensus_tx_id,
                    "contractAddress": deployment_details["contract_address"],
                    "derivedAddresses": deployment_details["derived_addresses"],
                },
            )
            return {
                "txHash": tx_hash,
                "consensusTxId": consensus_tx_id,
                "contractAddress": deployment_details["contract_address"],
                "derivedAddresses": deployment_details["derived_addresses"],
                "content": "Intelligent Contract deployment submitted to GenLayer Studionet.",
            }
        except Exception as e:
            await logs_store.append("ERROR", "DEPLOY_FAILED", "Deployment process failed.", {"error": str(e), "intent": intent})
            raise HTTPException(status_code=502, detail=f"Deployment failed: {str(e)}")

    if intent["action"] == "contract_call":
        if not request.signed_transaction and not request.tx_hash:
            raise HTTPException(status_code=400, detail="Contract call requires tx_hash or signed_transaction from user wallet")
        try:
            client = get_client(network=network)
            tx_hash = request.tx_hash or await client._rpc_call("eth_sendRawTransaction", [request.signed_transaction])
            await client._wait_for_receipt_or_raise(tx_hash)
            consensus_tx_id = await client.get_consensus_transaction_id(tx_hash)
            persist_workflow_action(db=db, user=current_user, intent=intent, tx_hash=tx_hash)
            await logs_store.append(
                "SUCCESS",
                "CONTRACT_CALL_SUCCESS",
                "Contract method transaction accepted by GenLayer.",
                {"txHash": tx_hash, "consensusTxId": consensus_tx_id, "method": intent.get("method")},
            )
            return {
                "txHash": tx_hash,
                "consensusTxId": consensus_tx_id,
                "content": "Workflow action submitted to GenLayer.",
            }
        except Exception as e:
            await logs_store.append("ERROR", "CONTRACT_CALL_FAILED", "Contract call failed.", {"error": str(e), "intent": intent})
            raise HTTPException(status_code=502, detail=f"Contract call failed: {str(e)}")

    await logs_store.append("ERROR", "UNSUPPORTED_ACTION", "Unsupported action during confirmation.", {"intent": intent})
    raise HTTPException(status_code=400, detail="Unsupported action for execution")


@router.post("/deploy-tx")
async def build_deploy_tx(request: DeployTxRequest) -> DeployTxResponse:
    """Build the Studionet consensus-contract transaction for wallet-side deployment."""
    try:
        network = resolve_network_or_400(request.network)
        client = get_client(network=network)
        checksum_address = Web3.to_checksum_address(request.address)
        value = int(request.value_wei or "0")
        if value < 0:
            raise ValueError("Deployment value cannot be negative")
        if request.gas_limit is not None and request.gas_limit < 21000:
            raise ValueError("Gas limit is too low")

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
        )
    except Exception as e:
        await logs_store.append("ERROR", "DEPLOY_TX_BUILD_FAILED", "Failed to prepare deployment transaction.", {"error": str(e)})
        raise HTTPException(status_code=502, detail=f"Failed to prepare deployment transaction: {str(e)}")


@router.post("/workflow-deploy-tx")
async def build_workflow_deploy_tx(request: WorkflowDeployTxRequest) -> WorkflowDeployTxResponse:
    """Build a deploy transaction from a trusted backend workflow template."""
    try:
        network = resolve_network_or_400(request.network)
        checksum_address = Web3.to_checksum_address(request.address)
        validated_config = validate_workflow_config(request.workflow_config, checksum_address)
        code = generate_workflow_contract_code(validated_config)
        constructor_args = get_workflow_constructor_args(validated_config, checksum_address)
        value = int(request.value_wei or "0")
        if value < 0:
            raise ValueError("Deployment value cannot be negative")

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
            contract_name=get_workflow_contract_name(validated_config),
            constructor_args=constructor_args,
            constructor_kwargs={},
            workflow_config=validated_config,
        )
    except WorkflowValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as e:
        await logs_store.append("ERROR", "WORKFLOW_DEPLOY_TX_BUILD_FAILED", "Failed to prepare workflow deployment.", {"error": str(e)})
        raise HTTPException(status_code=502, detail=f"Failed to prepare workflow deployment: {str(e)}")


@router.post("/contract-call-tx")
async def build_contract_call_tx(request: ContractCallTxRequest) -> DeployTxResponse:
    """Build a GenLayer consensus transaction for a deployed contract method call."""
    try:
        network = resolve_network_or_400(request.network)
        checksum_address = Web3.to_checksum_address(request.address)
        checksum_contract = Web3.to_checksum_address(request.contract_address)
        method = request.method.strip()
        if not method:
            raise ValueError("Method is required")
        if request.workflow_type:
            validate_workflow_action(request.workflow_type, method, request.args)
        value = int(request.value_wei or "0")
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
        )
    except WorkflowValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as e:
        await logs_store.append("ERROR", "CONTRACT_CALL_TX_BUILD_FAILED", "Failed to prepare contract call.", {"error": str(e)})
        raise HTTPException(status_code=502, detail=f"Failed to prepare contract call: {str(e)}")


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

    validation = validate_python_contract(request.code)
    await logs_store.append(
        "INFO" if validation["valid"] else "ERROR",
        "CONTRACT_VALIDATION",
        validation["message"],
        {"file_name": request.file_name, "errors": validation["errors"], "warnings": validation["warnings"]},
    )
    return ContractValidationResponse(**validation)


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
    }


@router.get("/tx-params")
async def get_tx_params(address: str = Query(...), network: str | None = Query(default=None)) -> TxParamsResponse:
    """Get transaction parameters needed for client-side signing"""
    try:
        selected_network = resolve_network_or_400(network)
        client = get_client(network=selected_network)
        checksum_address = Web3.to_checksum_address(address)

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
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Failed to get transaction parameters: {str(e)}")
