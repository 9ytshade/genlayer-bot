# Submission Proof

No public GenLayer proof has been recorded for the current release. This document intentionally contains no placeholder hashes, addresses, or explorer links.

Add a proof entry only after a real validator-backed lifecycle completes:

| Field | Required evidence |
|---|---|
| Release commit | Exact Git commit deployed |
| Network / chain ID | Selected network and independently observed RPC chain ID |
| Contract / source hash | Final address and reviewed source hash |
| Deployment | EVM hash, GenLayer consensus ID, rounds, validators, votes, result, execution result |
| Action | Claim/evaluation/funding/settlement hashes and consensus IDs |
| Readback | Canonical final contract state matching the reviewed specification |
| Value movement | Triggered transfer ID and verified recipient/refund balance change, where applicable |
| Explorer | Direct public explorer link |

`FINALIZED` alone is insufficient. A successful Intelligent Contract write must show `FINISHED_WITH_RETURN` and canonical state readback.
