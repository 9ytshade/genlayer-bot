"""Read-only, evidence-first GenLayer transaction diagnostics."""

from __future__ import annotations

import json
from typing import Any

from .genlayer_client import (
    EXECUTION_STATUS_FINISHED_WITH_ERROR,
    EXECUTION_STATUS_FINISHED_WITH_RETURN,
    GenLayerClientWrapper,
)


def _as_int(value: Any) -> int | None:
    try:
        if isinstance(value, str):
            return int(value, 16) if value.lower().startswith("0x") else int(value)
        return int(value)
    except (TypeError, ValueError):
        return None


def _field(mapping: dict[str, Any], *names: str) -> Any:
    for name in names:
        value = mapping.get(name)
        if value not in (None, ""):
            return value
    return None


def _rounds(raw: Any) -> tuple[list[dict[str, Any]], str | None, str | None, int, int, int]:
    if not isinstance(raw, dict):
        return [], None, None, 0, 0, 0
    source = _field(raw, "rounds", "consensus_rounds", "consensusRounds")
    if not isinstance(source, list):
        last = _field(raw, "last_round", "lastRound")
        source = [last] if isinstance(last, dict) else []
    validators: set[str] = set()
    output: list[dict[str, Any]] = []
    committed = revealed = 0
    activator = _field(raw, "activator", "activator_address", "activatorAddress")
    leader = _field(raw, "leader", "leader_address", "leaderAddress")
    for index, item in enumerate(source, start=1):
        if not isinstance(item, dict):
            continue
        members = _field(item, "round_validators", "roundValidators")
        members = members if isinstance(members, list) else []
        validators.update(str(member) for member in members if member)
        round_committed = _as_int(_field(item, "votes_committed", "votesCommitted"))
        round_revealed = _as_int(_field(item, "votes_revealed", "votesRevealed"))
        votes = item.get("votes")
        if round_committed is None and isinstance(votes, (list, tuple, dict)):
            round_committed = len(votes)
        committed += round_committed or 0
        revealed += round_revealed or 0
        leader = leader or _field(item, "leader", "leader_address", "leaderAddress")
        output.append(
            {
                "index": index,
                "validator_count": len(members),
                "validators": [str(member) for member in members],
                "votes_committed": round_committed,
                "votes_revealed": round_revealed,
                "result": _field(item, "result_name", "resultName", "result"),
            }
        )
    return output, str(activator) if activator else None, str(leader) if leader else None, len(validators), committed, revealed


def classify_diagnostic(summary: dict[str, Any]) -> str:
    """Classify only what the observed transaction can establish."""
    if not summary.get("rpc_reachable"):
        return "RPC_OR_NETWORK_UNREACHABLE"
    if summary.get("consensus_result") == "NO_MAJORITY" and summary.get("round_count") == 0 and summary.get("round_validator_count") == 0:
        return "SUSPECTED_HOSTED_VALIDATOR_OR_NETWORK_AVAILABILITY_BLOCKER"
    if summary.get("execution_result") == EXECUTION_STATUS_FINISHED_WITH_RETURN:
        return "CONSENSUS_AND_GENVM_EXECUTION_SUCCEEDED"
    if summary.get("execution_result") == EXECUTION_STATUS_FINISHED_WITH_ERROR:
        return "GENVM_EXECUTION_FAILED"
    if summary.get("status") in {"VALIDATORS_TIMEOUT", "LEADER_TIMEOUT"}:
        return "VALIDATOR_OR_LEADER_TIMEOUT"
    if summary.get("status") == "UNDETERMINED":
        return "CONSENSUS_UNDETERMINED"
    if summary.get("status") == "FINALIZED":
        return "FINALIZED_EXECUTION_UNRESOLVED"
    return "CONSENSUS_PENDING_OR_INCOMPLETE"


async def diagnose_transaction(client: GenLayerClientWrapper, tx_id: str) -> dict[str, Any]:
    """Read a transaction without broadcasting or treating finality as success."""
    summary: dict[str, Any] = {
        "network": client.network, "chain_id": client.chain_id, "rpc_reachable": False,
        "tx_id": tx_id, "status": None, "consensus_result": None, "execution_result": None,
        "round_count": 0, "rounds": [], "activator": None, "leader": None,
        "round_validator_count": 0, "votes_committed": 0, "votes_revealed": 0,
        "rotations_left": None, "contract_address": None, "messages": [],
        "triggered_transaction_ids": [], "classification": None, "raw": {},
    }
    try:
        observed_chain = await client._rpc_call("eth_chainId", [])
        summary["rpc_reachable"] = True
        if (parsed_chain := _as_int(observed_chain)) is not None:
            summary["observed_chain_id"] = parsed_chain
            if parsed_chain != client.chain_id:
                summary["messages"].append("RPC chain ID differs from selected network configuration.")
        status = await client.get_consensus_transaction_status(tx_id)
        protocol = await client.get_protocol_transaction_diagnostics(tx_id)
        details = await client.get_transaction_details(tx_id)
        deployment = await client.get_deployment_details(tx_id, details.get("transaction"))
    except Exception as exc:
        summary["messages"].append(f"Diagnostic RPC/SDK read failed: {type(exc).__name__}: {exc}")
        summary["classification"] = classify_diagnostic(summary)
        return summary

    raw = protocol.get("transaction") or details.get("transaction") or {}
    rounds, activator, leader, validator_count, committed, revealed = _rounds(raw)
    triggered = _field(raw, "triggered_transactions", "triggered_transaction_ids", "triggeredTransactions") if isinstance(raw, dict) else None
    summary.update(
        {
            "status": status.get("status"), "consensus_result": protocol.get("protocol_result"),
            "execution_result": details.get("execution_status"),
            "round_count": protocol.get("num_rounds") if isinstance(protocol.get("num_rounds"), int) else len(rounds),
            "rounds": rounds, "activator": activator, "leader": leader,
            "round_validator_count": validator_count, "votes_committed": committed,
            "votes_revealed": revealed,
            "rotations_left": _as_int(_field(raw, "rotations_left", "rotationsLeft")) if isinstance(raw, dict) else None,
            "contract_address": deployment.get("contract_address"),
            "triggered_transaction_ids": [str(item) for item in triggered if item] if isinstance(triggered, (list, tuple, set)) else [],
            "raw": {"transaction": raw},
        }
    )
    if protocol.get("zero_round_no_majority"):
        summary["messages"].append("NO_MAJORITY with zero rounds and validators does not identify a contract-source failure.")
    summary["classification"] = classify_diagnostic(summary)
    return summary


def diagnostic_json(summary: dict[str, Any]) -> str:
    return json.dumps(summary, indent=2, sort_keys=True, default=str)
