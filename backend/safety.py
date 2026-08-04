import os
from typing import Any
from web3 import Web3

SUPPORTED_ACTIONS = {
    "transfer",
    "check_balance",
    "deploy_contract",
    "create_contract",
    "generate_contract",
    "contract_review",
    "contract_call",
    "conditional_payment",
    "escrow",
    "subscription",
    "bounty",
    "debug_trace",
    "appeal_transaction",
    "unknown",
}


def normalize_intent(raw_intent: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(raw_intent, dict):
        return {"action": "unknown"}

    action = str(raw_intent.get("action", "unknown")).strip().lower()
    if action not in SUPPORTED_ACTIONS:
        action = "unknown"

    intent: dict[str, Any] = {"action": action}

    if action == "transfer":
        amount = raw_intent.get("amount")
        try:
            intent["amount"] = float(amount) if amount is not None else None
        except (TypeError, ValueError):
            intent["amount"] = None

        token = str(raw_intent.get("token", "GEN")).strip().upper()
        intent["token"] = token or "GEN"
        recipient = raw_intent.get("recipient")
        intent["recipient"] = str(recipient).strip() if recipient is not None else None

    elif action in {"create_contract", "deploy_contract"}:
        intent["action"] = "deploy_contract"
        intent["contract_type"] = str(raw_intent.get("contract_type", "custom")).strip().lower()
        intent["contract_name"] = str(raw_intent.get("contract_name", "IntelligentContract")).strip() or "IntelligentContract"
        intent["logic_description"] = str(raw_intent.get("logic_description", "")).strip()
        intent["condition"] = str(raw_intent.get("condition", "")).strip()
        code = raw_intent.get("code")
        if code is not None:
            intent["code"] = str(code)

        constructor_args = raw_intent.get("constructor_args", raw_intent.get("args", []))
        intent["constructor_args"] = constructor_args if isinstance(constructor_args, list) else []

        constructor_kwargs = raw_intent.get("constructor_kwargs", raw_intent.get("kwargs", {}))
        intent["constructor_kwargs"] = constructor_kwargs if isinstance(constructor_kwargs, dict) else {}

        try:
            intent["deploy_value"] = float(raw_intent.get("deploy_value", raw_intent.get("value", 0)) or 0)
        except (TypeError, ValueError):
            intent["deploy_value"] = 0

        try:
            gas_limit = raw_intent.get("gas_limit")
            intent["gas_limit"] = int(gas_limit) if gas_limit else None
        except (TypeError, ValueError):
            intent["gas_limit"] = None

        try:
            rotations = raw_intent.get("consensus_max_rotations")
            intent["consensus_max_rotations"] = int(rotations) if rotations else None
        except (TypeError, ValueError):
            intent["consensus_max_rotations"] = None

        intent["leader_only"] = bool(raw_intent.get("leader_only", False))
        
        amount = raw_intent.get("amount")
        if amount:
            try:
                intent["amount"] = float(amount)
            except (TypeError, ValueError):
                intent["amount"] = None
        
        recipient = raw_intent.get("recipient")
        if recipient:
            intent["recipient"] = str(recipient).strip()

        workflow_config = raw_intent.get("workflow_config")
        if isinstance(workflow_config, dict):
            intent["workflow_config"] = workflow_config

    elif action == "generate_contract":
        intent["logic_description"] = str(raw_intent.get("logic_description", raw_intent.get("prompt", ""))).strip()
        intent["advanced"] = bool(raw_intent.get("advanced", False))
        contract_type = raw_intent.get("contract_type")
        if contract_type:
            intent["contract_type"] = str(contract_type).strip().lower()

    elif action == "contract_review":
        intent["status"] = "reserved"

    elif action == "contract_call":
        intent["contract_address"] = str(raw_intent.get("contract_address", "")).strip()
        intent["method"] = str(raw_intent.get("method", "")).strip()
        args = raw_intent.get("args", [])
        intent["args"] = args if isinstance(args, list) else []
        kwargs = raw_intent.get("kwargs", {})
        intent["kwargs"] = kwargs if isinstance(kwargs, dict) else {}
        workflow_type = raw_intent.get("workflow_type")
        if workflow_type:
            intent["workflow_type"] = str(workflow_type).strip().lower()
        next_status = raw_intent.get("next_status")
        if next_status:
            intent["next_status"] = str(next_status).strip().lower()

    elif action in {"conditional_payment", "escrow", "subscription", "bounty"}:
        token = str(raw_intent.get("token", "GEN")).strip().upper()
        intent["token"] = token or "GEN"
        if action in {"conditional_payment", "subscription"}:
            intent["recipient"] = str(raw_intent.get("recipient", "")).strip()
            try:
                intent["amount"] = float(raw_intent.get("amount") or 0)
            except (TypeError, ValueError):
                intent["amount"] = 0
        if action == "conditional_payment":
            intent["condition"] = str(raw_intent.get("condition", "")).strip()
        if action == "subscription":
            intent["frequency"] = str(raw_intent.get("frequency", "")).strip().lower()
        if action == "escrow":
            intent["buyer"] = str(raw_intent.get("buyer", "")).strip()
            intent["seller"] = str(raw_intent.get("seller", "")).strip()
            intent["description"] = str(raw_intent.get("description", "")).strip()
            try:
                intent["amount"] = float(raw_intent.get("amount") or 0)
            except (TypeError, ValueError):
                intent["amount"] = 0
        if action == "bounty":
            intent["title"] = str(raw_intent.get("title", "")).strip()
            intent["description"] = str(raw_intent.get("description", "")).strip()
            try:
                intent["reward"] = float(raw_intent.get("reward") or 0)
            except (TypeError, ValueError):
                intent["reward"] = 0

    elif action == "debug_trace":
        intent["tx_hash"] = str(raw_intent.get("tx_hash", "")).strip()

    elif action == "appeal_transaction":
        intent["tx_hash"] = str(raw_intent.get("tx_hash", "")).strip()
        intent["consensus_tx_id"] = str(raw_intent.get("consensus_tx_id", "")).strip()

    return intent


def validate_intent(intent: dict[str, Any]) -> tuple[bool, str]:
    if intent.get("action") == "unknown":
        return False, "Unknown intent."

    if intent.get("action") == "transfer":
        amount = intent.get("amount")
        if not amount or amount <= 0:
            return False, "Invalid transfer amount."

        max_amount = float(os.getenv("MAX_TRANSFER_AMOUNT", 1000))
        if amount > max_amount:
            return False, f"Transfer amount exceeds maximum limit of {max_amount} GEN."

        supported_tokens = os.getenv("SUPPORTED_TOKENS", "GEN").upper().split(",")
        supported_tokens = [token.strip() for token in supported_tokens if token.strip()]
        token = str(intent.get("token", "GEN")).upper()
        if token not in supported_tokens:
            return False, f"Unsupported token '{token}'. Supported tokens: {', '.join(supported_tokens)}."

        recipient = intent.get("recipient")
        if not recipient:
            return False, "Recipient address is missing."

        if not Web3.is_address(recipient):
            return False, "Recipient address is invalid."

        if recipient == "0x0000000000000000000000000000000000000000":
            return False, "Recipient cannot be the zero address."
            
    if intent.get("action") == "deploy_contract":
        if not intent.get("code") and not intent.get("logic_description"):
            return False, "Contract logic description is missing."

        if intent.get("deploy_value", 0) < 0:
            return False, "Deployment value cannot be negative."

        gas_limit = intent.get("gas_limit")
        if gas_limit is not None and gas_limit < 21000:
            return False, "Deployment gas limit is too low."
        
        # Template-generated or uploaded contracts already carry deployable code.
        # In that case constructor parameters are collected by the deploy UI, so
        # do not require natural-language payment fields like amount/recipient.
        if not intent.get("code") and intent.get("contract_type") in ["escrow", "conditional_payment"]:
            if not intent.get("amount") or intent.get("amount") <= 0:
                return False, f"Amount is required for {intent.get('contract_type')}."
            if not intent.get("recipient"):
                return False, f"Recipient is required for {intent.get('contract_type')}."
            if not Web3.is_address(intent.get("recipient")):
                return False, "Recipient address is invalid."
            
            if intent.get("contract_type") == "conditional_payment" and not intent.get("condition"):
                return False, "Condition is required for conditional payment."

    if intent.get("action") == "generate_contract":
        if not intent.get("logic_description"):
            return False, "Contract generation request is missing. Describe the contract you want to generate."

    if intent.get("action") == "contract_review":
        return False, "Contract review is reserved for a future release."

    if intent.get("action") == "contract_call":
        contract_address = intent.get("contract_address")
        if not contract_address:
            return False, "Contract address is missing."
        if not Web3.is_address(contract_address):
            return False, "Contract address is invalid."
        if not intent.get("method"):
            return False, "Contract method is missing."

    if intent.get("action") in {"conditional_payment", "escrow", "subscription", "bounty"}:
        try:
            from .services.workflow_service import WorkflowValidationError, validate_workflow_config

            workflow_config = {"workflowType": intent["action"], **intent}
            validate_workflow_config(workflow_config, intent.get("buyer"))
        except WorkflowValidationError as exc:
            return False, str(exc)

    if intent.get("action") == "debug_trace":
        if not intent.get("tx_hash"):
            return False, "Transaction hash is required for debug trace."

    if intent.get("action") == "appeal_transaction":
        if not intent.get("tx_hash") and not intent.get("consensus_tx_id"):
            return False, "Transaction hash or consensus transaction ID is required for appeal."

    return True, ""
