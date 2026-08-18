from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class NotarySpec:
    """Canonical public-evidence claim reviewed before any wallet transaction."""

    claim_id: str
    statement: str
    source_urls: tuple[str, ...]
    rubric: str
    freshness_rule: str
    # Keep the readiness state truthful until Studio/multi-validator, appeal,
    # and finality evidence is complete.
    product_status: str = "prototype"

    def as_dict(self) -> dict[str, Any]:
        return {
            "claim_id": self.claim_id,
            "statement": self.statement,
            "source_urls": list(self.source_urls),
            "rubric": self.rubric,
            "freshness_rule": self.freshness_rule,
            "product_status": self.product_status,
        }
