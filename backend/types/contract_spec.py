from dataclasses import dataclass, field
from typing import Any, Literal


ContractType = Literal[
    "escrow",
    "conditional_payment",
    "subscription",
    "dao_voting",
    "treasury",
    "bounty",
    "ai_arbitration",
    "web_verified_payment",
    "screenshot_verification",
    "content_moderation",
    "contract_factory",
]


@dataclass
class ContractSpec:
    contract_type: ContractType
    contract_name: str
    description: str
    participants: int = 1
    release_condition: str | None = None
    payment_condition: str | None = None
    amount: float | None = None
    token: str = "GEN"
    advanced: bool = False
    features: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "contractType": self.contract_type,
            "contractName": self.contract_name,
            "description": self.description,
            "participants": self.participants,
            "releaseCondition": self.release_condition,
            "paymentCondition": self.payment_condition,
            "amount": self.amount,
            "token": self.token,
            "advanced": self.advanced,
            "features": self.features,
            "metadata": self.metadata,
        }
