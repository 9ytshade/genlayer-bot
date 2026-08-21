# Network Diagnostics

GenLayer Bot separates an EVM submission, consensus participation, GenVM execution, and final contract state. A transaction marked `FINALIZED` is not automatically a successful Intelligent Contract execution.

## Read-only transaction diagnostic

Run this without a private key or wallet signature:

```bash
python scripts/diagnose_genlayer_network.py \
  --network studionet \
  --tx-id 0x669ddac46123047ca1cc10d6f6f929c70cadca0a21b53177bb0a2e05bc3173d1
```

It prints JSON containing the selected and observed chain IDs, consensus status/result, execution result, rounds, validators, votes, contract address, triggered transactions, raw transaction data, and a conservative classification.

The historical Studionet transaction recorded `NO_MAJORITY`, zero rounds, and zero validators. This is classified as `SUSPECTED_HOSTED_VALIDATOR_OR_NETWORK_AVAILABILITY_BLOCKER`. It is evidence that no validator round occurred for that transaction; it is not proof of a platform-wide outage or a contract-source failure.

## Canary ladder

The pinned source lives in `contracts/canaries/`.

| Canary | What it isolates | Required success evidence |
|---|---|---|
| A — Storage | Basic validator activation and deterministic GenVM execution | validator round, non-empty validators, execution `FINISHED_WITH_RETURN`, contract address, state readback |
| B — Structured LLM | LLM provider and substantive equivalence | validator participation, bounded decision, successful execution and readback |
| C — Vision | Web rendering and actual screenshot-to-vision path | render, image passed to model, bounded result, independent validation, successful readback |

Run Canary A before changing any workflow contract. If it shows zero validators/rounds on hosted Studionet, stop retrying application deployments there. Run controlled diagnostics on Localnet, then use Bradbury for public proof when a funded test account is available.

## Direct Mode compatibility

Direct Mode is normally the free first layer. This repository does not currently run it because the published `genlayer-test==0.29.2` package requires `genlayer-py <0.17`, while the application deliberately pins `genlayer-py==0.18.0` for deployment-transaction compatibility. Installing the test package would downgrade the application SDK, so it is intentionally blocked rather than silently mutating the runtime. Resolve that version mismatch in a reviewed SDK migration or use a GenLayer-supported compatible test release before recording Direct Mode as passed.

## Controlled Localnet

Install the non-production test tools, then use the current GenLayer CLI:

```bash
pip install -r backend/requirements-dev.txt
genlayer init --numValidators 5
genlayer up --numValidators 5
```

Verify validator health in Studio before submitting Canary A. Localnet proves controlled multi-validator behavior; it is not public-network proof.

## Classification guide

- `LOCAL CONTRACT / TOOLCHAIN FAILURE`: Direct Mode canary fails.
- `LOCAL STUDIO / VALIDATOR CONFIGURATION FAILURE`: Direct Mode passes but five-validator Localnet Canary A fails.
- `SUSPECTED_HOSTED_VALIDATOR_OR_NETWORK_AVAILABILITY_BLOCKER`: a fresh hosted canary has `NO_MAJORITY`, zero rounds, and zero validators.
- `LLM / EQUIVALENCE / PROVIDER CAPABILITY FAILURE`: Canary A passes but B fails.
- `WEB RENDER / VISION CAPABILITY FAILURE`: Canary B passes but C fails.

Do not infer a stronger diagnosis than the captured transaction data supports.
