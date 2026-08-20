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
