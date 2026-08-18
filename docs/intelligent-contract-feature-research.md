# Intelligent Contract Feature Research

**Date:** 2026-08-05
**Status:** Research
**Decision:** Recommend an AI Notary feature, delivered through the chatbot's text-based contract experience.

## Scope And Source Boundary

This research uses the official GenLayer documentation snapshot in `genlayer-docs (1).txt` and the current repository. The official idea list is under **Build With GenLayer**, beginning around line 8897.

P0.5 appeal hardening is suspended by current project direction while AI Notary advances as a prototype. This does not waive the readiness charter or permit promotion beyond `prototype` without Studio/multi-validator, appeal, and finality proof.

## Decision Summary

The strongest new feature for GenLayer Bot is **AI Notary**: a user describes a public online claim in chat, supplies public evidence sources and an evaluation rubric, and deploys or calls an Intelligent Contract that records a consensus-backed verdict such as `CONFIRMED`, `REFUTED`, or `INCONCLUSIVE`.

This combines two official ideas without confusing their roles:

- **AI Notary** is the contract's domain and official feature anchor (`genlayer-docs (1).txt`, line 8917).
- **Text-based Intelligent Contracts** is the conversational creation and configuration experience (`genlayer-docs (1).txt`, line 8922).

AI Notary is the best first choice because it exercises GenLayer's distinctive web and LLM consensus capabilities, fits a chat-first interface, reuses the existing authenticated transaction and lifecycle architecture, and does not require payout custody in its first version.

## Official Ideas Comparison

| Official idea | Fit | Research disposition |
| --- | --- | --- |
| Prediction Markets | Medium | Strong web-resolution example, but introduces wagering, custody, settlement, and legal risk. Defer. |
| Parametric Insurance | Low | Requires authoritative data policies, reserves, claims economics, and payout custody. Defer. |
| Bounty Review and Payout | Existing | Already represented by the experimental bounty workflow. Improve later rather than add again. |
| Performance-based Contracting | High | Fits escrow and web verification, but substantially overlaps current conditional-payment, escrow, and bounty work. Later extension. |
| Slashing Monitoring and Insurance | Low | Needs continuous protocol monitoring, high-confidence violation rules, and insurance capital. Defer. |
| Hack Detection and Emergency Pause | Low | Automated pause authority has a very high false-positive and security impact. Not an appropriate first chatbot feature. |
| On-chain Identity Verification | Medium | Chat and web verification fit, but privacy, impersonation, revocation, and social-platform reliability are substantial. Defer. |
| Under-collateralized Lending | Low | Depends on identity and reputation while adding credit, liquidation, and custody risk. Reject for the current architecture. |
| P2P Gambling | Low | Technically similar to prediction markets but adds wagering and dispute risk without new architectural value. Defer. |
| Decentralized Game Master | Medium | Excellent conversational fit and low custody requirements, but weak alignment with the bot's current transaction and contract-operations focus. Possible later experiment. |
| Interoperable Games with NFTs | Low | Requires NFT standards, asset interoperability, and game-specific product surfaces not present in the bot. Defer. |
| Unstoppable Organizations | Low | Too broad for a bounded feature and requires governance, treasury, upgrade, and mission-continuity design. Defer. |
| Retroactive Public Goods Funding | Medium | Valuable judgment use case, but requires contribution discovery, scoring, Sybil resistance, and treasury payouts. Later phase. |
| Crowd-sourced Knowledge Database | High | Strong chat and vector-store fit, but contribution rewards, moderation, provenance, spam, and duplicate handling make it a larger second-stage product. Shortlist. |
| AI Notary | Very high | Clear public-evidence judgment, strong web/LLM use, inspectable result, no required payout custody, and a natural chat workflow. Recommend. |
| AI Arbitration | High | Strong GenLayer fit and a generic template already exists, but evidence privacy, party authorization, legal copy, and remedy enforcement make it higher risk. Later feature. |
| Private P2P Contracts | Medium | Useful extension of escrow/arbitration, but commit/reveal privacy, disclosure rules, custody, and disputes need deeper protocol proof. Defer. |
| Multi-modal Use Cases | High | Best treated as an evidence capability added to AI Notary or performance contracting, not a standalone product. Phase-two Notary extension. |
| Generative Memes | Low | Does not match the bot's operational contract focus or current users' primary jobs. Defer. |
| Text-based Intelligent Contracts | Very high | This is already partially embodied by `/generate-contract`. Use it as the AI Notary configuration layer and later strengthen it as a platform capability. |
| Honeypot Contracts for Security | Low | Intentionally adversarial contracts create operational and reputational risk and need an isolated security environment. Defer. |
| Fair and Transparent Moderation | High | Clear structured LLM judgment and an existing generic generator template. Strong second choice after AI Notary. |

## Architecture Fit

The proposed feature can reuse existing capabilities:

- Natural-language chat intent collection and structured parsing.
- Backend-owned canonical contract generation, validation, artifact hashing, and deployment source.
- SIWE-authenticated wallet, chain, destination, calldata, value, gas, and intent binding.
- Wallet-side deployment and contract-call broadcast.
- Separate EVM submission, GenLayer consensus, appealability, finality, and GenVM execution states.
- Existing message cards, confirmation controls, and workflow-style detail panels.

It should not be implemented as another financial workflow in `workflow_service.py`. AI Notary has no payout lifecycle in its MVP and deserves a dedicated `notary_service.py` boundary while reusing the shared deployment and transaction builders.

The current generic non-deterministic templates are useful prototypes, not a production source for this feature. Some use exact equality with raw web or LLM output, while the supplied docs require stable derived web fields and structural or semantic validation for LLM results. The AI Notary contract should therefore be generated from a dedicated, tested backend template.

## Feature Research Record

| Field | Decision |
| --- | --- |
| Official idea | **AI Notary**, official Ideas page at `genlayer-docs (1).txt:8917`. Text-based Intelligent Contracts at line 8922 informs the user experience. |
| User outcome | Create an inspectable on-chain record of whether a public online claim is confirmed, refuted, or inconclusive based on declared evidence. |
| Contract boundary | GenLayer judgment is required because independent validators must fetch changing public sources, interpret unstructured evidence, and agree on a bounded verdict. |
| Evidence | One to three public HTTPS sources in the MVP. Store source URLs, declared freshness policy, fetch outcome, normalized supporting facts, and failure reason. Unavailable, stale, or conflicting evidence produces `INCONCLUSIVE`; it does not silently pass. |
| Equivalence | Validators independently fetch and evaluate the sources. They must agree on the verdict enum and whether each required source was usable. Rationales may differ, but must cite the same material facts. Borderline or insufficient cases resolve to `INCONCLUSIVE`. Use a custom validator or comparative validation, never strict equality over raw LLM or web output. |
| Consensus | The leader proposes structured evidence and a verdict. Validators reproduce the evaluation. Disagreement triggers normal rotation; exhausted disagreement becomes `UNDETERMINED`. No UI verdict is authoritative before finalized successful execution. |
| Appeals/finality | The authenticated claimant or a challenger can prepare a protocol appeal where allowed by GenLayer. The UI displays the required bond/gas, provisional result, appeal window, active appeal rounds, and final result. Network-level appeal rules remain authoritative. |
| Value | MVP transfers no claim payout and holds no user funds. Users only review network transaction value, gas, and any protocol appeal bond. This intentionally avoids adding custody before the core adjudication flow is proven. |
| Privacy/abuse | Public evidence only. Reject credentials, private documents, local-network URLs, and unsupported schemes. Treat all fetched text as untrusted, limit source count and content size, bind the submitting wallet, prevent duplicate evaluation, and defend prompts against source-borne instructions. |
| Studio proof | Use five validators with mocked web and LLM responses for confirmed, refuted, inconclusive, unavailable-source, stale-source, conflicting-source, malformed-output, prompt-injection, disagreement, and rotation fixtures. Add live Studio/local appeal and finality scenarios when the environment is available. |
| Product status | `prototype`: local contract, API, lifecycle, build, and feature-scoped lint gates pass. Promote to `experimental` only after multi-validator Studio proof; never `production` before all readiness gates pass. |

## Implementation Checkpoint

As of 2026-08-07, the local prototype includes the dedicated Notary specification and canonical registry generator, public HTTPS/domain validation, deterministic claim IDs, multi-turn chat blueprint completion, authenticated deployment and contract-call preparation, registry/claim persistence, finalized record reads, and responsive blueprint/record panels. The generated registry also passes pinned GenVM lint, semantic validation, ABI extraction, and direct runtime execution through submission, evaluation, validator acceptance, and record read.

The remaining boundary is connected protocol proof: a five-validator local simulator finalized deployment and submission unanimously and produced a confirmed record, but its evaluation receipt exposed a simulator state-isolation defect during validator re-execution. A clean connected-wallet Studio execution, true per-validator disagreement/rotation fixtures, appeals, and finality behavior are still required.

The first clean connected-wallet Studio retry reached deployment preparation with the same Rabby wallet connected in the prototype and Studio, but the Studio RPC returned HTTP 503 before a fresh signing request was created. The prepared envelope remained unconsumed and no gas was spent. Offline hardening now preserves transaction hashes and prepared-intent identifiers across confirmation errors, emits structured wallet/destination mismatch diagnostics without exposing calldata, marks RPC visibility failures as retriable after five lookup attempts, and adds 14 frontend regression tests for Notary blueprint/record states and recovery UI. The feature remains `prototype`; this resilience evidence does not replace connected Studio proof.

## Proposed Product Flow

1. The user starts with a message such as: `Notarize whether project.example shipped version 2.0 by 1 August 2026 using these release and repository pages.`
2. The bot collects the claim, public source URLs, cutoff/freshness rule, and the exact rubric for `CONFIRMED`, `REFUTED`, and `INCONCLUSIVE`.
3. The bot presents a Notary Blueprint showing sources, evidence policy, equivalence rule, authorization, privacy warning, and expected contract methods.
4. The backend generates and validates the canonical AI Notary contract artifact and displays its source hash.
5. The authenticated wallet deploys a reusable notary registry or calls an existing registry to submit the claim.
6. The UI follows EVM submission, consensus, provisional verdict, appealability, finality, and GenVM execution as separate states.
7. A Notary Record panel exposes the claim ID, claimant, sources, normalized evidence, verdict, rationale, consensus state, appeal state, and finality.

## Contract Shape

The first contract should be a reusable public-claim registry rather than one deployment per claim.

Suggested methods:

- `submit_claim(statement, source_urls, rubric, freshness_rule) -> claim_id`
- `evaluate_claim(claim_id) -> verdict`
- `get_claim(claim_id) -> claim record`
- `get_claim_count() -> count`

Suggested verdicts:

- `PENDING`
- `CONFIRMED`
- `REFUTED`
- `INCONCLUSIVE`

Deterministic storage changes must occur only after the non-deterministic result has passed validator consensus. The stored record should preserve the submitting wallet and declared sources, but avoid copying arbitrary full web pages on chain.

## Implementation Outline

1. Add a dedicated backend Notary specification, validator, and canonical contract generator.
2. Add a `notarize_claim` intent and a multi-turn blueprint flow for missing claim, source, freshness, and rubric fields.
3. Reuse the authenticated deployment and contract-call builders instead of creating a separate transaction path.
4. Add a Notary Record frontend panel with truthful consensus, appeal, finality, evidence, and error states.
5. Add GenVM linter/schema checks and mocked multi-validator contract tests before UI integration.
6. Add API and UI tests for authorization, intent mismatch, duplicate evaluation, malformed sources, prompt injection, unavailable evidence, disagreement, and finalized execution errors.
7. Extend the feature later with image evidence under the official Multi-modal Use Cases idea.

## Recommended Sequence

1. Research approval and contract interface review.
2. Offline contract prototype and test fixtures.
3. Chat blueprint and canonical artifact generation.
4. Authenticated deployment/call integration.
5. Notary Record UI.
6. Studio multi-validator, appeal, and finality proof when the environment is available.

AI Notary should be the first new Ideas-page feature. Fair and Transparent Moderation is the best second feature, and Crowd-sourced Knowledge Database is the strongest larger follow-on once the reusable evidence and adjudication foundation is proven.
