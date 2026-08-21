"""Apply every Alembic migration to a disposable SQLite database."""

from __future__ import annotations

import tempfile
import sys
from pathlib import Path

from alembic import command
from alembic.config import Config


ROOT = Path(__file__).resolve().parents[1]

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="genlayer-bot-migration-") as directory:
        database = Path(directory) / "migration-smoke.db"
        config = Config(str(ROOT / "backend" / "alembic.ini"))
        config.set_main_option("script_location", str(ROOT / "backend" / "alembic"))
        config.set_main_option("sqlalchemy.url", f"sqlite:///{database.as_posix()}")
        command.upgrade(config, "head")
    print("Migration smoke test passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
