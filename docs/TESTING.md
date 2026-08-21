# Testing

From the repository root, run:

```bash
python -m pytest backend/tests -q
cd frontend
npm run lint
npm run test:lifecycle
npm run test:notary
npm run build
```

The backend suite covers intent validation, exact wei conversion, prepared-transaction integrity, wallet/chain/calldata/value mismatch rejection, lifecycle persistence, contract preflight, authorization and workflow test doubles, SIWE, logging, and disabled-capability gates. The frontend suite covers lifecycle copy, transaction diagnostics, API handling, notary panels, and truthful workflow labels.

Local tests do not prove GenLayer consensus. A real network proof requires an active validator set, a finalized contract address, and the full recorded contract lifecycle.

For Direct Mode and controlled Studio/localnet tests, install the isolated test dependency set:

```bash
pip install -r backend/requirements-dev.txt
```

The three canonical sources in `contracts/canaries/` must be proven in order: deterministic storage, bounded LLM equivalence, then screenshot/vision. Record every outcome—pass, failure, or external blocker—in the proof artifacts; `NOT_RUN` is never a pass.

Current local release gates:

```bash
python scripts/check_tracked_artifacts.py
python scripts/lint_shipping_contracts.py
python scripts/verify_shipping_contracts.py
python scripts/migration_smoke.py
python -m pytest backend/tests -q
```

The linter and migration smoke test run in CI. Direct Mode, Localnet, Studionet, and Bradbury results remain `NOT_RUN` until their evidence is recorded in the proof matrix.
