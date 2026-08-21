"""Run the installed GenVM linter against every canonical canary contract."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CANARY_DIR = ROOT / "contracts" / "canaries"


def main() -> int:
    files = sorted(CANARY_DIR.glob("*.py"))
    if not files:
        raise SystemExit("No canonical canary contracts found.")
    environment = {**os.environ, "PYTHONUTF8": "1"}
    for path in files:
        subprocess.run(["genvm-lint", str(path)], check=True, env=environment)
    print(f"GenVM lint passed for {len(files)} canonical canary contract(s).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
