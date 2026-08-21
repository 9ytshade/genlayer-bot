"""Reject generated runtimes and credential-shaped files in the Git index."""

from __future__ import annotations

import subprocess


FORBIDDEN_PARTS = ("/.venv/", "/node_modules/", "/__pycache__/", "/.pytest_cache/", "/.next/")
FORBIDDEN_SUFFIXES = (".db", ".sqlite", ".sqlite3", ".pem", ".p12", ".pfx")
FORBIDDEN_NAMES = {".env", "id_rsa", "credentials.json", "genlayer-docs (1).txt"}


def main() -> int:
    tracked = subprocess.check_output(["git", "ls-files"], text=True).splitlines()
    forbidden = [
        path for path in tracked
        if any(part in f"/{path}" for part in FORBIDDEN_PARTS)
        or path.endswith(FORBIDDEN_SUFFIXES)
        or path.rsplit("/", 1)[-1] in FORBIDDEN_NAMES
    ]
    if forbidden:
        raise SystemExit("Generated runtime or credential-shaped files are tracked:\n" + "\n".join(forbidden))
    print("Tracked artifact check passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
