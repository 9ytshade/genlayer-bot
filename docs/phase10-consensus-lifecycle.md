# Consensus Lifecycle Persistence

Phase 10 separates wallet/EVM acceptance from GenLayer consensus and GenVM execution.

## Canonical records

`prepared_transactions` is the wallet-scoped execution-intent and lifecycle index. It stores:

- the reviewed transaction identity, EVM hash, and consensus transaction ID
- `lifecycle_status`, `evm_status`, `consensus_status`, and `execution_status`
- finality, terminal, and appealability flags
- protocol result, round count, validator count, vote count, and the zero-round `NO_MAJORITY` blocker
- a JSON diagnostic payload and the last consensus poll timestamp

`workflow_deployments` stores the same canonical lifecycle fields for deployment metadata and continues to expose the deployed contract only after finalized successful GenVM execution.

## Transitions

The confirmation path records `BROADCAST` immediately after exact RPC transaction verification. A successful EVM receipt becomes `CHAIN_ACCEPTED`; a consensus-bound deployment or call then becomes `CONSENSUS_PENDING`. Polling updates the canonical record to the protocol status and execution result. Finality is never inferred from the outer EVM receipt.

The same reviewed transaction hash can be submitted again for idempotent reconciliation for transfers, deployments, and contract calls. A hash belonging to a different prepared intent remains rejected.

## UI behavior

Chat history stores the lifecycle fields and renders EVM, GenLayer, and GenVM state separately. Browser reloads can recover a prepared transaction from its consensus ID or use the EVM hash to resolve a missing consensus ID without blindly resending.

## Evidence boundary

The local lifecycle fixtures pass. Studionet proof remains infrastructure-dependent; the recorded Phase 9 transaction ended with zero rounds, zero validators, and `NO_MAJORITY`, so it is not a successful consensus proof.
