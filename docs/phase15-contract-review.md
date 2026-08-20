# Automated Contract Preflight

The `/chat/contract-review` endpoint and `/contract-review` chat command provide automated preflight analysis for pasted GenLayer Intelligent Contract source.

The result is intentionally not a formal security audit. It contains:

- structural findings for contract classes, public methods, storage fields, nondeterministic calls, and Equivalence Principle boundaries
- safety findings for value custody, visible sender authorization checks, terminal-state markers, and potential duplicate settlement risks
- GenLayer-native findings describing whether nondeterministic judgment is present and whether structured output/equivalence handling is visible
- deployment readiness as `READY`, `READY_WITH_WARNINGS`, or `BLOCKED`, with blocking errors, warnings, and review suggestions

The normal deployment path still runs the authoritative GenLayer-aware validator and requires a fresh reviewed source hash before wallet transaction construction. Preflight output does not bypass validation, source-integrity checks, or wallet confirmation.
