import pytest

from backend.contract_artifacts import (
    PINNED_DEPENDENCY_HEADER,
    PY_GENLAYER_DEPENDENCY,
    StaleContractReviewError,
    artifact_metadata,
    source_hash,
    verify_reviewed_source,
)
from backend.services.contract_generation_service import ContractGenerationService
from backend.services.workflow_service import generate_workflow_contract_code


def test_backend_generators_pin_the_documented_genvm_dependency():
    service = ContractGenerationService()
    service.client = None
    generated = service.generate("Create a subscription contract")
    workflow_code = generate_workflow_contract_code(
        {
            "workflowType": "bounty",
            "title": "Pinned runtime",
            "reward": 1,
            "token": "GEN",
        }
    )

    assert generated["ok"] is True
    assert generated["code"].splitlines()[0] == PINNED_DEPENDENCY_HEADER
    assert workflow_code.splitlines()[0] == PINNED_DEPENDENCY_HEADER
    assert generated["py_genlayer_dependency"] == PY_GENLAYER_DEPENDENCY
    assert generated["source_hash"] == source_hash(generated["code"])


def test_reviewed_source_hash_matches_exact_deployed_bytes():
    code = generate_workflow_contract_code(
        {
            "workflowType": "bounty",
            "title": "Exact bytes",
            "reward": 1,
            "token": "GEN",
        }
    )
    metadata = artifact_metadata(code, "workflow")

    verified = verify_reviewed_source(
        code=code,
        origin="workflow",
        reviewed_source_hash=str(metadata["source_hash"]),
        reviewed_py_genlayer_dependency=str(metadata["py_genlayer_dependency"]),
        reviewed_generator_version=str(metadata["generator_version"]),
        reviewed_validator_version=str(metadata["validator_version"]),
    )

    assert verified["source_hash"] == source_hash(code)


def test_template_change_invalidates_stale_review():
    code = generate_workflow_contract_code(
        {
            "workflowType": "bounty",
            "title": "Stale review",
            "reward": 1,
            "token": "GEN",
        }
    )
    metadata = artifact_metadata(code, "workflow")

    with pytest.raises(StaleContractReviewError, match="changed after review"):
        verify_reviewed_source(
            code=code + "\n",
            origin="workflow",
            reviewed_source_hash=str(metadata["source_hash"]),
            reviewed_py_genlayer_dependency=str(metadata["py_genlayer_dependency"]),
            reviewed_generator_version=str(metadata["generator_version"]),
            reviewed_validator_version=str(metadata["validator_version"]),
        )
