import pytest

from backend.genlayer_client import (
    EXECUTION_STATUS_FINISHED_WITH_ERROR,
    EXECUTION_STATUS_FINISHED_WITH_RETURN,
)
from backend.network_diagnostics import classify_diagnostic, diagnose_transaction


TX_ID = "0x" + "ab" * 32


class FakeClient:
    network = "studionet"
    chain_id = 61999

    async def _rpc_call(self, method, params):
        assert method == "eth_chainId"
        assert params == []
        return "0xf22f"

    async def get_consensus_transaction_status(self, tx_id):
        assert tx_id == TX_ID
        return {"status": "FINALIZED"}

    async def get_protocol_transaction_diagnostics(self, tx_id):
        assert tx_id == TX_ID
        return {
            "protocol_result": "NO_MAJORITY",
            "num_rounds": 0,
            "zero_round_no_majority": True,
            "transaction": {"last_round": {"round_validators": []}},
        }

    async def get_transaction_details(self, tx_id):
        return {"execution_status": "NOT_VOTED", "transaction": None}

    async def get_deployment_details(self, tx_id, transaction):
        return {"contract_address": None}


@pytest.mark.asyncio
async def test_zero_round_no_majority_is_an_external_availability_suspect():
    result = await diagnose_transaction(FakeClient(), TX_ID)

    assert result["rpc_reachable"] is True
    assert result["round_count"] == 0
    assert result["round_validator_count"] == 0
    assert result["classification"] == "SUSPECTED_HOSTED_VALIDATOR_OR_NETWORK_AVAILABILITY_BLOCKER"
    assert "contract-source failure" in result["messages"][0]


@pytest.mark.parametrize(
    ("summary", "classification"),
    [
        ({"rpc_reachable": False}, "RPC_OR_NETWORK_UNREACHABLE"),
        ({"rpc_reachable": True, "execution_result": EXECUTION_STATUS_FINISHED_WITH_RETURN}, "CONSENSUS_AND_GENVM_EXECUTION_SUCCEEDED"),
        ({"rpc_reachable": True, "execution_result": EXECUTION_STATUS_FINISHED_WITH_ERROR}, "GENVM_EXECUTION_FAILED"),
        ({"rpc_reachable": True, "status": "FINALIZED"}, "FINALIZED_EXECUTION_UNRESOLVED"),
    ],
)
def test_diagnostic_classification_distinguishes_finality_from_execution(summary, classification):
    assert classify_diagnostic(summary) == classification
