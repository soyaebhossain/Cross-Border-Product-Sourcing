from __future__ import annotations

import argparse
import sys
from pathlib import Path


SERVICE_ROOT = Path(__file__).resolve().parents[1]
if str(SERVICE_ROOT) not in sys.path:
    sys.path.insert(0, str(SERVICE_ROOT))

from app.config import get_settings  # noqa: E402
from scripts.database_ops import backup_postgresql, backup_sqlite  # noqa: E402
from sqlalchemy.engine import make_url  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Create a consistent database backup and checksum manifest.",
    )
    parser.add_argument(
        "--output-directory",
        type=Path,
        required=True,
        help="Restricted, encrypted-at-rest backup destination.",
    )
    args = parser.parse_args()
    database_url = get_settings().database_url
    backend = make_url(database_url).get_backend_name()
    try:
        if backend == "sqlite":
            backup, manifest = backup_sqlite(database_url, args.output_directory)
        elif backend == "postgresql":
            backup, manifest = backup_postgresql(database_url, args.output_directory)
        else:
            raise ValueError(f"Unsupported database engine: {backend}")
    except (OSError, RuntimeError, ValueError) as exc:
        print(f"Backup failed: {exc}", file=sys.stderr)
        return 1
    print(f"Backup created: {backup}")
    print(f"Checksum manifest: {manifest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
