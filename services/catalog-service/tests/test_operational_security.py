from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

from app.db import Base
from app.models import AccountUser, AdminAuditEvent
from scripts.database_ops import backup_sqlite, verify_sqlite_restore
from scripts.provision_admin import provision_admin


def test_admin_provisioning_has_no_default_and_requires_first_login_mfa() -> None:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine, expire_on_commit=False) as session:
        admin = provision_admin(
            session,
            username="security-owner",
            email="owner@example.test",
            password="T9!rK4@wQ8#pSecure",
        )
        assert admin.role == "admin"
        assert admin.is_staff and admin.is_superuser and admin.is_active
        assert admin.mfa_enabled is False
        assert admin.password_hash != "T9!rK4@wQ8#pSecure"
        audit = session.scalar(
            select(AdminAuditEvent).where(AdminAuditEvent.action == "auth.admin.provisioned")
        )
        assert audit is not None and audit.entity_id == str(admin.id)

        with pytest.raises(ValueError, match="already provisioned"):
            provision_admin(
                session,
                username="security-owner",
                email="other@example.test",
                password="V8!nM4@qZ7#cSecure",
            )
        assert session.scalar(select(func.count()).select_from(AccountUser)) == 1
    engine.dispose()


def test_admin_provisioning_rejects_weak_password() -> None:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        with pytest.raises(ValueError, match="Password must contain"):
            provision_admin(
                session,
                username="new-owner",
                email="new-owner@example.test",
                password="password",
            )
        assert session.scalar(select(func.count()).select_from(AccountUser)) == 0
    engine.dispose()


def test_sqlite_backup_manifest_and_isolated_restore_verification(tmp_path: Path) -> None:
    source = tmp_path / "source.sqlite3"
    engine = create_engine(f"sqlite:///{source.as_posix()}")
    Base.metadata.create_all(engine)
    with engine.begin() as connection:
        connection.exec_driver_sql("CREATE TABLE alembic_version (version_num VARCHAR(32) NOT NULL)")
        connection.exec_driver_sql("INSERT INTO alembic_version VALUES ('20260730_02')")
    engine.dispose()

    backup, manifest = backup_sqlite(
        f"sqlite:///{source.as_posix()}",
        tmp_path / "backups",
    )
    assert backup.is_file() and manifest.is_file()
    metadata = json.loads(manifest.read_text(encoding="utf-8"))
    assert metadata["database_engine"] == "sqlite"
    assert metadata["schema_revision"] == "20260730_02"
    assert str(source) not in manifest.read_text(encoding="utf-8")

    result = verify_sqlite_restore(backup)
    assert result["ok"] is True
    assert result["schema_revision"] == "20260730_02"

    with backup.open("ab") as stream:
        stream.write(b"tampered")
    with pytest.raises(ValueError, match="checksum"):
        verify_sqlite_restore(backup)
