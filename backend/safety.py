import os
from typing import Any
from web3 import Web3

SUPPORTED_ACTIONS = {"transfer", "check_balance", "create_contract", "unknown"}


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

    elif action == "create_contract":
        intent["contract_type"] = str(raw_intent.get("contract_type", "custom")).strip().lower()
        intent["logic_description"] = str(raw_intent.get("logic_description", "")).strip()
        intent["condition"] = str(raw_intent.get("condition", "")).strip()
        
        amount = raw_intent.get("amount")
        if amount:
            try:
                intent["amount"] = float(amount)
            except (TypeError, ValueError):
                intent["amount"] = None
        
        recipient = raw_intent.get("recipient")
        if recipient:
            intent["recipient"] = str(recipient).strip()

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
            
    if intent.get("action") == "create_contract":
        if not intent.get("logic_description"):
            return False, "Contract logic description is missing."
        
        if intent.get("contract_type") in ["escrow", "conditional_payment"]:
            if not intent.get("amount") or intent.get("amount") <= 0:
                return False, f"Amount is required for {intent.get('contract_type')}."
            if not intent.get("recipient"):
                return False, f"Recipient is required for {intent.get('contract_type')}."
            if not Web3.is_address(intent.get("recipient")):
                return False, "Recipient address is invalid."
            
            if intent.get("contract_type") == "conditional_payment" and not intent.get("condition"):
                return False, "Condition is required for conditional payment."

    return True, ""
