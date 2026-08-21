# Submission Proof

No public GenLayer proof has been recorded for the current release. The controlled Studio proof below is not a substitute for a public Studionet or Bradbury proof.

## Controlled Studio Canary A - recorded 2026-08-21

| Field | Recorded evidence |
|---|---|
| Release commit | `4818021` |
| Environment | GenLayer Studio, Normal (Full Consensus); chain ID was not captured in the Studio UI |
| Contract | `CanaryAStorage` at `0x8710710053432A39686D3828b2EBf01abFf5BA25` |
| Source SHA-256 | `14aff5063b1f92200ff4c623a5a0380a53971fdcf6b2f5fd56dc26c43242eed0` |
| Deployment transaction | `0x493c4ba18364095c98e2bfe921bf4e47188670c8e0c3022a93a68cecb28acc6c` - Studio reported `FINALIZED` / `SUCCESS`; four validator entries succeeded and agreed, one was cancelled after quorum |
| Increment transaction | `0xe5337782ef471967ad6ddce20dc5868413c0ed51f6ef7ef46f08366ac49350b2` - Studio reported `FINALIZED` / `SUCCESS`, output `1`; three validator entries succeeded and agreed, two were cancelled after quorum |
| Readback | `get_value()` returned `1` with Studio state `Accepted` |
| Not captured | Numeric round count, canonical RPC execution enum, raw receipt, and public explorer link |

This proves deterministic contract deployment, multi-validator consensus participation, a successful write, and canonical state readback in the recorded Studio environment. It does not prove an LLM path, screenshot/vision path, public-network operation, or settlement.

## Controlled Studio Canary B - recorded 2026-08-21

| Field | Recorded evidence |
|---|---|
| Release commit | `4818021` |
| Environment | GenLayer Studio, Normal (Full Consensus); chain ID was not captured in the Studio UI |
| Contract | `CanaryBStructuredLlm` at `0x3D720B21F7C025F71a6D6abC58495E51120aEB4b` |
| Source SHA-256 | `5b26c6f6bb16d3dadcf0f22b7dd208ffd8f639bd1e1c1591cc024e07f0d76ba9` |
| Deployment transaction | `0x576cf14af0bf3d7a6809f712610674ed43448659570ff8dafa8bbe6f4d9e081d` - Studio reported `FINALIZED` / `SUCCESS`; four validator entries succeeded, with one cancelled after quorum |
| Evaluate transaction | `0xfaaf360c562e4d6b1efd2017c161f6bd974193f2ae120eeac9460ae7d209bdd6` - Studio reported `FINALIZED` / `SUCCESS`, output `YES`; the equivalence-principle panel reported `{"decision":"YES"}`; three validator entries succeeded and agreed, with two cancelled after quorum |
| Readback | `get_decision()` returned `YES` with Studio state `Accepted` |
| Not captured | Numeric round count, canonical RPC execution enum, raw receipt, and public explorer link |

This proves the bounded LLM/equivalence path in the recorded Studio environment. It does not prove screenshot/vision, public-network operation, or settlement.

## Controlled Studio Canary C - recorded failure, 2026-08-21

| Field | Recorded evidence |
|---|---|
| Release commit | `4818021` |
| Environment | GenLayer Studio, Normal (Full Consensus); chain ID was not captured in the Studio UI |
| Contract | `CanaryCVision` at `0x378Ac533A7A883Ec2450550fa76Ac5984eC24C42` |
| Source SHA-256 | `3ff85d3550d8356f7830406a9d0f84e95d2931dcd2c633e04bdc3461c9a5f0d4` |
| Deployment transaction | `0x7d3a69bdc14658046913861a0c9270e7c1c2d45e0ea1083bab3943035a8b8590` - Studio showed `ACCEPTED` / `SUCCESS` at capture; successful validators agreed and one was cancelled after quorum |
| Evaluate transaction | `0x2ca323f15b50a7b34197382c7a496b7d921d4e4bcdf36fdf7f5cb896a53f4586` - Studio showed `FINALIZED` / `SUCCESS` and leader output `RENDERED`; equivalence output was `{"outcome":"RENDERED"}`, but consensus history showed three leader rotations then `Undetermined`, and several validators disagreed |
| Readback | `get_outcome()` returned `PENDING`, proving the state change was not accepted |
| Classification | `WEB RENDER / VISION CAPABILITY FAILURE` (more specifically: cross-validator vision/equivalence disagreement) |

The leader was able to render/evaluate the page, but the validator set did not reach agreement. `FINALIZED` and a leader result are not treated as a successful vision feature; Screenshot Verification remains disabled.

## Controlled Studio AI Notary - recorded 2026-08-21

| Field | Recorded evidence |
|---|---|
| Release commit | `4818021` |
| Environment | GenLayer Studio, Normal (Full Consensus); chain ID was not captured in the Studio UI |
| Registry contract | `AiNotaryRegistry` at `0x612946FdaD187F69b6E50E3a39E492965750845A` |
| Source SHA-256 | `26130015f726dff4003967c5d2483e5163bb9bcec8c52285f8833785f97f09b1` |
| Owner / claimant | `0xfB73b3b3C379A8ec184959F114d19481B891d54E` |
| Deployment transaction | `0xeed3fd55549f03c1a124041ea7790d9055cca04a2dc8d064842e783497aaa207` - Studio reported `FINALIZED` / `SUCCESS`; validators reached quorum |
| Claim submission | `0x1f7aa2dd3811691858a6122a41f524d13c125fed5743335671b3c5c3752be7f8` - Studio reported `FINALIZED` / `SUCCESS`; returned the submitted claim ID |
| Claim evaluation | `0x432d97f9d927169427f25de345a058700f96bb5e6b88dfce06663c299269014c` - Studio reported `FINALIZED` / `SUCCESS`, output `CONFIRMED`; consensus reached `Accepted` after leader rotations. Validators included both agreement and disagreement, with quorum accepting the bounded result. |
| Claim ID | `notary-fb73b3b3c379a8ec184959f114d19481b891d54e-000000000000000000000001` |
| Canonical readback | `evaluated: true`, `verdict: CONFIRMED`, `source_statuses: [USABLE]`, no failure reason, and stored statement/rubric/freshness/source URL matched the submitted review. Material facts were source-cited as `s1:`. |
| Not captured | Numeric round count, canonical RPC execution enum, raw receipt, and public explorer link |

This is a genuine controlled multi-validator proof of the text/web-evidence AI Notary lifecycle. It is not a public Studionet or Bradbury proof, and it does not enable the public feature.

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
