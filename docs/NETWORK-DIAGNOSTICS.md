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

## Recorded controlled Studio result

On 2026-08-21, `CanaryAStorage` was deployed in Studio Normal (Full Consensus) mode at `0x8710710053432A39686D3828b2EBf01abFf5BA25`. The deployment transaction `0x493c4ba18364095c98e2bfe921bf4e47188670c8e0c3022a93a68cecb28acc6c` and write transaction `0xe5337782ef471967ad6ddce20dc5868413c0ed51f6ef7ef46f08366ac49350b2` both showed `FINALIZED` / `SUCCESS` in Studio. The deployment panel showed four agreeing successful validators and one quorum-cancelled validator; the increment panel showed three agreeing successful validators and two quorum-cancelled validators. `get_value()` returned `1`.

This establishes controlled Studio validator participation and deterministic execution. The UI evidence does not expose a numeric round count or the canonical RPC execution enum, and it is not public-network proof. The full record is in [Submission Proof](SUBMISSION-PROOF.md).

`CanaryBStructuredLlm` then passed the bounded LLM/equivalence layer in the same environment. Its evaluate transaction `0xfaaf360c562e4d6b1efd2017c161f6bd974193f2ae120eeac9460ae7d209bdd6` showed `FINALIZED` / `SUCCESS`, output `YES`, and equivalence output `{"decision":"YES"}`; `get_decision()` returned `YES`. This isolates the next diagnostic step to web-rendering and vision capability, not general consensus or basic LLM equivalence.

Canary C then established that this isolation matters: the leader produced `RENDERED`, but the consensus history on `0x2ca323f15b50a7b34197382c7a496b7d921d4e4bcdf36fdf7f5cb896a53f4586` had multiple leader rotations and ended `Undetermined` with validator disagreements. `get_outcome()` remained `PENDING`, so the write did not reach accepted state. Treat this as a web-render/vision equivalence failure, not as proof that the screenshot feature works.

The same Studio environment completed the canonical AI Notary text/web-evidence path: registry deployment, claim submission, evaluator consensus to `CONFIRMED`, and a stored claim record with `evaluated: true` and `source_statuses: [USABLE]`. This confirms that ordinary text web retrieval and the bounded Notary equivalence rule can reach accepted consensus even though screenshot/vision agreement cannot yet. See [Submission Proof](SUBMISSION-PROOF.md).

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
