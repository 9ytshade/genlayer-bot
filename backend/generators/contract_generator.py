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
            "web_verified_payment": self._web_verified_payment,
            "screenshot_verification": self._screenshot_verification,
            "content_moderation": self._content_moderation,
            "contract_factory": self._contract_factory,
        }
        return generators[spec.contract_type](spec).strip() + "\n"

    def _header(self, spec: ContractSpec) -> str:
        return dedent(
            f"""
            # {{ "Depends": "py-genlayer:test" }}
            from genlayer import *


            class {class_name(spec.contract_name)}(gl.Contract):
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

    @gl.public.write.payable
    def __receive__(self):
        pass

    @gl.public.write
    def approve_release(self):
        if self.released:
            raise gl.vm.UserError("Escrow has already been released")
        if gl.message.sender_address == self.buyer:
            self.buyer_approved = True
        elif gl.message.sender_address == self.seller:
            self.seller_approved = True
        else:
            raise gl.vm.UserError("Only escrow participants can approve release")
        if self.buyer_approved and self.seller_approved:
            self.released = True
            return "Escrow release approved by both parties"
        return "Approval recorded"

    @gl.public.view
    def get_balance(self) -> u256:
        return self.balance

    @gl.public.view
    def status(self) -> str:
        return f"buyer_approved={{self.buyer_approved}}, seller_approved={{self.seller_approved}}, released={{self.released}}, balance={{self.balance}}"
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
            raise gl.vm.UserError("Payment has already been marked complete")

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
    active: TreeMap[Address, bool]

    def __init__(self, owner: Address):
        self.owner = owner
        self.active = TreeMap()

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
    votes_for: TreeMap[u256, u256]
    votes_against: TreeMap[u256, u256]
    voted: TreeMap[str, bool]

    def __init__(self, owner: Address):
        self.owner = owner
        self.proposal_count = 0
        self.votes_for = TreeMap()
        self.votes_against = TreeMap()
        self.voted = TreeMap()

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
            raise gl.vm.UserError("Address has already voted on this proposal")
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
    approved_spenders: TreeMap[Address, bool]

    def __init__(self, owner: Address):
        self.owner = owner
        self.approved_spenders = TreeMap()

    @gl.public.write
    def approve_spender(self, spender: Address):
        if gl.message.sender_address != self.owner:
            raise gl.vm.UserError("Only owner can approve spenders")
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
            raise gl.vm.UserError("Only issuer can accept bounty submissions")
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
            raise gl.vm.UserError("Dispute has already been resolved")

        principle = "The rulings must reach the same conclusion and assign responsibility to the same party, even if worded differently."

        def task() -> str:
            prompt = f"Resolve this dispute fairly. Issue: {{self.issue}} Evidence: {{evidence}}"
            return gl.nondet.exec_prompt(prompt)

        self.ruling = gl.eq_principle.prompt_comparative(task, principle)
        self.resolved = True
        return self.ruling
"""

    def _web_verified_payment(self, spec: ContractSpec) -> str:
        condition = (spec.payment_condition or spec.release_condition or "the API returns a truthy value").replace('"', "'")
        api_url = (spec.metadata.get("api_url") or "https://api.example.com/status").replace('"', "'")
        return f"""{self._header(spec)}
    payer: Address
    recipient: Address
    api_url: str
    condition: str
    paid: bool

    def __init__(self, payer: Address, recipient: Address, api_url: str, condition: str):
        self.payer = payer
        self.recipient = recipient
        self.api_url = api_url
        self.condition = condition
        self.paid = False

    @gl.public.write
    def verify_and_pay(self):
        if self.paid:
            raise gl.vm.UserError("Payment has already been released")

        def task() -> str:
            response = gl.nondet.web.get(self.api_url)
            result = gl.nondet.exec_prompt(
                f"Given this API response: {{response.body}}\n\nIs this condition satisfied: {{self.condition}}\nReturn a JSON object with keys 'satisfied' (bool) and 'reason' (string).",
                response_format="json",
            )
            return result

        result = gl.eq_principle.strict_eq(task)
        if result.get("satisfied", False):
            self.paid = True
            return f"Condition verified via live API. Payment released. Reason: {{result.get('reason', 'Condition met')}}"
        return f"Condition not yet satisfied. Reason: {{result.get('reason', 'Condition not met')}}"

    @gl.public.view
    def status(self) -> str:
        return f"api_url={{self.api_url}}, condition={{self.condition}}, paid={{self.paid}}"
"""

    def _screenshot_verification(self, spec: ContractSpec) -> str:
        criteria = (spec.description or "the page content matches the expected state").replace('"', "'")
        return f"""{self._header(spec)}
    verifier: Address
    target_url: str
    criteria: str
    verified: bool
    result: str

    def __init__(self, verifier: Address, target_url: str, criteria: str):
        self.verifier = verifier
        self.target_url = target_url
        self.criteria = criteria
        self.verified = False
        self.result = ""

    @gl.public.write
    def verify_screenshot(self):
        if self.verified:
            raise gl.vm.UserError("Verification has already been completed")

        principle = "Both results must agree on whether the page content meets the stated criteria, even if the exact wording differs."

        def task() -> str:
            screenshot = gl.nondet.web.render(self.target_url, mode="screenshot")
            return gl.nondet.exec_prompt(
                f"Analyze this screenshot of {{self.target_url}}. Does it satisfy this criteria: {{self.criteria}}? Provide your verdict as PASS or FAIL with a brief explanation.",
                images=[screenshot],
            )

        self.result = gl.eq_principle.prompt_non_comparative(
            input=self.target_url,
            task="Render screenshot and evaluate against criteria",
            criteria=f"The assessment must correctly determine if the page satisfies: {{self.criteria}}",
        )
        self.verified = True
        return self.result

    @gl.public.view
    def status(self) -> str:
        return f"url={{self.target_url}}, criteria={{self.criteria}}, verified={{self.verified}}"
"""

    def _content_moderation(self, spec: ContractSpec) -> str:
        guidelines = (spec.description or "content must be respectful, factual, and free of hate speech").replace('"', "'")
        return f"""{self._header(spec)}
    moderator: Address
    guidelines: str
    moderation_count: u256
    decisions: TreeMap[u256, str]

    def __init__(self, moderator: Address, guidelines: str):
        self.moderator = moderator
        self.guidelines = guidelines
        self.moderation_count = u256(0)
        self.decisions = TreeMap()

    @gl.public.write
    def moderate(self, content: str):
        principle = "Both moderators must agree on whether the content is approved or rejected, even if their reasoning differs."

        def task() -> str:
            return gl.nondet.exec_prompt(
                f"You are a content moderator. Review this content against these guidelines:\n\nGuidelines: {{self.guidelines}}\n\nContent to review: {{content}}\n\nReturn a JSON object with keys: 'decision' ('approved' or 'rejected'), 'reason' (string), 'severity' ('none', 'low', 'medium', 'high').",
                response_format="json",
            )

        result = gl.eq_principle.prompt_comparative(task, principle)
        self.moderation_count += 1
        self.decisions[self.moderation_count] = f"{{result.get('decision', 'unknown')}}: {{result.get('reason', 'no reason')}}"
        return result

    @gl.public.view
    def get_decision(self, decision_id: u256) -> str:
        if decision_id not in self.decisions:
            raise gl.vm.UserError("Decision not found")
        return self.decisions[decision_id]

    @gl.public.view
    def status(self) -> str:
        return f"guidelines={{self.guidelines}}, total_moderations={{self.moderation_count}}"
"""

    def _contract_factory(self, spec: ContractSpec) -> str:
        return f"""{self._header(spec)}
    child_contracts: DynArray[str]

    def __init__(self):
        self.child_contracts = DynArray[str]()

    @gl.public.write
    def deploy_child(self, child_code: str, *args) -> str:
        address = gl.deploy_contract(child_code, args=list(args))
        self.child_contracts.append(str(address))
        return str(address)

    @gl.public.view
    def get_child_count(self) -> int:
        return len(self.child_contracts)

    @gl.public.view
    def get_child_address(self, index: int) -> str:
        if index < 0 or index >= len(self.child_contracts):
            raise gl.vm.UserError("Index out of range")
        return self.child_contracts[index]
"""


