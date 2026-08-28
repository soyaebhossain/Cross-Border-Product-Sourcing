"""Normalize login identifiers and harden authenticator verification.

Revision ID: 20260826_06
Revises: 20260806_05
"""

from __future__ import annotations

import unicodedata
from collections import Counter
from typing import Any

from alembic import op
import sqlalchemy as sa
from sqlalchemy.engine import Connection


revision = "20260826_06"
down_revision = "20260806_05"
branch_labels = None
depends_on = None


def _columns(bind: Connection) -> set[str]:
    if not sa.inspect(bind).has_table("accounts_users"):
        return set()
    return {
        str(column["name"])
        for column in sa.inspect(bind).get_columns("accounts_users")
    }


def _ensure_column(bind: Connection, column: sa.Column[Any]) -> None:
    if column.name not in _columns(bind):
        op.add_column("accounts_users", column)


def _key(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = unicodedata.normalize("NFKC", value).strip().casefold()
    return normalized or None


def _backfill_identifiers(bind: Connection) -> None:
    rows = list(
        bind.execute(
            sa.text("SELECT id, username, email, phone FROM accounts_users")
        ).mappings()
    )
    normalized_rows = [
        {
            "id": int(row["id"]),
            "username": _key(row["username"]),
            "email": _key(row["email"]),
            "phone": _key(row["phone"]),
        }
        for row in rows
    ]
    for field in ("username", "email", "phone"):
        counts = Counter(
            row[field] for row in normalized_rows if row[field] is not None
        )
        duplicates = {value for value, count in counts.items() if count > 1}
        if duplicates:
            duplicate_ids = sorted(
                row["id"] for row in normalized_rows if row[field] in duplicates
            )
            raise RuntimeError(
                "Normalized account identity collision in "
                f"{field}; resolve account IDs {duplicate_ids} before migrating"
            )
    for row in normalized_rows:
        bind.execute(
            sa.text(
                """
                UPDATE accounts_users
                SET username_normalized = :username,
                    email_normalized = :email,
                    phone_normalized = :phone
                WHERE id = :id
                """
            ),
            row,
        )


def _ensure_index(
    bind: Connection,
    name: str,
    columns: tuple[str, ...],
    *,
    unique: bool = False,
) -> None:
    inspector = sa.inspect(bind)
    for index in inspector.get_indexes("accounts_users"):
        if index.get("name") == name:
            return
        if (
            tuple(index.get("column_names") or ()) == columns
            and bool(index.get("unique")) == unique
        ):
            return
    op.create_index(name, "accounts_users", list(columns), unique=unique)


def _normalize_and_constrain_skus(bind: Connection) -> None:
    table_name = "catalog_product_variants"
    if not sa.inspect(bind).has_table(table_name):
        return
    rows = list(
        bind.execute(sa.text(f"SELECT id, sku FROM {table_name}")).mappings()
    )
    normalized = [
        {
            "id": int(row["id"]),
            "sku": (
                unicodedata.normalize("NFKC", str(row["sku"])).strip().upper()
                if row["sku"] is not None
                else None
            ),
        }
        for row in rows
    ]
    counts = Counter(row["sku"] for row in normalized if row["sku"])
    duplicate_skus = {value for value, count in counts.items() if count > 1}
    if duplicate_skus:
        duplicate_ids = sorted(
            row["id"] for row in normalized if row["sku"] in duplicate_skus
        )
        raise RuntimeError(
            "Normalized product SKU collision; resolve variant IDs "
            f"{duplicate_ids} before migrating"
        )
    for row in normalized:
        bind.execute(
            sa.text(
                "UPDATE catalog_product_variants SET sku = :sku WHERE id = :id"
            ),
            {"id": row["id"], "sku": row["sku"] or None},
        )
    inspector = sa.inspect(bind)
    if not any(
        tuple(index.get("column_names") or ()) == ("sku",)
        and bool(index.get("unique"))
        for index in inspector.get_indexes(table_name)
    ) and not any(
        tuple(constraint.get("column_names") or ()) == ("sku",)
        for constraint in inspector.get_unique_constraints(table_name)
    ):
        op.create_index(
            "ix_catalog_product_variants_sku",
            table_name,
            ["sku"],
            unique=True,
        )


def upgrade() -> None:
    bind = op.get_bind()
    if not sa.inspect(bind).has_table("accounts_users"):
        from app import models  # noqa: F401
        from app.db import Base

        Base.metadata.create_all(bind=bind, checkfirst=True)
        return

    for column in (
        sa.Column("username_normalized", sa.String(length=150)),
        sa.Column("email_normalized", sa.String(length=254)),
        sa.Column("phone_normalized", sa.String(length=40)),
        sa.Column(
            "mfa_failed_attempts",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
        sa.Column("mfa_locked_until", sa.DateTime(timezone=True)),
        sa.Column("last_totp_counter", sa.BigInteger()),
    ):
        _ensure_column(bind, column)

    _backfill_identifiers(bind)
    _ensure_index(
        bind,
        "ix_accounts_users_username_normalized",
        ("username_normalized",),
        unique=True,
    )
    _ensure_index(
        bind,
        "ix_accounts_users_email_normalized",
        ("email_normalized",),
        unique=True,
    )
    _ensure_index(
        bind,
        "ix_accounts_users_phone_normalized",
        ("phone_normalized",),
        unique=True,
    )
    _ensure_index(
        bind,
        "ix_accounts_users_mfa_locked_until",
        ("mfa_locked_until",),
    )
    _normalize_and_constrain_skus(bind)


def downgrade() -> None:
    # Identity keys and MFA replay state are security data and are intentionally
    # retained by automated downgrades.
    pass
