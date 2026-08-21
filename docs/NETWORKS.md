# Networks

The application supports GenLayer Studionet and Bradbury through network-specific RPC URLs, chain IDs, and protocol contract configuration. The frontend requests a wallet network switch and the backend verifies that the broadcast transaction belongs to the prepared network.

Network support does not imply support for every feature. Consensus-dependent writes, screenshot verification, and appeals are disabled where their protocol flow has not been proven. Configuration and operational readiness are checked by `/ready`; use `/health` only as a liveness check.

The historical Studionet Conditional Payment transaction is negative evidence, not a diagnosis of every network or contract: it reached `NO_MAJORITY` with zero rounds and zero validators. Until the deterministic canary ladder has controlled results, classify it only as a **suspected hosted validator/network availability blocker**. See [Network Diagnostics](NETWORK-DIAGNOSTICS.md) and the preserved [Phase 9 proof](phase9-studionet-proof.md).
