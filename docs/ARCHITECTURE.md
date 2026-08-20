# Architecture

GenLayer Bot is a Next.js frontend and FastAPI backend. The frontend owns wallet connection, network switching, and transaction broadcast. The backend authenticates the wallet with SIWE, parses requests into structured intents, applies deterministic policy checks, prepares transaction data, and indexes lifecycle state.

Every write is represented by a short-lived, wallet-scoped prepared transaction. The envelope binds the chain, sender, target, calldata, value, nonce, gas/fee fields, and an intent hash. After the wallet broadcasts, the backend reads the transaction from the selected RPC and rejects mismatches. It stores the EVM transaction hash and, when available, the GenLayer consensus ID.

The database is an index and recovery layer, never the source of truth for contract state. The frontend and backend use canonical RPC reads to reconcile EVM acceptance, consensus status, and GenVM execution. A mined EVM transaction is not presented as consensus finality.

Generated contract source is backend-owned. It is reviewed with its SHA-256 source hash and pinned generator, validator, compiler, SDK, and dependency metadata before deployment preparation.
