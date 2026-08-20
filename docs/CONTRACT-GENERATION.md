# Contract Generation and Review

Natural-language requests are converted to structured intents and accepted only by trusted generator families. A generated or workflow artifact is validated, reviewed, and frozen before the backend prepares a deployment transaction.

The preflight checks Python syntax, the pinned GenLayer dependency header, imports, contract inheritance, public method types, storage declarations, forbidden floating point usage, non-deterministic boundary placement, and loose consensus substring checks. It returns diagnostics and remains an automated preflight, not a formal audit.

Deployment rejects changed source, an unpinned dependency, or stale generator/validator metadata. User-supplied source can be reviewed, but must not bypass this reviewed-artifact boundary.
