from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


SERVICE_ROOT = Path(__file__).resolve().parents[1]
if str(SERVICE_ROOT) not in sys.path:
    sys.path.insert(0, str(SERVICE_ROOT))

from scripts.database_ops import (  # noqa: E402
    verify_postgresql_restore,
    verify_sqlite_restore,
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Verify a backup by restoring into an isolated target.",
    )
    parser.add_argument("--backup", type=Path, required=True)
    parser.add_argument(
        "--empty-postgres-target-url",
        help=(
            "Required for PostgreSQL. The target must be an isolated, empty "
            "database; the command refuses a target containing any tables."
        ),
    )
    args = parser.parse_args()
    try:
        manifest_path = args.backup.with_name(f"{args.backup.name}.manifest.json")
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        if manifest.get("database_engine") == "sqlite":
            result = verify_sqlite_restore(args.backup)
        elif manifest.get("database_engine") == "postgresql":
            if not args.empty_postgres_target_url:
                parser.error("--empty-postgres-target-url is required for PostgreSQL")
            result = verify_postgresql_restore(args.backup, args.empty_postgres_target_url)
        else:
            raise ValueError("Unknown database engine in backup manifest")
    except (OSError, RuntimeError, ValueError, json.JSONDecodeError) as exc:
        print(f"Restore verification failed: {exc}", file=sys.stderr)
        return 1
    print(
        "Restore verification passed "
        f"(engine={result['database_engine']}, revision={result['schema_revision']}, "
        f"tables={result['table_count']})."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
