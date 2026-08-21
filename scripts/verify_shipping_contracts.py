"""Fail CI when a canonical shipping/canary contract fails project preflight."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CANARY_DIR = ROOT / "contracts" / "canaries"

# A script is executed with its own directory first on sys.path. Add the
# repository root explicitly so this works identically in local shells and CI.
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.validators.contract_validator import ContractValidator


def main() -> int:
    validator = ContractValidator()
    files = sorted(CANARY_DIR.glob("*.py"))
    if not files:
        raise SystemExit("No canonical canary contracts found.")
    failures: list[str] = []
    for path in files:
        result = validator.validate(path.read_text(encoding="utf-8"))
        if not result.get("valid"):
            failures.append(f"{path.relative_to(ROOT)}: {'; '.join(result.get('errors', []))}")
    if failures:
        raise SystemExit("Canonical contract preflight failed:\n" + "\n".join(failures))
    print(f"Validated {len(files)} canonical canary contract(s).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
