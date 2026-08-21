"""Export the reviewed AI Notary registry source used by the backend."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.services.notary_service import generate_notary_contract_code


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        default=str(ROOT / "contracts" / "canaries" / "AiNotaryRegistry.py"),
        help="Path for the canonical generated source.",
    )
    args = parser.parse_args()
    output = Path(args.output).resolve()
    if ROOT not in output.parents:
        raise SystemExit("Output must stay inside the repository.")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(generate_notary_contract_code(), encoding="utf-8", newline="\n")
    print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
