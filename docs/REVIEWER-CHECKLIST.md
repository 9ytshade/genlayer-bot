# Reviewer Checklist

## Evidence-first checks

- [ ] Run the read-only network diagnostic for each proof transaction.
- [ ] Confirm validator count and round count are non-zero.
- [ ] Confirm the execution result is `FINISHED_WITH_RETURN`, not just consensus `FINALIZED`.
- [ ] Confirm canonical contract state readback matches the reviewed source/specification.
- [ ] For any payout, confirm the triggered child transaction and recipient/refund balance change.

## Safety checks

- [ ] Wallet remains the external signer; no server private key exists.
- [ ] Prepared transaction hashes bind wallet, chain, target, calldata, and value.
- [ ] Amounts use integer wei and contract settlement contains no floating-point arithmetic.
- [ ] Validator output uses bounded outcome fields and insufficient evidence is safe.
- [ ] Web evidence is treated as untrusted content and restricted to public HTTPS sources.

## Current release boundary

- [ ] AI Notary, Conditional Payment, Bounty, Screenshot Verification, and Appeals remain disabled until their individual public-proof gate is met.
- [ ] No documentation claims public proof before a real record is added to `SUBMISSION-PROOF.md`.
