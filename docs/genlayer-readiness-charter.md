# GenLayer Readiness and Feature Research Charter

**Status:** Draft baseline for review
**Scope:** Existing GenLayer Bot behavior and all future Intelligent Contract work
**Source boundary:** The supplied official GenLayer documentation snapshot and the current repository only

## Purpose

This charter is the decision boundary for optimizing the existing application and researching new features. No new Ideas-page feature is implemented until the readiness gates and the feature research record are complete.

The application may expose ordinary wallet and EVM operations, but any behavior described as an Intelligent Contract workflow must be correct under GenLayer's consensus, transaction, value, and finality model. A wallet receipt or RPC submission acknowledgment is not presented as GenLayer success.

## Protocol Invariants

1. **Intelligent Contract purpose.** Use an Intelligent Contract for consensus-backed judgment over non-deterministic inputs such as language, web data, APIs, images, or other external information.
2. **Explicit equivalence.** Every non-deterministic operation defines equivalent outcomes, comparative/non-comparative validation, and borderline handling.
3. **Optimistic Democracy.** A leader, model, backend response, or EVM receipt is not authoritative; validators independently evaluate and reach consensus.
4. **Lifecycle-aware UX.** Represent `pending`, `proposing`, `committing`, `revealing`, `accepted`, `appealable`, `finalized`, `undetermined`, and `canceled` (or exact network statuses). `accepted` is provisional; `finalized` is irreversible after the appeal window.
5. **Appeals are part of correctness.** Define appellant, bond/gas, appeal window, successful/failed transitions, and final outcome.
6. **Value follows the protocol.** GEN uses wei, is attached to the reviewed transaction, and is held/transferred by the intended account or ghost contract. UI state is not proof of funding.
7. **Prove GenVM behavior.** Validate with GenVM-compatible tooling and GenLayer Studio or equivalent local multi-validator tests.
8. **Make evidence inspectable.** Declare web/API/LLM/image sources, parsing, freshness, provenance, and failure behavior.
9. **Make authorization explicit.** Bind builders, confirmations, appeals, administration, and private records to the authenticated wallet and exact reviewed destination, calldata, value, and chain.
10. **Avoid legal overclaims.** Product copy describes protocol adjudication and does not imply automatic legal enforceability.

## Existing Feature Classification

- **Operational, subject to lifecycle fixes:** wallet connection, network selection, balance reads, and ordinary wallet-side GEN transfers.
- **Experimental and not production-safe:** conditional payments, escrow, subscriptions, and bounties. They do not yet prove custody/value movement, consensus adjudication, authorization, or truthful state.
- **Deployment path under hardening:** validation, transaction construction, receipt polling, and results must distinguish submission from consensus and finality.
- **Observability under hardening:** logs are sensitive wallet-scoped data until authentication and redaction are complete.

The UI and API must identify experimental workflows rather than implying that a template is funded, settled, or protected by GenLayer consensus.

## Feature Research Record

Every candidate must come from the official **Build With GenLayer -> Ideas** page in `genlayer-docs (1).txt`, around line 8897. External patterns or assumptions cannot become unmarked requirements.

| Field | Required decision |
| --- | --- |
| Official idea | Exact Ideas-page name and source location |
| User outcome | What the user is trying to settle or automate |
| Contract boundary | Why GenLayer judgment is required |
| Evidence | Sources, freshness, parsing, provenance, failure behavior |
| Equivalence | Comparative/non-comparative rule and acceptance rubric |
| Consensus | Validator work, disagreement, rotation, `undetermined`, retry |
| Appeals/finality | Appellant, bond/gas, window, transitions, final result |
| Value | Wei conversion, custody, authorization, payout/refund |
| Privacy/abuse | Sensitive data, commit/reveal, replay, adversarial inputs |
| Studio proof | Validators, fixtures, failures, observable states |
| Product status | `research`, `prototype`, `experimental`, or `production` |

Reject or defer a candidate with no meaningful non-deterministic judgment, equivalence rule, verifiable evidence, disagreement/appeal model, custody model, or Studio/local consensus test path.

## Readiness Gates

| Gate | Exit evidence |
| --- | --- |
| G0 Source control | Workflows classified; research cites official sources; backend-generated code is deployment source of truth. |
| G1 Lifecycle | Submission and consensus are separate; appeal/terminal states are handled; finality is queried, not inferred. |
| G2 Integrity/auth | SIWE complete; exact wallet, chain, destination, calldata, value, and intent are bound to the hash. |
| G3 Reproducibility | One generator produces reviewed/deployed code; dependencies are pinned; source hash is verified. |
| G4 Workflow correctness | GEN custody, authorization, state changes, payouts, and refunds are contract-tested. |
| G5 Consensus proof | Multi-validator tests cover equivalence, failures, rotation, appeals, `undetermined`, and finality. |
| G6 Truthful UI | Nothing is called successful, funded, paid, or finalized before the corresponding state is read. |
| G7 Regression safety | Backend tests/build, frontend lint/build, protected logs, and clean generated environments. |

## Change Review Rule

Every feature change links its research record, affected gates, contract source hash, transaction-state evidence, and deterministic/non-deterministic classification. A feature that cannot pass its gates remains experimental.
