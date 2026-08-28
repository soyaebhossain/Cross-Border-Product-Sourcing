from __future__ import annotations

"""Small, additive runtime upgrades for existing SQLite deployments.

The production path should use Alembic. This module exists because the current
single-file SQLite deployment predates Alembic and ``metadata.create_all`` does
not add columns. Every statement here is additive or a data backfill; no table,
column, or row is removed.
"""

import unicodedata
from collections import Counter
from collections.abc import Iterable

from sqlalchemy import Engine, inspect, text
from sqlalchemy.exc import IntegrityError, OperationalError


def _existing_columns(connection, table_name: str) -> set[str]:
    return {column["name"] for column in inspect(connection).get_columns(table_name)}


def _add_columns(
    connection,
    table_name: str,
    definitions: Iterable[tuple[str, str]],
) -> None:
    if not inspect(connection).has_table(table_name):
        return
    columns = _existing_columns(connection, table_name)
    for name, definition in definitions:
        if name not in columns:
            connection.execute(text(f'ALTER TABLE "{table_name}" ADD COLUMN "{name}" {definition}'))
            columns.add(name)


def _execute_best_effort(connection, statement: str) -> None:
    try:
        connection.execute(text(statement))
    except (IntegrityError, OperationalError):
        # A legacy database can contain duplicates or lack SQLite JSON1. The
        # application layer still enforces the invariant and the migration can
        # be completed after an operator resolves the legacy rows.
        pass


def _identity_key(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = unicodedata.normalize("NFKC", value).strip().casefold()
    return normalized or None


def _backfill_sqlite_identity_keys(connection) -> None:
    if not inspect(connection).has_table("accounts_users"):
        return
    required = {
        "username_normalized",
        "email_normalized",
        "phone_normalized",
    }
    if not required.issubset(_existing_columns(connection, "accounts_users")):
        return
    rows = list(
        connection.execute(
            text("SELECT id, username, email, phone FROM accounts_users")
        ).mappings()
    )
    normalized = [
        {
            "id": int(row["id"]),
            "username": _identity_key(row["username"]),
            "email": _identity_key(row["email"]),
            "phone": _identity_key(row["phone"]),
        }
        for row in rows
    ]
    duplicate_values: dict[str, set[str]] = {}
    for field in ("username", "email", "phone"):
        counts = Counter(row[field] for row in normalized if row[field] is not None)
        duplicate_values[field] = {
            value for value, count in counts.items() if count > 1
        }
    for row in normalized:
        connection.execute(
            text(
                """
                UPDATE accounts_users
                SET username_normalized = :username,
                    email_normalized = :email,
                    phone_normalized = :phone
                WHERE id = :id
                """
            ),
            {
                "id": row["id"],
                "username": (
                    None
                    if row["username"] in duplicate_values["username"]
                    else row["username"]
                ),
                "email": (
                    None
                    if row["email"] in duplicate_values["email"]
                    else row["email"]
                ),
                "phone": (
                    None
                    if row["phone"] in duplicate_values["phone"]
                    else row["phone"]
                ),
            },
        )


def _normalize_sqlite_skus(connection) -> None:
    table_name = "catalog_product_variants"
    if not inspect(connection).has_table(table_name):
        return
    rows = list(
        connection.execute(text(f"SELECT id, sku FROM {table_name}")).mappings()
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
    duplicates = {value for value, count in counts.items() if count > 1}
    for row in normalized:
        if row["sku"] in duplicates:
            continue
        connection.execute(
            text(f"UPDATE {table_name} SET sku = :sku WHERE id = :id"),
            row,
        )


def upgrade_sqlite_schema(engine: Engine) -> None:
    if engine.dialect.name != "sqlite":
        return

    with engine.begin() as connection:
        _add_columns(
            connection,
            "orders_saved_quotes",
            (
                ("status", "VARCHAR(20) NOT NULL DEFAULT 'requested'"),
                ("expires_at", "DATETIME"),
                ("updated_at", "DATETIME"),
            ),
        )
        for table_name in (
            "catalog_categories",
            "catalog_products",
            "catalog_product_variants",
            "sourcing_sellers",
            "sourcing_seller_offers",
            "pricing_currency_rates",
            "pricing_service_fee_rules",
            "shipping_rate_cards",
            "shipping_eta_rules",
        ):
            _add_columns(
                connection,
                table_name,
                (
                    ("is_active", "BOOLEAN NOT NULL DEFAULT 1"),
                    ("archived_at", "DATETIME"),
                    ("archived_by_user_id", "INTEGER"),
                    ("updated_at", "DATETIME"),
                ),
            )
        _add_columns(
            connection,
            "orders_orders",
            (
                ("saved_quote_id", "INTEGER"),
                ("quote_snapshot", "JSON"),
                ("idempotency_key", "VARCHAR(80)"),
                ("actual_cost_bdt", "NUMERIC(12, 2)"),
                ("promised_delivery_at", "DATETIME"),
                ("delivered_at", "DATETIME"),
                ("quality_defect_reported", "BOOLEAN NOT NULL DEFAULT 0"),
                ("updated_at", "DATETIME"),
            ),
        )
        _add_columns(
            connection,
            "orders_status_history",
            (
                ("previous_status", "VARCHAR(20)"),
                ("actor_user_id", "INTEGER"),
                ("actor_role", "VARCHAR(20)"),
                ("request_id", "VARCHAR(100)"),
            ),
        )
        _add_columns(
            connection,
            "orders_manual_payments",
            (
                ("trx_normalized", "VARCHAR(80)"),
                ("decision", "VARCHAR(20) NOT NULL DEFAULT 'PENDING'"),
                ("decision_reason", "TEXT"),
                ("decided_at", "DATETIME"),
                ("decided_by_user_id", "INTEGER"),
            ),
        )
        _add_columns(
            connection,
            "accounts_users",
            (
                ("failed_login_attempts", "INTEGER NOT NULL DEFAULT 0"),
                ("locked_until", "DATETIME"),
                ("last_failed_login_at", "DATETIME"),
                ("last_login_at", "DATETIME"),
                ("auth_version", "INTEGER NOT NULL DEFAULT 1"),
                ("mfa_enabled", "BOOLEAN NOT NULL DEFAULT 0"),
                ("mfa_secret_encrypted", "TEXT"),
                ("mfa_recovery_hashes", "JSON NOT NULL DEFAULT '[]'"),
                ("mfa_enrolled_at", "DATETIME"),
                ("username_normalized", "VARCHAR(150)"),
                ("email_normalized", "VARCHAR(254)"),
                ("phone_normalized", "VARCHAR(40)"),
                ("mfa_failed_attempts", "INTEGER NOT NULL DEFAULT 0"),
                ("mfa_locked_until", "DATETIME"),
                ("last_totp_counter", "BIGINT"),
            ),
        )
        _backfill_sqlite_identity_keys(connection)
        _normalize_sqlite_skus(connection)

        if inspect(connection).has_table("orders_saved_quotes"):
            _execute_best_effort(
                connection,
                """
                UPDATE orders_saved_quotes
                SET status = COALESCE(NULLIF(json_extract(response, '$.status'), ''), status, 'requested'),
                    expires_at = COALESCE(expires_at, json_extract(response, '$.expires_at')),
                    updated_at = COALESCE(updated_at, created_at, CURRENT_TIMESTAMP)
                """,
            )
        if inspect(connection).has_table("orders_orders"):
            connection.execute(
                text(
                    """
                    UPDATE orders_orders
                    SET updated_at = COALESCE(updated_at, created_at, CURRENT_TIMESTAMP)
                    """
                )
            )
        for table_name in (
            "catalog_categories",
            "catalog_products",
            "catalog_product_variants",
            "sourcing_sellers",
            "sourcing_seller_offers",
            "pricing_currency_rates",
            "pricing_service_fee_rules",
            "shipping_rate_cards",
            "shipping_eta_rules",
        ):
            if inspect(connection).has_table(table_name):
                connection.execute(
                    text(
                        f"""
                        UPDATE "{table_name}"
                        SET is_active = COALESCE(is_active, 1),
                            updated_at = COALESCE(updated_at, CURRENT_TIMESTAMP)
                        """
                    )
                )
        if inspect(connection).has_table("orders_manual_payments"):
            connection.execute(
                text(
                    """
                    UPDATE orders_manual_payments
                    SET trx_normalized = COALESCE(
                            NULLIF(trx_normalized, ''),
                            lower(replace(replace(trim(trx_id), ' ', ''), '-', ''))
                        ),
                        decision = CASE
                            WHEN verified = 1 THEN 'APPROVED'
                            WHEN decision IS NULL OR decision = '' THEN 'PENDING'
                            ELSE decision
                        END,
                        decided_at = CASE
                            WHEN verified = 1 THEN COALESCE(decided_at, verified_at)
                            ELSE decided_at
                        END
                    """
                )
            )

        connection.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS admin_audit_events (
                    id INTEGER NOT NULL PRIMARY KEY,
                    actor_user_id INTEGER NOT NULL,
                    actor_role VARCHAR(20) NOT NULL,
                    action VARCHAR(80) NOT NULL,
                    entity_type VARCHAR(50) NOT NULL,
                    entity_id VARCHAR(80) NOT NULL,
                    request_id VARCHAR(100),
                    before_data JSON,
                    after_data JSON,
                    note TEXT,
                    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
        )
        if inspect(connection).has_table("accounts_users"):
            connection.execute(
                text(
                    """
                    CREATE TABLE IF NOT EXISTS accounts_auth_challenges (
                        id VARCHAR(64) NOT NULL PRIMARY KEY,
                        user_id INTEGER NOT NULL REFERENCES accounts_users(id),
                        purpose VARCHAR(30) NOT NULL,
                        remember BOOLEAN NOT NULL DEFAULT 1,
                        failed_attempts INTEGER NOT NULL DEFAULT 0,
                        consumed_at DATETIME,
                        expires_at DATETIME NOT NULL,
                        created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
                    )
                    """
                )
            )
            connection.execute(
                text(
                    """
                    CREATE TABLE IF NOT EXISTS accounts_refresh_sessions (
                        id VARCHAR(64) NOT NULL PRIMARY KEY,
                        user_id INTEGER NOT NULL REFERENCES accounts_users(id),
                        family_id VARCHAR(64) NOT NULL,
                        token_hash VARCHAR(64) NOT NULL UNIQUE,
                        remember BOOLEAN NOT NULL DEFAULT 1,
                        expires_at DATETIME NOT NULL,
                        last_used_at DATETIME,
                        revoked_at DATETIME,
                        revoke_reason VARCHAR(40),
                        replaced_by_id VARCHAR(64),
                        created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
                    )
                    """
                )
            )

        for statement in (
            "CREATE INDEX IF NOT EXISTS ix_accounts_users_locked_until ON accounts_users (locked_until)",
            "CREATE UNIQUE INDEX IF NOT EXISTS ix_accounts_users_username_normalized ON accounts_users (username_normalized)",
            "CREATE UNIQUE INDEX IF NOT EXISTS ix_accounts_users_email_normalized ON accounts_users (email_normalized)",
            "CREATE UNIQUE INDEX IF NOT EXISTS ix_accounts_users_phone_normalized ON accounts_users (phone_normalized)",
            "CREATE INDEX IF NOT EXISTS ix_accounts_users_mfa_locked_until ON accounts_users (mfa_locked_until)",
            "CREATE INDEX IF NOT EXISTS ix_auth_challenges_user_id ON accounts_auth_challenges (user_id)",
            "CREATE INDEX IF NOT EXISTS ix_auth_challenges_expires_at ON accounts_auth_challenges (expires_at)",
            "CREATE INDEX IF NOT EXISTS ix_refresh_sessions_user_id ON accounts_refresh_sessions (user_id)",
            "CREATE INDEX IF NOT EXISTS ix_refresh_sessions_family_id ON accounts_refresh_sessions (family_id)",
            "CREATE INDEX IF NOT EXISTS ix_refresh_sessions_expires_at ON accounts_refresh_sessions (expires_at)",
            "CREATE INDEX IF NOT EXISTS ix_refresh_sessions_revoked_at ON accounts_refresh_sessions (revoked_at)",
            "CREATE INDEX IF NOT EXISTS ix_saved_quotes_status ON orders_saved_quotes (status)",
            "CREATE INDEX IF NOT EXISTS ix_saved_quotes_expires_at ON orders_saved_quotes (expires_at)",
            "CREATE INDEX IF NOT EXISTS ix_orders_saved_quote_id ON orders_orders (saved_quote_id)",
            "CREATE INDEX IF NOT EXISTS ix_orders_created_at ON orders_orders (created_at)",
            "CREATE INDEX IF NOT EXISTS ix_orders_status ON orders_orders (status)",
            "CREATE INDEX IF NOT EXISTS ix_orders_promised_delivery_at ON orders_orders (promised_delivery_at)",
            "CREATE INDEX IF NOT EXISTS ix_orders_delivered_at ON orders_orders (delivered_at)",
            "CREATE INDEX IF NOT EXISTS ix_order_history_request_id ON orders_status_history (request_id)",
            "CREATE INDEX IF NOT EXISTS ix_categories_is_active ON catalog_categories (is_active)",
            "CREATE INDEX IF NOT EXISTS ix_products_is_active ON catalog_products (is_active)",
            "CREATE INDEX IF NOT EXISTS ix_variants_is_active ON catalog_product_variants (is_active)",
            "CREATE UNIQUE INDEX IF NOT EXISTS ix_catalog_product_variants_sku ON catalog_product_variants (sku)",
            "CREATE INDEX IF NOT EXISTS ix_sellers_is_active ON sourcing_sellers (is_active)",
            "CREATE INDEX IF NOT EXISTS ix_offers_is_active ON sourcing_seller_offers (is_active)",
            "CREATE INDEX IF NOT EXISTS ix_manual_payments_decision ON orders_manual_payments (decision)",
            "CREATE INDEX IF NOT EXISTS ix_manual_payments_created_at ON orders_manual_payments (created_at)",
            "CREATE INDEX IF NOT EXISTS ix_admin_audit_actor ON admin_audit_events (actor_user_id)",
            "CREATE INDEX IF NOT EXISTS ix_admin_audit_action ON admin_audit_events (action)",
            "CREATE INDEX IF NOT EXISTS ix_admin_audit_entity ON admin_audit_events (entity_type, entity_id)",
            "CREATE INDEX IF NOT EXISTS ix_admin_audit_created_at ON admin_audit_events (created_at)",
            """
            CREATE UNIQUE INDEX IF NOT EXISTS uq_orders_user_idempotency
            ON orders_orders (user_id, idempotency_key)
            WHERE idempotency_key IS NOT NULL
            """,
            """
            CREATE UNIQUE INDEX IF NOT EXISTS uq_orders_saved_quote
            ON orders_orders (saved_quote_id)
            WHERE saved_quote_id IS NOT NULL
            """,
            """
            CREATE UNIQUE INDEX IF NOT EXISTS uq_manual_payment_channel_transaction
            ON orders_manual_payments (lower(channel), trx_normalized)
            WHERE trx_normalized IS NOT NULL AND trx_normalized <> ''
            """,
        ):
            _execute_best_effort(connection, statement)
