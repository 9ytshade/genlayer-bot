from backend.generators.contract_generator import ContractGenerator
from backend.services.contract_review_service import ContractReviewService
from backend.types.contract_spec import ContractSpec


def test_contract_review_reports_structural_and_trust_model_findings():
    code = ContractGenerator().generate(
        ContractSpec(
            contract_type="counter",
            contract_name="CounterContract",
            description="A deterministic counter",
        )
    )

    result = ContractReviewService().review(code)

    assert result["verdict"] in {"READY", "READY_WITH_WARNINGS"}
    assert result["deploymentReady"] is True
    assert result["structural"]["contractNames"] == ["CounterContract"]
    assert "increment" in result["structural"]["publicMethods"]
    assert result["genlayer"]["requiredForBehavior"] is False


def test_contract_review_blocks_invalid_source_and_does_not_claim_readiness():
    result = ContractReviewService().review("class NotAContract: pass")

    assert result["verdict"] == "BLOCKED"
    assert result["deploymentReady"] is False
    assert result["blockingErrors"]
