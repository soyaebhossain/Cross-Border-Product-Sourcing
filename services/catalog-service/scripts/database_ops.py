from __future__ import annotations

import hashlib
import json
import os
import secrets
import shutil
import sqlite3
import subprocess
import tempfile
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import make_url


REQUIRED_TABLES = {
    "accounts_users",
    "catalog_products",
    "orders_orders",
    "orders_manual_payments",
    "admin_audit_events",
}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _restrict_permissions(path: Path) -> None:
    try:
        path.chmod(0o600)
    except OSError:
        # Windows ACLs are inherited from the destination. The runbook requires
        # a restricted backup directory and encrypted storage.
        pass


def _manifest_path(backup_path: Path) -> Path:
    return backup_path.with_name(f"{backup_path.name}.manifest.json")


def _write_manifest(backup_path: Path, manifest: dict[str, Any]) -> Path:
    destination = _manifest_path(backup_path)
    temporary = destination.with_name(f".{destination.name}.{secrets.token_hex(4)}.tmp")
    temporary.write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")
    _restrict_permissions(temporary)
    os.replace(temporary, destination)
    return destination


def _read_manifest(backup_path: Path) -> dict[str, Any]:
    manifest_path = _manifest_path(backup_path)
    if not manifest_path.is_file():
        raise ValueError(f"Backup manifest is missing: {manifest_path.name}")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    actual = _sha256(backup_path)
    if not secrets.compare_digest(str(manifest.get("sha256") or ""), actual):
        raise ValueError("Backup checksum does not match its manifest")
    if int(manifest.get("size_bytes") or -1) != backup_path.stat().st_size:
        raise ValueError("Backup size does not match its manifest")
    return manifest


def _sqlite_path(database_url: str) -> Path:
    parsed = make_url(database_url)
    if parsed.get_backend_name() != "sqlite" or not parsed.database or parsed.database == ":memory:":
        raise ValueError("A file-backed SQLite database URL is required")
    return Path(parsed.database).expanduser().resolve()


def _schema_revision_sqlite(connection: sqlite3.Connection) -> str | None:
    row = connection.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='alembic_version'"
    ).fetchone()
    if not row:
        return None
    revision = connection.execute("SELECT version_num FROM alembic_version LIMIT 1").fetchone()
    return str(revision[0]) if revision else None


def backup_sqlite(database_url: str, output_directory: Path) -> tuple[Path, Path]:
    source_path = _sqlite_path(database_url)
    if not source_path.is_file():
        raise ValueError("SQLite source database does not exist")
    output_directory = output_directory.expanduser().resolve()
    output_directory.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    destination = output_directory / f"sourceai-{stamp}-{secrets.token_hex(4)}.sqlite3"
    temporary = destination.with_name(f".{destination.name}.tmp")
    try:
        with closing(sqlite3.connect(source_path)) as source:
            with closing(sqlite3.connect(temporary)) as target:
                source.backup(target)
                integrity = target.execute("PRAGMA integrity_check").fetchone()
                if not integrity or integrity[0] != "ok":
                    raise RuntimeError("SQLite backup failed its integrity check")
                revision = _schema_revision_sqlite(target)
                table_count = int(
                    target.execute(
                        "SELECT count(*) FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
                    ).fetchone()[0]
                )
        _restrict_permissions(temporary)
        os.replace(temporary, destination)
    finally:
        if temporary.exists():
            temporary.unlink()
    manifest = {
        "format_version": 1,
        "database_engine": "sqlite",
        "backup_format": "sqlite-online-backup",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "sha256": _sha256(destination),
        "size_bytes": destination.stat().st_size,
        "schema_revision": revision,
        "table_count": table_count,
    }
    return destination, _write_manifest(destination, manifest)


def verify_sqlite_restore(backup_path: Path) -> dict[str, Any]:
    backup_path = backup_path.expanduser().resolve()
    manifest = _read_manifest(backup_path)
    if manifest.get("database_engine") != "sqlite":
        raise ValueError("Manifest is not for a SQLite backup")
    with tempfile.TemporaryDirectory(prefix="sourceai-restore-check-") as directory:
        restored_path = Path(directory) / "restored.sqlite3"
        shutil.copy2(backup_path, restored_path)
        with closing(sqlite3.connect(restored_path)) as restored:
            integrity = restored.execute("PRAGMA integrity_check").fetchone()
            if not integrity or integrity[0] != "ok":
                raise ValueError("Restored SQLite database failed integrity_check")
            tables = {
                str(row[0])
                for row in restored.execute(
                    "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
                )
            }
            missing = sorted(REQUIRED_TABLES - tables)
            if missing:
                raise ValueError(f"Restored database is missing required tables: {', '.join(missing)}")
            revision = _schema_revision_sqlite(restored)
    expected_revision = manifest.get("schema_revision")
    if expected_revision and revision != expected_revision:
        raise ValueError("Restored schema revision does not match the manifest")
    return {
        "ok": True,
        "database_engine": "sqlite",
        "schema_revision": revision,
        "table_count": len(tables),
    }


def _postgres_process(
    executable_name: str,
    database_url: str,
    extra_arguments: list[str],
) -> subprocess.CompletedProcess[str]:
    executable = shutil.which(executable_name)
    if not executable:
        raise RuntimeError(f"{executable_name} is not installed or not available on PATH")
    parsed = make_url(database_url)
    if parsed.get_backend_name() != "postgresql":
        raise ValueError("A PostgreSQL database URL is required")
    arguments = [
        executable,
        "--host",
        parsed.host or "localhost",
        "--port",
        str(parsed.port or 5432),
        "--username",
        parsed.username or "",
        "--dbname",
        parsed.database or "",
        *extra_arguments,
    ]
    environment = os.environ.copy()
    if parsed.password:
        environment["PGPASSWORD"] = parsed.password
    try:
        return subprocess.run(
            arguments,
            env=environment,
            check=True,
            capture_output=True,
            text=True,
        )
    except subprocess.CalledProcessError as exc:
        # Do not echo stderr: database tools can include host/user details.
        raise RuntimeError(
            f"{executable_name} failed with exit code {exc.returncode}"
        ) from None


def backup_postgresql(database_url: str, output_directory: Path) -> tuple[Path, Path]:
    output_directory = output_directory.expanduser().resolve()
    output_directory.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    destination = output_directory / f"sourceai-{stamp}-{secrets.token_hex(4)}.pgdump"
    temporary = destination.with_name(f".{destination.name}.tmp")
    try:
        _postgres_process(
            "pg_dump",
            database_url,
            ["--format=custom", "--no-owner", "--no-acl", "--file", str(temporary)],
        )
        if not temporary.is_file() or temporary.stat().st_size == 0:
            raise RuntimeError("pg_dump did not create a usable backup")
        _restrict_permissions(temporary)
        os.replace(temporary, destination)
    finally:
        if temporary.exists():
            temporary.unlink()

    engine = create_engine(database_url)
    try:
        with engine.connect() as connection:
            has_version = inspect(connection).has_table("alembic_version")
            revision = (
                connection.scalar(text("SELECT version_num FROM alembic_version LIMIT 1"))
                if has_version
                else None
            )
            table_count = len(inspect(connection).get_table_names())
    finally:
        engine.dispose()
    manifest = {
        "format_version": 1,
        "database_engine": "postgresql",
        "backup_format": "pg_dump-custom",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "sha256": _sha256(destination),
        "size_bytes": destination.stat().st_size,
        "schema_revision": revision,
        "table_count": table_count,
    }
    return destination, _write_manifest(destination, manifest)


def verify_postgresql_restore(backup_path: Path, empty_target_database_url: str) -> dict[str, Any]:
    backup_path = backup_path.expanduser().resolve()
    manifest = _read_manifest(backup_path)
    if manifest.get("database_engine") != "postgresql":
        raise ValueError("Manifest is not for a PostgreSQL backup")
    engine = create_engine(empty_target_database_url)
    try:
        existing_tables = inspect(engine).get_table_names()
        if existing_tables:
            raise ValueError("Restore target is not empty; refusing to overwrite any database")
    finally:
        engine.dispose()
    _postgres_process(
        "pg_restore",
        empty_target_database_url,
        ["--exit-on-error", "--no-owner", "--no-acl", str(backup_path)],
    )
    engine = create_engine(empty_target_database_url)
    try:
        inspector = inspect(engine)
        tables = set(inspector.get_table_names())
        missing = sorted(REQUIRED_TABLES - tables)
        if missing:
            raise ValueError(f"Restored database is missing required tables: {', '.join(missing)}")
        with engine.connect() as connection:
            revision = connection.scalar(text("SELECT version_num FROM alembic_version LIMIT 1"))
    finally:
        engine.dispose()
    if manifest.get("schema_revision") and revision != manifest["schema_revision"]:
        raise ValueError("Restored schema revision does not match the manifest")
    return {
        "ok": True,
        "database_engine": "postgresql",
        "schema_revision": revision,
        "table_count": len(tables),
    }
