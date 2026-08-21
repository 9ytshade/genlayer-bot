# Evidence-First Proof Matrix

`PASS` means evidence is recorded at the stated level. `NOT_RUN` is not a pass. `BLOCKED_EXTERNAL` means the code path may be ready but a validator, network, wallet, or toolchain requirement prevented proof.

| Feature | Unit | Direct | Studio full consensus | 5-validator Localnet | Hosted Studionet | Bradbury | Publicly enabled |
|---|---|---|---|---|---|---|---|
| Canary A - deterministic storage | PASS (preflight/diagnostic) | NOT_RUN | PASS - deploy, write, and readback; numeric rounds not exposed by captured Studio UI | NOT_RUN | Historical failure: zero validators | NOT_RUN | No |
| Canary B - bounded LLM equivalence | PASS (preflight) | NOT_RUN | PASS - deploy, structured equivalence output, write, and readback; numeric rounds not exposed by captured Studio UI | NOT_RUN | NOT_RUN | NOT_RUN | No |
| Canary C - rendered screenshot/vision | PASS (preflight) | NOT_RUN | FAIL - leader produced RENDERED but validator consensus was undetermined; state remained PENDING | NOT_RUN | NOT_RUN | NOT_RUN | No |
| AI Notary | PASS | NOT_RUN | PASS - deploy, submit, validator-backed CONFIRMED evaluation, and canonical claim readback | NOT_RUN | NOT_RUN | NOT_RUN | No |
| Conditional Payment | PASS | NOT_RUN | NOT_RUN | NOT_RUN | Historical deployment did not activate validators | NOT_RUN | No |
| Bounty | PASS | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | No |
| Screenshot Verification | PASS (disabled-capability gate) | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | No |
| Appeals | PASS (read-only/rejection gates) | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | No |
| Escrow | PASS | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | No |
| Subscription | PASS | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | No |

The next valid work is a public-network AI Notary proof on Bradbury when funded credentials are available. Canary C web/vision equivalence remains a separate failure to diagnose; Direct Mode and a five-validator Localnet remain follow-ups when their SDK/tooling compatibility is resolved. Do not promote a feature based on this table without updating it with transaction and readback evidence.
