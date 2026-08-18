import pytest
from web3 import Web3
from genlayer_py.abi import calldata

from backend.genlayer_client import (
    EXECUTION_STATUS_FINISHED_WITH_ERROR,
    EXECUTION_STATUS_FINISHED_WITH_RETURN,
    EXECUTION_STATUS_NOT_VOTED,
    EXECUTION_STATUS_UNKNOWN,
    GenLayerClientWrapper,
)


@pytest.mark.asyncio
async def test_consensus_status_normalizes_named_status(monkeypatch):
    client = object.__new__(GenLayerClientWrapper)

    async def fake_rpc_call(method, params):
        assert method == "gen_getTransactionStatus"
        assert params == [{"txId": "0x" + "ab" * 32}]
        return {"status": "accepted", "statusCode": 5}

    monkeypatch.setattr(client, "_rpc_call", fake_rpc_call)

    result = await client.get_consensus_transaction_status("0x" + "ab" * 32)

    assert result == {
        "status": "ACCEPTED",
        "statusCode": 5,
        "final": False,
        "appealable": True,
        "terminal": False,
    }


@pytest.mark.asyncio
async def test_consensus_transaction_id_matches_prefixed_receipt_topics(monkeypatch):
    client = object.__new__(GenLayerClientWrapper)
    consensus_tx_id = "0x" + "ab" * 32
    event_topic = Web3.keccak(text="NewTransaction(bytes32,address,address)").hex()
    event_topic = event_topic if event_topic.startswith("0x") else f"0x{event_topic}"

    async def fake_rpc_call(method, params):
        assert method == "eth_getTransactionReceipt"
        assert params == ["0x" + "cd" * 32]
        return {"logs": [{"topics": [event_topic, consensus_tx_id]}]}

    monkeypatch.setattr(client, "_rpc_call", fake_rpc_call)

    assert await client.get_consensus_transaction_id("0x" + "cd" * 32) == consensus_tx_id


@pytest.mark.asyncio
async def test_consensus_status_normalizes_hex_status(monkeypatch):
    client = object.__new__(GenLayerClientWrapper)

    async def fake_rpc_call(_method, _params):
        return {"status": "0x7"}

    monkeypatch.setattr(client, "_rpc_call", fake_rpc_call)

    result = await client.get_consensus_transaction_status("0x" + "cd" * 32)

    assert result["status"] == "FINALIZED"
    assert result["statusCode"] == 7
    assert result["final"] is True
    assert result["terminal"] is True


@pytest.mark.asyncio
async def test_consensus_status_rejects_non_hex_identifier():
    client = object.__new__(GenLayerClientWrapper)

    with pytest.raises(ValueError, match="0x prefix"):
        await client.get_consensus_transaction_status("not-a-transaction")


@pytest.mark.parametrize(
    ("transaction", "expected"),
    [
        (
            {"tx_execution_result_name": "FINISHED_WITH_RETURN"},
            EXECUTION_STATUS_FINISHED_WITH_RETURN,
        ),
        (
            {"txExecutionResultName": "FINISHED_WITH_ERROR"},
            EXECUTION_STATUS_FINISHED_WITH_ERROR,
        ),
        (
            {"tx_execution_result_name": "NOT_VOTED"},
            EXECUTION_STATUS_NOT_VOTED,
        ),
        (
            {"consensus_data": {"leader_receipt": {"execution_result": "SUCCESS"}}},
            EXECUTION_STATUS_FINISHED_WITH_RETURN,
        ),
        (
            {"consensus_data": {"leader_receipt": [{"execution_result": "ERROR"}]}},
            EXECUTION_STATUS_FINISHED_WITH_ERROR,
        ),
        (
            {"consensusData": {"leaderReceipt": {"result": {"status": "FINISHED_WITH_RETURN"}}}},
            EXECUTION_STATUS_FINISHED_WITH_RETURN,
        ),
        ({}, EXECUTION_STATUS_UNKNOWN),
    ],
)
def test_execution_status_supports_documented_and_sdk_shapes(transaction, expected):
    assert GenLayerClientWrapper._extract_execution_status(transaction) == expected


@pytest.mark.asyncio
async def test_transaction_details_returns_execution_and_raw_transaction(monkeypatch):
    consensus_tx_id = "0x" + "ef" * 32
    transaction = {
        "consensus_data": {
            "leader_receipt": {
                "execution_result": "SUCCESS",
            }
        }
    }

    class FakeSdkClient:
        def get_transaction(self, transaction_id):
            assert transaction_id == consensus_tx_id
            return transaction

    import genlayer_py.client as sdk_client_module

    monkeypatch.setattr(
        sdk_client_module,
        "create_client",
        lambda chain, endpoint: FakeSdkClient(),
    )

    client = object.__new__(GenLayerClientWrapper)
    client.rpc_url = "https://example.invalid"
    monkeypatch.setattr(client, "_chain_config", lambda: object())

    result = await client.get_transaction_details(consensus_tx_id)

    assert result == {
        "execution_status": EXECUTION_STATUS_FINISHED_WITH_RETURN,
        "transaction": transaction,
    }


@pytest.mark.asyncio
async def test_deployment_details_only_returns_deployed_contract_addresses(monkeypatch):
    consensus_tx_id = "0x" + "12" * 32
    child_tx_id = "0x" + "34" * 32
    contract_address = Web3.to_checksum_address("0x" + "ab" * 20)
    child_address = Web3.to_checksum_address("0x" + "cd" * 20)
    sender_address = Web3.to_checksum_address("0x" + "11" * 20)
    validator_address = Web3.to_checksum_address("0x" + "22" * 20)

    transactions = {
        consensus_tx_id: {
            "sender": sender_address,
            "activator": validator_address,
            "last_round": {"round_validators": [validator_address]},
            "data": {"contract_address": contract_address},
            "triggered_transactions": [child_tx_id],
        },
        child_tx_id: {
            "sender": contract_address,
            "activator": validator_address,
            "tx_data_decoded": {
                "type": "deploy",
                "contract_address": child_address,
            },
        },
    }

    class FakeSdkClient:
        def get_transaction(self, transaction_id):
            return transactions[transaction_id]

    import genlayer_py.client as sdk_client_module

    monkeypatch.setattr(
        sdk_client_module,
        "create_client",
        lambda chain, endpoint: FakeSdkClient(),
    )

    client = object.__new__(GenLayerClientWrapper)
    client.rpc_url = "https://example.invalid"
    monkeypatch.setattr(client, "_chain_config", lambda: object())

    result = await client.get_deployment_details(consensus_tx_id)

    assert result == {
        "contract_address": contract_address,
        "derived_addresses": [child_address],
    }
    assert sender_address not in result["derived_addresses"]
    assert validator_address not in result["derived_addresses"]


@pytest.mark.asyncio
async def test_read_contract_uses_latest_final_state(monkeypatch):
    caller = Web3.to_checksum_address("0x" + "11" * 20)
    contract = Web3.to_checksum_address("0x" + "22" * 20)
    client = object.__new__(GenLayerClientWrapper)

    async def fake_rpc_call(method, params):
        assert method == "gen_call"
        request = params[0]
        assert request["type"] == "read"
        assert request["from"] == caller
        assert request["to"] == contract
        assert request["transaction_hash_variant"] == "latest-final"
        encoded = calldata.encode({"funded": True, "balance_wei": 10**18})
        return encoded.hex()

    monkeypatch.setattr(client, "_rpc_call", fake_rpc_call)

    result = await client.read_contract(caller, contract, "get_state")

    assert result == {"funded": True, "balance_wei": 10**18}


@pytest.mark.asyncio
async def test_protocol_transaction_diagnostics_detects_zero_round_no_majority(monkeypatch):
    consensus_tx_id = "0x" + "aa" * 32
    client = object.__new__(GenLayerClientWrapper)
    async def rpc_call(method, params):
        assert method == "eth_getTransactionByHash"
        assert params == [consensus_tx_id]
        return {"result_name": "NO_MAJORITY", "num_of_rounds": 0, "last_round": {"round_validators": []}}
    monkeypatch.setattr(client, "_rpc_call", rpc_call)
    result = await client.get_protocol_transaction_diagnostics(consensus_tx_id)
    assert result["protocol_result"] == "NO_MAJORITY"
    assert result["num_rounds"] == 0
    assert result["validator_count"] == 0
    assert result["zero_round_no_majority"] is True


@pytest.mark.asyncio
async def test_protocol_transaction_diagnostics_maps_numeric_result(monkeypatch):
    consensus_tx_id = "0x" + "bb" * 32
    client = object.__new__(GenLayerClientWrapper)
    async def rpc_call(method, params):
        return {"result": 5, "num_of_rounds": 0, "last_round": {"round_validators": []}}
    monkeypatch.setattr(client, "_rpc_call", rpc_call)
    result = await client.get_protocol_transaction_diagnostics(consensus_tx_id)
    assert result["protocol_result"] == "NO_MAJORITY"
