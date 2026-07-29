"""Add persistent lockout, MFA challenges, and revocable refresh sessions.

Revision ID: 20260730_02
Revises: 20260729_01
"""

from __future__ import annotations

from typing import Any

from alembic import op
import sqlalchemy as sa
from sqlalchemy.engine import Connection


revision = "20260730_02"
down_revision = "20260729_01"
branch_labels = None
depends_on = None


def _table_exists(bind: Connection, table_name: str) -> bool:
    return sa.inspect(bind).has_table(table_name)


def _columns(bind: Connection, table_name: str) -> set[str]:
    if not _table_exists(bind, table_name):
        return set()
    return {column["name"] for column in sa.inspect(bind).get_columns(table_name)}


def _ensure_column(bind: Connection, table_name: str, column: sa.Column[Any]) -> None:
    if column.name not in _columns(bind, table_name):
        op.add_column(table_name, column)


def _ensure_index(
    bind: Connection,
    name: str,
    table_name: str,
    columns: tuple[str, ...],
    *,
    unique: bool = False,
) -> None:
    if not _table_exists(bind, table_name):
        return
    inspector = sa.inspect(bind)
    for index in inspector.get_indexes(table_name):
        if index.get("name") == name:
            return
        if tuple(index.get("column_names") or ()) == columns and bool(index.get("unique")) == unique:
            return
    if unique:
        for constraint in inspector.get_unique_constraints(table_name):
            if tuple(constraint.get("column_names") or ()) == columns:
                return
    op.create_index(name, table_name, list(columns), unique=unique)


def _create_challenges(bind: Connection) -> None:
    if not _table_exists(bind, "accounts_auth_challenges"):
        op.create_table(
            "accounts_auth_challenges",
            sa.Column("id", sa.String(length=64), primary_key=True),
            sa.Column("user_id", sa.Integer(), nullable=False),
            sa.Column("purpose", sa.String(length=30), nullable=False),
            sa.Column("remember", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("failed_attempts", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("consumed_at", sa.DateTime(timezone=True)),
            sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.ForeignKeyConstraint(["user_id"], ["accounts_users.id"]),
        )
    _ensure_index(bind, "ix_auth_challenges_user_id", "accounts_auth_challenges", ("user_id",))
    _ensure_index(bind, "ix_auth_challenges_expires_at", "accounts_auth_challenges", ("expires_at",))


def _create_refresh_sessions(bind: Connection) -> None:
    if not _table_exists(bind, "accounts_refresh_sessions"):
        op.create_table(
            "accounts_refresh_sessions",
            sa.Column("id", sa.String(length=64), primary_key=True),
            sa.Column("user_id", sa.Integer(), nullable=False),
            sa.Column("family_id", sa.String(length=64), nullable=False),
            sa.Column("token_hash", sa.String(length=64), nullable=False),
            sa.Column("remember", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("last_used_at", sa.DateTime(timezone=True)),
            sa.Column("revoked_at", sa.DateTime(timezone=True)),
            sa.Column("revoke_reason", sa.String(length=40)),
            sa.Column("replaced_by_id", sa.String(length=64)),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.ForeignKeyConstraint(["user_id"], ["accounts_users.id"]),
        )
    _ensure_index(bind, "ix_refresh_sessions_user_id", "accounts_refresh_sessions", ("user_id",))
    _ensure_index(bind, "ix_refresh_sessions_family_id", "accounts_refresh_sessions", ("family_id",))
    _ensure_index(bind, "ix_refresh_sessions_token_hash", "accounts_refresh_sessions", ("token_hash",), unique=True)
    _ensure_index(bind, "ix_refresh_sessions_expires_at", "accounts_refresh_sessions", ("expires_at",))
    _ensure_index(bind, "ix_refresh_sessions_revoked_at", "accounts_refresh_sessions", ("revoked_at",))


def upgrade() -> None:
    bind = op.get_bind()
    if not _table_exists(bind, "accounts_users"):
        from app.db import Base
        from app import models  # noqa: F401

        Base.metadata.create_all(bind=bind, checkfirst=True)
        return

    for column in (
        sa.Column("failed_login_attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("locked_until", sa.DateTime(timezone=True)),
        sa.Column("last_failed_login_at", sa.DateTime(timezone=True)),
        sa.Column("last_login_at", sa.DateTime(timezone=True)),
        sa.Column("auth_version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("mfa_enabled", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("mfa_secret_encrypted", sa.Text()),
        sa.Column("mfa_recovery_hashes", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("mfa_enrolled_at", sa.DateTime(timezone=True)),
    ):
        _ensure_column(bind, "accounts_users", column)

    _ensure_index(bind, "ix_accounts_users_locked_until", "accounts_users", ("locked_until",))
    _create_challenges(bind)
    _create_refresh_sessions(bind)


def downgrade() -> None:
    # Authentication state is security/audit material. An automated downgrade
    # must not silently delete it.
    pass
