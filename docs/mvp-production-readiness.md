# GenLayer Bot local validation and production-readiness runbook

## Current release posture

The repository has local validation coverage, but it is not proven MVP-production-ready and no 10/10 or demo-ready claim is made. Passing local tests, lint, type checking, or a production build does not replace live GenLayer proof.

Previously recorded local gates include:

- Backend test suite: 173 passed with the repository's configured pytest settings.
- Frontend ESLint: passed.
- Frontend TypeScript: passed.
- Frontend production build: passed.
- Consensus lifecycle tests: 10 passed.
- Notary, lifecycle, RPC, auth, logging, and failed-transaction tests are included in the 173-test backend suite.
- Phase 10 targeted backend suite: 77 passed.
- Migration smoke test: upgraded a fresh SQLite database through `202608180002` and verified lifecycle columns plus the persisted `siwe_nonces` table and indexes.
- Frontend regression tests: 27 passed across lifecycle, notary, workflow-truthfulness, message, and API coverage.
- Browser smoke check: local app rendered successfully with wallet gating and network selection visible.
- GitHub Actions now runs backend tests plus frontend lint, lifecycle/component tests, and the production build on pull requests and pushes to `main`.

## Required production configuration

- Set `APP_ENV=production` and a non-placeholder `JWT_SECRET` of at least 32 random characters outside source control.
- `/health` is process liveness only; configure deployment readiness checks against `/ready`.
- `/ready` verifies required configuration, database connectivity, the current Alembic migration head, and production RPC connectivity/chain identity.
- Set production `DATABASE_URL` and run Alembic migrations during deployment.
- Set an explicit `ALLOWED_ORIGINS` list; do not use wildcard origins with credentials.
- Set network-specific GenLayer RPC URLs and chain IDs.
- Keep protocol contract addresses namespaced per network.
- Configure Redis for multi-instance log streaming. Set `REQUIRE_REDIS=true` when a missing shared log store must fail readiness.
- Activity logs are wallet-scoped, metadata-redacted, bounded, and stored under hashed Redis keys/channels.
- SIWE nonces are hashed, database-backed, expiring, and consumed before signature verification.
- Tune bounded RPC behavior with `RPC_REQUEST_TIMEOUT_SEC`, `RPC_MAX_ATTEMPTS`, and `RPC_RETRY_BACKOFF_SEC`.
- Requests enforce bounded chat, contract-source, transaction-builder, and persisted-history payloads.
- Keep wallet confirmation in the connected-wallet client; the backend never accepts raw signed transactions.

## Product capability boundary

- Deterministic escrow and subscription paths remain available subject to their local validation gates; they are not presented as GenLayer judgment.
- New conditional-payment generation, deployment, and settlement are disabled until evidence evaluation, structured abstention, custody, and deterministic settlement are rebuilt and proven.
- New bounty generation, deployment, review, winner selection, and closure are disabled until validators judge qualitative completion with structured insufficient-evidence handling.
- Screenshot verification is disabled until validators are proven to evaluate the exact rendered screenshot with the pinned runtime.
- Appealability metadata is read-only. Appeal preparation, wallet submission, and confirmation are disabled until a real appeal round and post-window finality are proven.
- Automated contract preflight is available, but it is advisory and does not replace the deployment validator or source-integrity review.

## Release blockers

1. Clean connected-wallet GenLayer consensus proof with multiple validators. The August 17, 2026 Phase 9 conditional-payment deployment was accepted by Rabby and mined as `0x669ddac46123047ca1cc10d6f6f929c70cadca0a21b53177bb0a2e05bc3173d1`, but finalized with 0 rounds / 0 validators / `NO_MAJORITY` and no contract address. See `docs/phase9-studionet-proof.md`.
2. AI Notary live deployment, claim submission, evaluation, finality, and record-read proof.
3. A complete real appeal-round proof with a positive authoritative minimum bond and post-window finality before any appeal UI can be enabled.
4. Completion of the disabled conditional-payment, bounty, and screenshot-verification protocol paths.

The appeal flow remains fail-closed regardless of read-only eligibility until Phase 16 is completely proven.

## Safe staging sequence

1. Deploy the backend and frontend with the production configuration above.
2. Run `/health`, require `/ready` to return HTTP 200, and run authenticated read-only checks.
3. Verify wallet authentication and prepared transaction creation without broadcasting.
4. Verify locally supported blueprint/review flows with a test wallet without describing them as live consensus proof.
5. Run a clean protocol deployment only on an approved network with known validator health.
6. Do not use the prior Studionet `NO_MAJORITY` canaries for appeal testing.
7. Do not open an appeal wallet confirmation in the current release; the submission path is disabled.

## Explicit non-goals for this release

- Do not guess missing Studio appeal addresses.
- Do not treat local simulator output as live consensus proof.
- Do not promote AI Notary beyond prototype until live consensus, appeal, and finality evidence is attached.
- Do not enable conditional-payment, bounty, screenshot-verification, or appeal actions based only on local tests.
