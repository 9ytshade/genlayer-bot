import pytest

from backend.services.contract_generation_service import ContractGenerationService


@pytest.mark.parametrize(
    ("request_text", "capability_code"),
    [
        ("Create an escrow contract", "generic_escrow_generation_rebuild_required"),
        ("Create an AI arbitration contract", "ai_arbitration_generation_rebuild_required"),
        ("Create a payment verified by live weather API data", "web_verified_payment_generation_rebuild_required"),
        ("Create a content moderation contract", "content_moderation_generation_rebuild_required"),
        ("Create a factory that can deploy child contracts", "contract_factory_generation_disabled"),
    ],
)
def test_unsafe_generic_contract_families_fail_closed(request_text: str, capability_code: str):
    service = ContractGenerationService()
    service.client = None

    result = service.generate(request_text)

    assert result["ok"] is False
    assert result["capabilityCode"] == capability_code
    assert result["errors"] == [result["message"]]


def test_safe_deterministic_counter_generation_remains_available():
    service = ContractGenerationService()
    service.client = None

    result = service.generate("Create a deterministic counter contract")

    assert result["ok"] is True
    assert result["contractType"] == "counter"
    assert result["validation"]["valid"] is True
