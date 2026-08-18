from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class DisabledCapability:
    code: str
    message: str


SCREENSHOT_VERIFICATION = DisabledCapability(
    code="screenshot_verification_unproven",
    message=(
        "Screenshot verification is unavailable until the exact rendered-image path is "
        "validated against the pinned GenVM runtime and proven on Studionet."
    ),
)

APPEAL_SUBMISSION = DisabledCapability(
    code="appeal_submission_unproven",
    message=(
        "Appeal submission is unavailable until a real appeal round and post-window "
        "finality are proven on Studionet. Appealability metadata remains read-only."
    ),
)

WORKFLOW_REBUILD_REQUIRED: dict[str, DisabledCapability] = {
    "conditional_payment": DisabledCapability(
        code="conditional_payment_rebuild_required",
        message=(
            "New conditional-payment deployment and settlement are unavailable until "
            "GenLayer evidence evaluation, structured abstention, and deterministic custody "
            "settlement are implemented and proven."
        ),
    ),
    "bounty": DisabledCapability(
        code="bounty_rebuild_required",
        message=(
            "New bounty deployment and winner selection are unavailable until validators, "
            "rather than the issuer or backend, judge qualitative completion."
        ),
    ),
}

GENERATION_REBUILD_REQUIRED: dict[str, DisabledCapability] = {
    "escrow": DisabledCapability(
        code="generic_escrow_generation_rebuild_required",
        message=(
            "Generic escrow contract generation is unavailable because the legacy template "
            "records approval without transferring escrowed GEN. Use the guided escrow workflow instead."
        ),
    ),
    "ai_arbitration": DisabledCapability(
        code="ai_arbitration_generation_rebuild_required",
        message=(
            "AI arbitration contract generation is unavailable until validator output uses a bounded, "
            "structured ruling schema with an explicit insufficient-evidence outcome."
        ),
    ),
    "web_verified_payment": DisabledCapability(
        code="web_verified_payment_generation_rebuild_required",
        message=(
            "Web-verified payment generation is unavailable until the template compiles, validates "
            "structured evidence, supports abstention, and deterministically transfers escrowed GEN."
        ),
    ),
    "content_moderation": DisabledCapability(
        code="content_moderation_generation_rebuild_required",
        message=(
            "Content-moderation contract generation is unavailable until the template compiles and "
            "validates a bounded structured moderation decision before persisting it."
        ),
    ),
    "contract_factory": DisabledCapability(
        code="contract_factory_generation_disabled",
        message=(
            "Arbitrary contract-factory generation is disabled because accepting caller-supplied child "
            "source bypasses the reviewed artifact and deployment safety boundary."
        ),
    ),
}


def disabled_generation_capability(contract_type: str) -> DisabledCapability | None:
    if contract_type == "screenshot_verification":
        return SCREENSHOT_VERIFICATION
    normalized_type = contract_type.strip().lower()
    return GENERATION_REBUILD_REQUIRED.get(normalized_type) or WORKFLOW_REBUILD_REQUIRED.get(normalized_type)


def disabled_workflow_capability(workflow_type: str) -> DisabledCapability | None:
    return WORKFLOW_REBUILD_REQUIRED.get(workflow_type.strip().lower())
