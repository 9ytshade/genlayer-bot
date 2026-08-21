# Known Limitations

The project is not 10/10 demo-ready and must not be described as production-ready.

- The recorded Studionet canary finalized with `NO_MAJORITY`, zero rounds, and no deployed address; it is not live workflow proof. It is classified only as a suspected hosted validator/network availability blocker until controlled canaries isolate the cause. See [Phase 9 proof](phase9-studionet-proof.md) and [Network Diagnostics](NETWORK-DIAGNOSTICS.md).
- Conditional payment and bounty deployment/actions are disabled pending structured validator evidence, abstention, deterministic custody settlement, and successful live proof.
- Screenshot verification is disabled pending proof that validators receive and evaluate the exact rendered image.
- Appeal submission is disabled pending a real appeal round, authoritative bond handling, and post-window finality proof.
- Contract preflight is automated guidance, not a formal audit.

The app fails closed for these limitations rather than exposing placeholder or simulated write flows.
