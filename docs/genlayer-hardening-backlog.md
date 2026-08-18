# GenLayer Hardening Backlog

This backlog turns the repository audit into bounded implementation work. It is ordered by protocol and user-safety impact. No new Ideas-page feature should start until the P0 gates in the readiness charter are complete.

## P0 - Protocol Truth and User Safety

### P0.1 Implement one canonical GenLayer transaction lifecycle

**Status:** Complete as of 2026-08-04.

**Owners:** `backend/routers/chat.py`, transaction persistence/models, `frontend/src/components/Message.tsx`, transaction hooks/services

**Work:** Store and expose GenLayer status independently from the EVM submission receipt. Normalize `pending`, `proposing`, `committing`, `revealing`, `accepted`, `appealable`, `finalized`, `undetermined`, and `canceled`; model appeal transitions and polling/backoff explicitly.

**Acceptance:** An EVM receipt never implies finality. Fixtures move through accepted, appealed, undetermined, and finalized states, and the UI displays each accurately.

**Evidence:** The backend exposes consensus and GenVM execution as separate fields, supports documented and installed-SDK receipt shapes, keeps finalized-but-unverified execution pollable, blocks failed deployment addresses, and persists workflow state only after successful execution. Frontend fixtures cover every canonical provisional, appeal, terminal-failure, finalized-success, finalized-error, and finalized-unverified presentation.

**Verification:** `backend/.venv-win/Scripts/python.exe -m pytest backend/tests -q` (35 passed), `npm run test:lifecycle` (7 passed), targeted ESLint for changed lifecycle files (passed), `npm run build` (passed), and `git diff --check` (passed). Repository-wide lint still reports only the pre-existing hook failures tracked under P2.1.

### P0.2 Bind preparation and confirmation to authenticated intent

**Status:** Complete as of 2026-08-04.

**Owners:** `backend/routers/chat.py`, `backend/auth.py`, `backend/schemas.py`, frontend wallet/API context

**Work:** Complete SIWE and require authentication for builders, confirmations, appeals, and sensitive reads. Persist a reviewed envelope containing wallet, chain, destination, calldata, value, gas/rotation settings, and intent hash. Confirm only an exact match.

**Acceptance:** A different wallet, chain, destination, calldata, or value cannot confirm another user's transaction. Unauthorized confirmation and log access fail.

**Evidence:** SIWE now validates the EIP-4361 domain, URI, address, nonce, issued-at window, signature, one-time replay protection, and an optional configured chain allowlist. Authenticated transfer, deployment, workflow-deployment, and contract-call builders persist expiring single-use envelopes containing the reviewed wallet, network/chain, destination, calldata, value, nonce, gas/fee fields, consensus settings, canonical intent, and SHA-256 intent hash. Confirmation no longer relays raw signed transactions: it loads the authenticated user's envelope, reads the wallet-broadcast transaction from the configured RPC, rejects any exact-field mismatch, and consumes the envelope once. Consensus-driven workflow persistence uses the stored intent rather than client-supplied metadata. HTTP and WebSocket activity logs require a valid session. Appeal broadcast is explicitly disabled until the bond/gas/appellant verification in P0.5 is complete, so it cannot bypass the envelope gate.

**Verification:** `backend/.venv-win/Scripts/python.exe -m pytest backend/tests -q` (47 passed), targeted ESLint for the changed frontend files (passed), `npm run test:lifecycle` (7 passed), `npm run build` (passed), and `git diff --check` (passed).

### P0.3 Make generated contract code the sole source of truth

**Status:** Partially proven locally; superseded by the strict remediation phases for unsupported judgment workflows.

**Owners:** `backend/services/contract_generation_service.py`, `backend/generators/contract_generator.py`, frontend workflow templates

**Work:** Eliminate duplicate frontend templates. Generate, validate, hash, display, and deploy the exact backend-produced Python source. Pin GenVM/`py-genlayer` versions and record validator/compiler versions.

**Acceptance:** Reviewed source hash equals deployed payload; template changes invalidate stale confirmations; validation targets the pinned runtime.

**Evidence:** All generated and workflow contracts now use the official pinned `py-genlayer` dependency hash from the repository's documentation snapshot, while `genlayer-py==0.18.0` remains pinned for transaction construction. Backend artifact metadata records the exact UTF-8 source SHA-256, source origin, GenLayer SDK version, generator fingerprint, validator fingerprint, Python AST/compiler version, and artifact format version. The authenticated workflow review endpoint generates and validates the canonical source before it is displayed. Both generic and workflow deploy builders reject missing, modified, or stale review metadata before transaction construction, pass the exact reviewed source bytes into the GenLayer deployment encoder, and bind the canonical metadata into the single-use prepared intent. The duplicate frontend `ContractRegistry` Python templates were removed; the frontend only displays backend-returned source and verifies the deploy builder returns the same hash.

**Verification:** `backend/.venv-win/Scripts/python.exe -m pytest backend/tests -q` (52 passed), `npm run test:lifecycle` (7 passed), targeted ESLint for the changed artifact/review files (passed), `npm run build` (passed), and `git diff --check` (passed).

### P0.4 Correct workflow value movement and authorization

**Status:** Complete as of 2026-08-05.

**Owners:** `backend/services/workflow_service.py`, workflow contract templates, dashboards, workflow action builders

**Work:** Define real GEN custody, payout, and refund paths; convert human amounts to wei without rounding; enforce roles; read on-chain state; remove hard-coded funded/status labels. Conditional payment and bounty require separate GenLayer judgment rebuilds and are disabled until those phases are complete.

**Acceptance:** Tests prove authorization, exact wei amounts, custody changes, payout/refund behavior, replay protection, and failed/appealed outcomes. Dashboards reflect contract and lifecycle reads.

**Evidence:** Exact integer-wei and deterministic workflow fixtures exist locally. Escrow and subscription remain classified as deterministic behavior. Legacy conditional-payment and bounty state can be displayed read-only, but new generation, deployment, and actions now fail closed because the current templates do not satisfy the required GenLayer evidence, abstention, validator-judgment, custody, and settlement gates.

**Verification:** Historical local checks do not prove live custody or GenLayer judgment. Current Phase 1 regression gates require disabled conditional-payment and bounty endpoints plus read-only dashboard behavior; direct pinned-runtime and live-network proof remain pending later phases.

### P0.5 Fix appeal construction and verification

**Status:** Disabled for submission. Only authoritative read-only appealability metadata is exposed until Phase 16 proof is complete.

**Owners:** `backend/genlayer_client.py`, appeal API/UI

**Work:** Build `appealTransaction` rather than `canAppeal`, attach required bond/gas, bind appellant and target transaction, and expose the appeal window.

**Acceptance:** Studio/local tests cover valid appeal, insufficient bond/gas, unauthorized appellant, successful/failed appeals, and finality after the window.

## P1 - Consensus and Reproducibility

### P1.1 Add Studio/local multi-validator tests

Cover comparative/non-comparative equivalence, divergent LLM/web results, malformed evidence, leader rotation, `undetermined`, appeal escalation, and finality with reproducible fixtures.

### P1.2 Add contract-level security tests

Cover caller authorization, replay/nonces, value conservation, constructor validation, malformed calldata, unsupported chain, and stale-intent rejection.

### P1.3 Replace AST-only checks with compatibility checks

Compile or execute generated contracts in the pinned GenVM/Studio target. Fail closed on unsupported APIs, dependencies, or non-determinism without an equivalence rule.

### P1.4 Make logs wallet-scoped, authenticated, and redacted

**Status:** Complete as of 2026-08-18.

HTTP and WebSocket reads are scoped to the authenticated wallet. Memory streams and Redis keys/channels use hashed wallet scopes; unscoped system events are not exposed through user endpoints. Metadata is restricted to safe lifecycle/action fields, sensitive values are redacted, subscriber queues and retained histories are bounded, and retention is configurable through `ACTIVITY_LOG_MAX_ITEMS`.

## P2 - Quality and Repository Hygiene

### P2.1 Fix frontend lint failures

Resolve hook errors in `frontend/src/hooks/useContractRead.ts` and `frontend/src/hooks/useTransactionReceipt.ts`; require `npm run lint`.

### P2.2 Remove committed environment/build artifacts

Stop tracking `backend/.venv` and other ignored generated artifacts. Keep reproducible source, locks, and configuration only.

### P2.3 Add truthful-UI regression coverage

Test loading, pending, accepted, appealable, undetermined, reverted, finalized, timeout, and RPC-error rendering for messages and dashboards.

## Definition of Done

- Every P0 item is complete and linked to tests.
- P1 consensus scenarios pass against the pinned GenVM target.
- Backend tests, frontend lint/build, and repository hygiene checks pass in CI.
- A workflow is promoted from experimental only when its readiness gates have evidence.
