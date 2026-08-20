# Security Model

- SIWE nonces are database-backed, expiring, hashed, and consumed before signature verification.
- JWT sessions are wallet-bound; prepared writes are wallet-scoped, short-lived, and single-use.
- Confirmed transaction hashes are verified against the frozen envelope rather than trusted as user assertions.
- GEN amounts are canonical decimal strings converted to integer wei; settlement logic must not use floats.
- Activity logs are wallet-scoped and redact secret-bearing metadata. Production can require Redis for shared log storage.
- CORS is explicit, and production readiness rejects unsafe placeholder secrets or missing required infrastructure.

Do not put private keys, JWT secrets, API keys, or `.env` files in source control. Automated contract preflight is not a substitute for an independent security review of a contract that will custody value.
