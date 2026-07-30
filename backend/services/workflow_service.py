from __future__ import annotations

from typing import Any

from web3 import Web3


WORKFLOW_TYPES = {"conditional_payment", "escrow", "subscription", "bounty"}
PAYMENT_FREQUENCIES = {"daily", "weekly", "monthly", "yearly"}


class WorkflowValidationError(ValueError):
    pass


def _require_address(value: Any, label: str) -> str:
    if not isinstance(value, str) or not Web3.is_address(value):
        raise WorkflowValidationError(f"{label} must be a valid Ethereum address.")
    return Web3.to_checksum_address(value)


def _require_positive_number(value: Any, label: str) -> int:
    try:
        amount = float(value)
    except (TypeError, ValueError) as exc:
        raise WorkflowValidationError(f"{label} must be a positive number.") from exc
    if amount <= 0:
        raise WorkflowValidationError(f"{label} must be greater than 0.")
    return max(1, round(amount))


def _require_text(value: Any, label: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise WorkflowValidationError(f"{label} is required.")
    return text


def _base_config(config: dict[str, Any]) -> dict[str, Any]:
    token = str(config.get("token") or "GEN").strip().upper()
    if token != "GEN":
        raise WorkflowValidationError("Only GEN workflows are supported for the public MVP.")
    return {"token": token, "validated": True, "errors": []}


def validate_workflow_config(config: dict[str, Any], wallet_address: str | None = None) -> dict[str, Any]:
    workflow_type = str(config.get("workflowType") or config.get("workflow_type") or "").strip().lower()
    if workflow_type not in WORKFLOW_TYPES:
        raise WorkflowValidationError("Unsupported workflow type.")

    base = _base_config(config)

    if workflow_type == "conditional_payment":
        return {
            "workflowType": workflow_type,
            "recipient": _require_address(config.get("recipient"), "Recipient"),
            "amount": float(_require_positive_number(config.get("amount"), "Amount")),
            "condition": _require_text(config.get("condition"), "Condition"),
            **base,
        }

    if workflow_type == "escrow":
        buyer = config.get("buyer") or wallet_address
        seller = config.get("seller")
        normalized_buyer = _require_address(buyer, "Buyer")
        normalized_seller = _require_address(seller, "Seller")
        if normalized_buyer == normalized_seller:
            raise WorkflowValidationError("Buyer and seller must be different addresses.")
        return {
            "workflowType": workflow_type,
            "buyer": normalized_buyer,
            "seller": normalized_seller,
            "amount": float(_require_positive_number(config.get("amount"), "Amount")),
            "description": str(config.get("description") or "Escrow workflow").strip(),
            **base,
        }

    if workflow_type == "subscription":
        frequency = str(config.get("frequency") or "").strip().lower()
        if frequency not in PAYMENT_FREQUENCIES:
            raise WorkflowValidationError("Frequency must be daily, weekly, monthly, or yearly.")
        return {
            "workflowType": workflow_type,
            "recipient": _require_address(config.get("recipient"), "Recipient"),
            "amount": float(_require_positive_number(config.get("amount"), "Amount")),
            "frequency": frequency,
            "nextPaymentDate": config.get("nextPaymentDate"),
            **base,
        }

    return {
        "workflowType": workflow_type,
        "title": _require_text(config.get("title"), "Bounty title"),
        "reward": float(_require_positive_number(config.get("reward"), "Reward")),
        "description": str(config.get("description") or config.get("title") or "Bounty workflow").strip(),
        **base,
    }


def get_workflow_contract_name(config: dict[str, Any]) -> str:
    workflow_type = str(config.get("workflowType") or config.get("workflow_type") or "").strip().lower()
    return {
        "conditional_payment": "ConditionalPaymentContract",
        "escrow": "EscrowContract",
        "subscription": "SubscriptionContract",
        "bounty": "BountyContract",
    }[workflow_type]


def get_workflow_constructor_args(config: dict[str, Any], wallet_address: str) -> list[Any]:
    validated = validate_workflow_config(config, wallet_address)
    workflow_type = validated["workflowType"]
    if workflow_type == "conditional_payment":
        return [
            Web3.to_checksum_address(wallet_address),
            validated["recipient"],
            _require_positive_number(validated["amount"], "Amount"),
            validated["condition"],
            validated["token"],
        ]
    if workflow_type == "escrow":
        return [
            validated["buyer"],
            validated["seller"],
            _require_positive_number(validated["amount"], "Amount"),
            validated["token"],
            validated["description"],
        ]
    if workflow_type == "subscription":
        return [
            Web3.to_checksum_address(wallet_address),
            validated["recipient"],
            _require_positive_number(validated["amount"], "Amount"),
            validated["token"],
            validated["frequency"],
        ]
    return [
        Web3.to_checksum_address(wallet_address),
        validated["title"],
        _require_positive_number(validated["reward"], "Reward"),
        validated["token"],
        validated["description"],
    ]


def generate_workflow_contract_code(config: dict[str, Any]) -> str:
    workflow_type = validate_workflow_config(config)["workflowType"]
    return {
        "conditional_payment": CONDITIONAL_PAYMENT_TEMPLATE,
        "escrow": ESCROW_TEMPLATE,
        "subscription": SUBSCRIPTION_TEMPLATE,
        "bounty": BOUNTY_TEMPLATE,
    }[workflow_type].strip() + "\n"


WORKFLOW_ACTIONS: dict[str, dict[str, int]] = {
    "conditional_payment": {
        "mark_condition_satisfied": 0,
        "cancel_contract": 0,
    },
    "escrow": {
        "approve_release": 0,
        "raise_dispute": 0,
        "cancel_escrow": 0,
    },
    "subscription": {
        "record_payment": 0,
        "pause": 0,
        "resume": 0,
        "cancel": 0,
    },
    "bounty": {
        "review_submission": 1,
        "select_winner": 1,
        "close_bounty": 0,
    },
}


def validate_workflow_action(workflow_type: str, method: str, args: list[Any]) -> None:
    allowed = WORKFLOW_ACTIONS.get(workflow_type, {})
    if method not in allowed:
        raise WorkflowValidationError(f"Method '{method}' is not allowed for {workflow_type}.")
    expected_count = allowed[method]
    if len(args) != expected_count:
        raise WorkflowValidationError(f"Method '{method}' requires {expected_count} argument(s).")
    for arg in args:
        if isinstance(arg, str) and arg.startswith("0x") and not Web3.is_address(arg):
            raise WorkflowValidationError("Workflow action contains an invalid address argument.")


HEADER = """import genlayer as gl
from genlayer.types import *
"""

CONDITIONAL_PAYMENT_TEMPLATE = f"""{HEADER}

class ConditionalPaymentContract(gl.contract.Contract):
    payer: Address
    recipient: Address
    amount: u256
    condition: str
    token: str
    executed: bool
    cancelled: bool

    def __init__(self, payer: Address, recipient: Address, amount: u256, condition: str, token: str):
        self.payer = payer
        self.recipient = recipient
        self.amount = amount
        self.condition = condition
        self.token = token
        self.executed = False
        self.cancelled = False

    @gl.public.write
    def mark_condition_satisfied(self):
        if self.cancelled:
            gl.vm.UserError.immediate("Conditional payment is cancelled")
        if self.executed:
            gl.vm.UserError.immediate("Conditional payment already executed")
        self.executed = True
        return "Condition satisfied. Payment workflow marked executed."

    @gl.public.write
    def cancel_contract(self):
        if self.executed:
            gl.vm.UserError.immediate("Executed conditional payment cannot be cancelled")
        self.cancelled = True
        return "Conditional payment cancelled"

    @gl.public.view
    def status(self) -> str:
        return f"recipient={{self.recipient}}, amount={{self.amount}}, condition={{self.condition}}, executed={{self.executed}}, cancelled={{self.cancelled}}"
"""

ESCROW_TEMPLATE = f"""{HEADER}

class EscrowContract(gl.contract.Contract):
    buyer: Address
    seller: Address
    amount: u256
    token: str
    description: str
    released: bool
    disputed: bool
    cancelled: bool

    def __init__(self, buyer: Address, seller: Address, amount: u256, token: str, description: str):
        self.buyer = buyer
        self.seller = seller
        self.amount = amount
        self.token = token
        self.description = description
        self.released = False
        self.disputed = False
        self.cancelled = False

    @gl.public.write
    def approve_release(self):
        if self.cancelled or self.disputed or self.released:
            gl.vm.UserError.immediate("Escrow cannot be released in its current state")
        self.released = True
        return "Escrow release approved"

    @gl.public.write
    def raise_dispute(self):
        if self.released or self.cancelled:
            gl.vm.UserError.immediate("Escrow is already closed")
        self.disputed = True
        return "Escrow dispute raised"

    @gl.public.write
    def cancel_escrow(self):
        if self.released:
            gl.vm.UserError.immediate("Released escrow cannot be cancelled")
        self.cancelled = True
        return "Escrow cancelled"

    @gl.public.view
    def status(self) -> str:
        return f"buyer={{self.buyer}}, seller={{self.seller}}, amount={{self.amount}}, released={{self.released}}, disputed={{self.disputed}}, cancelled={{self.cancelled}}"
"""

SUBSCRIPTION_TEMPLATE = f"""{HEADER}

class SubscriptionContract(gl.contract.Contract):
    payer: Address
    recipient: Address
    amount: u256
    token: str
    frequency: str
    active: bool
    payment_count: u256

    def __init__(self, payer: Address, recipient: Address, amount: u256, token: str, frequency: str):
        self.payer = payer
        self.recipient = recipient
        self.amount = amount
        self.token = token
        self.frequency = frequency
        self.active = True
        self.payment_count = 0

    @gl.public.write
    def record_payment(self):
        if not self.active:
            gl.vm.UserError.immediate("Subscription is paused or cancelled")
        self.payment_count += 1
        return "Subscription payment recorded"

    @gl.public.write
    def pause(self):
        self.active = False
        return "Subscription paused"

    @gl.public.write
    def resume(self):
        self.active = True
        return "Subscription resumed"

    @gl.public.write
    def cancel(self):
        self.active = False
        return "Subscription cancelled"

    @gl.public.view
    def status(self) -> str:
        return f"recipient={{self.recipient}}, amount={{self.amount}}, frequency={{self.frequency}}, active={{self.active}}, payments={{self.payment_count}}"
"""

BOUNTY_TEMPLATE = f"""{HEADER}

class BountyContract(gl.contract.Contract):
    issuer: Address
    title: str
    description: str
    reward: u256
    token: str
    open: bool
    submission_count: u256
    winner: Address
    winner_selected: bool

    def __init__(self, issuer: Address, title: str, reward: u256, token: str, description: str):
        self.issuer = issuer
        self.title = title
        self.description = description
        self.reward = reward
        self.token = token
        self.open = True
        self.submission_count = 0
        self.winner = issuer
        self.winner_selected = False

    @gl.public.write
    def review_submission(self, submitter: Address):
        if not self.open:
            gl.vm.UserError.immediate("Bounty is closed")
        self.submission_count += 1
        return f"Submission reviewed for {{submitter}}"

    @gl.public.write
    def select_winner(self, winner: Address):
        if not self.open:
            gl.vm.UserError.immediate("Bounty is closed")
        self.winner = winner
        self.winner_selected = True
        self.open = False
        return "Bounty winner selected"

    @gl.public.write
    def close_bounty(self):
        self.open = False
        return "Bounty closed"

    @gl.public.view
    def status(self) -> str:
        return f"title={{self.title}}, reward={{self.reward}}, open={{self.open}}, submissions={{self.submission_count}}, winner_selected={{self.winner_selected}}"
"""
