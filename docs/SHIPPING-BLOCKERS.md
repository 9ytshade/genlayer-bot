# Features Not Ready for Shipping

This list tracks features that must remain unavailable in the public preview. The historical hosted Studionet transaction recorded zero participating validators and finalized with `NO_MAJORITY`; therefore no end-to-end GenLayer consensus lifecycle has yet been proven. This is a suspected hosted validator/network availability blocker for that transaction, not evidence of a platform-wide outage or a contract-source failure. See [Network Diagnostics](NETWORK-DIAGNOSTICS.md).

| Feature | Why it is not ready | Re-enable gate |
|---|---|---|
| Intelligent Contract deployment | A prepared transaction can be broadcast, but deployment cannot be represented as successful without validator execution and finalization. | Fresh canary has validators, votes, a non-`NO_MAJORITY` result, and a finalized contract address. |
| Conditional payment | Requires real evidence judgment, structured abstention, custody, and deterministic settlement. | Full live lifecycle: deploy, fund, evaluate, settle, verify transfer/refund, then prove duplicate settlement fails. |
| Bounty | Requires validator—not issuer/backend—judgment of qualitative completion and deterministic payout. | Structured outcome plus live submission, evaluation, payout, and duplicate-payout rejection proof. |
| Screenshot verification | The exact rendered image must reach the validator’s vision path. | Direct and live proof that the declared screenshot and criterion are evaluated. |
| AI Notary evaluation | Live claim evaluation and finality have not been proven. | Deploy registry, submit claim, evaluate with validators, read finalized record. |
| Appeals | A real protocol appeal, authoritative bond, and post-appeal finality have not been proven. | Real appeal round with verified bond, submission, and finality record. |
| Workflow deployment/actions | New escrow and subscription writes still execute through GenLayer contract deployment/call infrastructure. | Healthy consensus canary followed by workflow-specific integration proof. |
| Public claims of GenLayer finality | The prior canary had no validator round. | Recorded live proof with consensus ID, votes, final state, and canonical readback. |

## Safe public-preview scope

The following are ready for users to test: wallet connection, SIWE login, network switching, balance reads, native GEN transfers, chat/intents, contract upload/paste, automated contract preflight, source review, transaction preparation, integrity diagnostics, activity logs, and read-only lifecycle inspection.

Do not describe an EVM receipt, a prepared transaction, or a broadcast as GenLayer consensus finality.
