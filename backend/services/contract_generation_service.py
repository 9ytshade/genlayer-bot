from __future__ import annotations

import json
import os
import re
from typing import Any

from dotenv import load_dotenv
from groq import Groq

from ..generators.contract_generator import ContractGenerator, class_name
from ..types.contract_spec import ContractSpec, ContractType
from ..validators.contract_validator import ContractValidator

load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), "..", ".env"))

SUPPORTED_TYPES: tuple[ContractType, ...] = (
    "escrow",
    "conditional_payment",
    "subscription",
    "dao_voting",
    "treasury",
    "bounty",
    "ai_arbitration",
)


class ContractGenerationService:
    def __init__(self):
        api_key = os.getenv("GROQ_API_KEY")
        self.client = Groq(api_key=api_key) if api_key else None
        self.generator = ContractGenerator()
        self.validator = ContractValidator()

    def generate(self, request_text: str, advanced: bool = False) -> dict[str, Any]:
        spec = self.build_specification(request_text, advanced=advanced)
        code = self.generator.generate(spec)
        validation = self.validator.validate(code)
        if not validation["valid"]:
            return {
                "ok": False,
                "message": "Unable to generate a valid GenLayer contract.",
                "errors": validation["errors"],
                "warnings": validation.get("warnings", []),
            }

        explanation = self.explain(spec)
        file_name = f"{class_name(spec.contract_name)}.py"
        return {
            "ok": True,
            "contractName": class_name(spec.contract_name),
            "contractType": spec.contract_type,
            "specification": spec.to_dict(),
            "explanation": explanation,
            "code": code,
            "fileName": file_name,
            "validation": validation,
        }

    def build_specification(self, request_text: str, advanced: bool = False) -> ContractSpec:
        if self.client:
            llm_spec = self._build_spec_with_llm(request_text, advanced)
            if llm_spec:
                return llm_spec
        return self._build_spec_heuristically(request_text, advanced)

    def _build_spec_with_llm(self, request_text: str, advanced: bool) -> ContractSpec | None:
        prompt = """
        Convert the user's request into a strict JSON contract specification.
        Do not generate Python code.
        Supported contractType values: escrow, conditional_payment, subscription, dao_voting, treasury, bounty, ai_arbitration.
        Fields: contractType, contractName, description, participants, releaseCondition, paymentCondition, amount, token, features.
        Use concise safe defaults when the user omits details.
        """
        tools = [
            {
                "type": "function",
                "function": {
                    "name": "build_contract_spec",
                    "description": "Build a structured GenLayer contract specification",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "contractType": {"type": "string", "enum": list(SUPPORTED_TYPES)},
                            "contractName": {"type": "string"},
                            "description": {"type": "string"},
                            "participants": {"type": "integer"},
                            "releaseCondition": {"type": "string"},
                            "paymentCondition": {"type": "string"},
                            "amount": {"type": "number"},
                            "token": {"type": "string"},
                            "features": {"type": "array", "items": {"type": "string"}},
                        },
                        "required": ["contractType", "contractName", "description"],
                    },
                },
            }
        ]
        try:
            response = self.client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[
                    {"role": "system", "content": prompt},
                    {"role": "user", "content": request_text},
                ],
                tools=tools,
                tool_choice={"type": "function", "function": {"name": "build_contract_spec"}},
                timeout=float(os.getenv("GROQ_TIMEOUT_SEC", "12")),
            )
            tool_calls = response.choices[0].message.tool_calls if response.choices else None
            if not tool_calls:
                return None
            data = json.loads(tool_calls[0].function.arguments)
            contract_type = data.get("contractType")
            if contract_type not in SUPPORTED_TYPES:
                return None
            return ContractSpec(
                contract_type=contract_type,
                contract_name=data.get("contractName") or f"{contract_type.title()}Contract",
                description=data.get("description") or request_text,
                participants=int(data.get("participants") or 1),
                release_condition=data.get("releaseCondition"),
                payment_condition=data.get("paymentCondition"),
                amount=data.get("amount"),
                token=(data.get("token") or "GEN").upper(),
                advanced=advanced,
                features=data.get("features") if isinstance(data.get("features"), list) else [],
                metadata={"source": "llm_specification"},
            )
        except Exception as exc:
            print(f"Error building contract spec with Groq: {exc}")
            return None

    def _build_spec_heuristically(self, request_text: str, advanced: bool) -> ContractSpec:
        text = request_text.lower()
        if "escrow" in text:
            ctype: ContractType = "escrow"
            name = "EscrowContract"
            condition = "mutual_approval"
            participants = 2
        elif "subscription" in text or "recurring" in text:
            ctype = "subscription"
            name = "SubscriptionContract"
            condition = "active_subscription"
            participants = 2
        elif "dao" in text or "voting" in text or "proposal" in text:
            ctype = "dao_voting"
            name = "DaoVotingContract"
            condition = "proposal_vote"
            participants = 1
        elif "treasury" in text:
            ctype = "treasury"
            name = "TreasuryContract"
            condition = "approved_spender"
            participants = 1
        elif "bounty" in text:
            ctype = "bounty"
            name = "BountyContract"
            condition = "accepted_submission"
            participants = 2
        elif "arbitration" in text or "dispute" in text or "arbiter" in text:
            ctype = "ai_arbitration"
            name = "AIArbitrationContract"
            condition = "ai_resolved_dispute"
            participants = 2
        else:
            ctype = "conditional_payment"
            name = "ConditionalPaymentContract"
            condition = request_text.strip() or "condition is satisfied"
            participants = 2

        amount_match = re.search(r"(\d+(?:\.\d+)?)\s*(?:gen|token|tokens)?", text)
        amount = float(amount_match.group(1)) if amount_match else None
        return ContractSpec(
            contract_type=ctype,
            contract_name=name,
            description=request_text.strip() or f"Generated {ctype} contract",
            participants=participants,
            release_condition=condition,
            payment_condition=condition if ctype == "conditional_payment" else None,
            amount=amount,
            token="GEN",
            advanced=advanced,
            features=[],
            metadata={"source": "heuristic_specification"},
        )

    def explain(self, spec: ContractSpec) -> str:
        fallback = {
            "escrow": "This contract acts as an escrow. Funds or obligations are considered releasable only after both configured parties approve.",
            "conditional_payment": "This contract records a conditional payment workflow and uses GenLayer consensus to evaluate whether the requested condition is satisfied.",
            "subscription": "This contract tracks active subscriptions and lets users subscribe or cancel their own status.",
            "dao_voting": "This contract supports proposal creation and one vote per address for each proposal.",
            "treasury": "This contract maintains a simple treasury approval list controlled by the owner.",
            "bounty": "This contract lets an issuer accept a bounty submission and record the winning submitter.",
            "ai_arbitration": "This contract uses GenLayer AI consensus to produce a dispute ruling from submitted evidence.",
        }[spec.contract_type]
        if not self.client:
            return fallback
        try:
            response = self.client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[
                    {"role": "system", "content": "Explain this GenLayer contract in one short paragraph. Do not include code."},
                    {"role": "user", "content": json.dumps(spec.to_dict())},
                ],
                timeout=float(os.getenv("GROQ_TIMEOUT_SEC", "12")),
            )
            return response.choices[0].message.content.strip() or fallback
        except Exception:
            return fallback
