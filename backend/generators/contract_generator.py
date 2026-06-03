from __future__ import annotations

import re
from textwrap import dedent

from ..types.contract_spec import ContractSpec


def class_name(value: str) -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9_ ]", " ", value).strip()
    parts = [part for part in re.split(r"[\s_]+", cleaned) if part]
    name = "".join(part[:1].upper() + part[1:] for part in parts) or "GeneratedContract"
    if name[0].isdigit():
        name = f"Contract{name}"
    return name


class ContractGenerator:
    """Template-driven generator for GenLayer Intelligent Contracts."""

    def generate(self, spec: ContractSpec) -> str:
        generators = {
            "escrow": self._escrow,
            "conditional_payment": self._conditional_payment,
            "subscription": self._subscription,
            "dao_voting": self._dao_voting,
            "treasury": self._treasury,
            "bounty": self._bounty,
            "ai_arbitration": self._ai_arbitration,
        }
        return generators[spec.contract_type](spec).strip() + "\n"

    def _header(self, spec: ContractSpec) -> str:
        return dedent(
            f"""
            import genlayer as gl
            from genlayer.types import *


            class {class_name(spec.contract_name)}(gl.contract.Contract):
            """
        ).rstrip()

    def _escrow(self, spec: ContractSpec) -> str:
        return f"""{self._header(spec)}
    buyer: Address
    seller: Address
    buyer_approved: bool
    seller_approved: bool
    released: bool

    def __init__(self, buyer: Address, seller: Address):
        self.buyer = buyer
        self.seller = seller
        self.buyer_approved = False
        self.seller_approved = False
        self.released = False

    @gl.public.write
    def approve_release(self):
        if self.released:
            gl.vm.UserError.immediate("Escrow has already been released")
        if gl.message.sender_address == self.buyer:
            self.buyer_approved = True
        elif gl.message.sender_address == self.seller:
            self.seller_approved = True
        else:
            gl.vm.UserError.immediate("Only escrow participants can approve release")
        if self.buyer_approved and self.seller_approved:
            self.released = True
            return "Escrow release approved by both parties"
        return "Approval recorded"

    @gl.public.view
    def status(self) -> str:
        return f"buyer_approved={{self.buyer_approved}}, seller_approved={{self.seller_approved}}, released={{self.released}}"
"""

    def _conditional_payment(self, spec: ContractSpec) -> str:
        condition = (spec.payment_condition or spec.release_condition or "the requested condition is true").replace('"', "'")
        return f"""{self._header(spec)}
    payer: Address
    recipient: Address
    condition: str
    paid: bool

    def __init__(self, payer: Address, recipient: Address):
        self.payer = payer
        self.recipient = recipient
        self.condition = "{condition}"
        self.paid = False

    @gl.public.write
    def evaluate_and_mark_paid(self):
        if self.paid:
            gl.vm.UserError.immediate("Payment has already been marked complete")

        def task() -> str:
            prompt = f"Return TRUE only if this payment condition is satisfied: {{self.condition}}"
            return gl.nondet.exec_prompt(prompt)

        result = gl.eq_principle.strict_eq(task)
        if "TRUE" in result.upper():
            self.paid = True
            return "Condition satisfied. Payment can be released by the configured settlement layer."
        return "Condition not satisfied"

    @gl.public.view
    def payment_status(self) -> str:
        return f"condition={{self.condition}}, paid={{self.paid}}"
"""

    def _subscription(self, spec: ContractSpec) -> str:
        return f"""{self._header(spec)}
    owner: Address
    active: dict[Address, bool]

    def __init__(self, owner: Address):
        self.owner = owner
        self.active = {{}}

    @gl.public.write
    def subscribe(self):
        self.active[gl.message.sender_address] = True
        return "Subscription activated"

    @gl.public.write
    def cancel(self):
        self.active[gl.message.sender_address] = False
        return "Subscription cancelled"

    @gl.public.view
    def is_active(self, subscriber: Address) -> bool:
        return self.active.get(subscriber, False)
"""

    def _dao_voting(self, spec: ContractSpec) -> str:
        return f"""{self._header(spec)}
    owner: Address
    proposal_count: u256
    votes_for: dict[u256, u256]
    votes_against: dict[u256, u256]
    voted: dict[str, bool]

    def __init__(self, owner: Address):
        self.owner = owner
        self.proposal_count = 0
        self.votes_for = {{}}
        self.votes_against = {{}}
        self.voted = {{}}

    @gl.public.write
    def create_proposal(self) -> u256:
        self.proposal_count += 1
        self.votes_for[self.proposal_count] = 0
        self.votes_against[self.proposal_count] = 0
        return self.proposal_count

    @gl.public.write
    def vote(self, proposal_id: u256, support: bool):
        key = f"{{proposal_id}}:{{gl.message.sender_address}}"
        if self.voted.get(key, False):
            gl.vm.UserError.immediate("Address has already voted on this proposal")
        self.voted[key] = True
        if support:
            self.votes_for[proposal_id] = self.votes_for.get(proposal_id, 0) + 1
        else:
            self.votes_against[proposal_id] = self.votes_against.get(proposal_id, 0) + 1
        return "Vote recorded"
"""

    def _treasury(self, spec: ContractSpec) -> str:
        return f"""{self._header(spec)}
    owner: Address
    approved_spenders: dict[Address, bool]

    def __init__(self, owner: Address):
        self.owner = owner
        self.approved_spenders = {{}}

    @gl.public.write
    def approve_spender(self, spender: Address):
        if gl.message.sender_address != self.owner:
            gl.vm.UserError.immediate("Only owner can approve spenders")
        self.approved_spenders[spender] = True
        return "Spender approved"

    @gl.public.view
    def can_spend(self, spender: Address) -> bool:
        return self.approved_spenders.get(spender, False)
"""

    def _bounty(self, spec: ContractSpec) -> str:
        return f"""{self._header(spec)}
    issuer: Address
    winner: Address
    completed: bool
    description: str

    def __init__(self, issuer: Address, description: str):
        self.issuer = issuer
        self.winner = Address("0x0000000000000000000000000000000000000000")
        self.completed = False
        self.description = description

    @gl.public.write
    def accept_submission(self, submitter: Address, submission_summary: str):
        if gl.message.sender_address != self.issuer:
            gl.vm.UserError.immediate("Only issuer can accept bounty submissions")
        self.winner = submitter
        self.completed = True
        return f"Bounty completed: {{submission_summary}}"
"""

    def _ai_arbitration(self, spec: ContractSpec) -> str:
        issue = spec.description.replace('"', "'")
        return f"""{self._header(spec)}
    claimant: Address
    respondent: Address
    issue: str
    resolved: bool
    ruling: str

    def __init__(self, claimant: Address, respondent: Address):
        self.claimant = claimant
        self.respondent = respondent
        self.issue = "{issue}"
        self.resolved = False
        self.ruling = ""

    @gl.public.write
    def arbitrate(self, evidence: str):
        if self.resolved:
            gl.vm.UserError.immediate("Dispute has already been resolved")

        def task() -> str:
            prompt = f"Resolve this dispute fairly. Issue: {{self.issue}} Evidence: {{evidence}}"
            return gl.nondet.exec_prompt(prompt)

        self.ruling = gl.eq_principle.strict_eq(task)
        self.resolved = True
        return self.ruling
"""
