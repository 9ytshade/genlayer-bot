# Evidence-First Proof Matrix

`PASS` means evidence is recorded at the stated level. `NOT_RUN` is not a pass. `BLOCKED_EXTERNAL` means the code path may be ready but a validator/network/wallet requirement prevented proof.

| Feature | Unit | Direct | 5-validator Localnet | Hosted Studionet | Bradbury | Publicly enabled |
|---|---|---|---|---|---|---|
| Canary A — deterministic storage | PASS (preflight/diagnostic) | NOT_RUN | NOT_RUN | Historical failure: zero validators | NOT_RUN | No |
| Canary B — bounded LLM equivalence | PASS (preflight) | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | No |
| Canary C — rendered screenshot/vision | PASS (preflight) | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | No |
| AI Notary | PASS | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | No |
| Conditional Payment | PASS | NOT_RUN | NOT_RUN | Historical deployment did not activate validators | NOT_RUN | No |
| Bounty | PASS | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | No |
| Screenshot Verification | PASS (disabled-capability gate) | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | No |
| Appeals | PASS (read-only/rejection gates) | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | No |
| Escrow | PASS | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | No |
| Subscription | PASS | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | No |

The next valid evidence is a Canary A run in Direct Mode followed by a five-validator Localnet. Do not promote a feature based on this table without updating it with command output and a transaction/readback artifact.
