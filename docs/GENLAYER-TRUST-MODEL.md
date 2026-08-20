# GenLayer Trust Model

The connected wallet is the only signer. The backend never receives a private key and never broadcasts a raw signed transaction on the user's behalf.

Deterministic fields such as addresses, wei amounts, authorization, state transitions, and settlement amounts are fixed by reviewed contract code and transaction-intent checks. The backend may parse, prepare, index, and explain, but cannot unilaterally select an outcome that moves funds.

GenLayer is required only where validators must judge an ambiguous fact from evidence. Any future intelligent workflow must use a bounded structured outcome, include an explicit insufficient-evidence outcome, and permit deterministic code—not model prose—to perform the resulting settlement. Current conditional-payment and bounty write paths remain disabled until that design is deployed and live-proven.
