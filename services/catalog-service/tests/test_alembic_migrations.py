from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text


SERVICE_ROOT = Path(__file__).resolve().parents[1]
HEAD_REVISION = "20260827_07"
EXPECTED_TABLES = {
    "accounts_auth_challenges",
    "accounts_refresh_sessions",
    "accounts_social_identities",
    "accounts_users",
    "admin_audit_events",
    "ai_decision_explanations",
    "catalog_categories",
    "catalog_product_variants",
    "catalog_products",
    "customer_addresses",
    "customer_disputes",
    "customer_invoices",
    "customer_notification_preferences",
    "customer_notifications",
    "customer_profiles",
    "logistics_shipment_events",
    "logistics_shipments",
    "orders_manual_payments",
    "orders_payment_adjustments",
    "orders_payment_proof_attempts",
    "orders_payment_proof_decisions",
    "orders_order_items",
    "orders_orders",
    "orders_saved_quotes",
    "orders_status_history",
    "pricing_currency_rates",
    "pricing_duty_rules",
    "pricing_service_fee_rules",
    "notification_outbox",
    "shipping_eta_rules",
    "shipping_rate_cards",
    "sourcing_countries",
    "sourcing_seller_offers",
    "sourcing_sellers",
    "support_messages",
    "support_tickets",
}


def _sqlite_url(path: Path) -> str:
    return f"sqlite:///{path.as_posix()}"


def _upgrade_to_head(database_url: str, revision: str = "head") -> None:
    config = Config(str(SERVICE_ROOT / "alembic.ini"))
    config.set_main_option("sqlalchemy.url", database_url)
    with patch.dict(
        os.environ,
        {"CATALOG_DATABASE_URL": database_url},
        clear=False,
    ):
        try:
            command.upgrade(config, revision)
        finally:
            # app.db is imported by the migration metadata. Dispose its pooled
            # SQLite connection so Windows can remove the temporary database.
            database_module = sys.modules.get("app.db")
            application_engine = getattr(database_module, "engine", None)
            if application_engine is not None:
                application_engine.dispose()


class AlembicMigrationTests(unittest.TestCase):
    def test_latest_migration_configures_duty_and_repairs_known_catalog_rows(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            database_path = Path(directory) / "catalog-quality.sqlite3"
            database_url = _sqlite_url(database_path)
            _upgrade_to_head(database_url, "20260826_06")

            engine = create_engine(database_url)
            with engine.begin() as connection:
                connection.execute(
                    text("INSERT INTO sourcing_countries (id, code, name) VALUES (91, 'CN', 'China')")
                )
                connection.execute(
                    text(
                        "INSERT INTO catalog_categories (id, name, slug) "
                        "VALUES (91, 'Phones', 'phones')"
                    )
                )
                connection.execute(
                    text(
                        """
                        INSERT INTO catalog_products (id, name, slug, model, category_id)
                        VALUES (91, 'Buttom Phones', 'Phone', 'Nokia 1100', 91)
                        """
                    )
                )
                connection.execute(
                    text(
                        """
                        INSERT INTO catalog_product_variants (
                            id, product_id, sku, variant_name, weight_kg,
                            length_cm, width_cm, height_cm
                        )
                        VALUES (
                            91, 91, 'PHONE', '1100 model', 120.000,
                            200.00, 40.00, 20.00
                        )
                        """
                    )
                )
            engine.dispose()

            _upgrade_to_head(database_url)

            engine = create_engine(database_url)
            with engine.connect() as connection:
                duty = connection.execute(
                    text(
                        """
                        SELECT percent, fixed_bdt
                        FROM pricing_duty_rules
                        WHERE country_id = 91 AND category_id IS NULL AND is_active = 1
                        """
                    )
                ).one()
                product = connection.execute(
                    text(
                        "SELECT name, slug, model FROM catalog_products WHERE id = 91"
                    )
                ).one()
                variant = connection.execute(
                    text(
                        """
                        SELECT sku, variant_name, weight_kg, length_cm, width_cm, height_cm
                        FROM catalog_product_variants WHERE id = 91
                        """
                    )
                ).one()
            engine.dispose()

            self.assertEqual(tuple(duty), (5, 0))
            self.assertEqual(
                tuple(product),
                ("Nokia 1100 Feature Phone", "nokia-1100-feature-phone", "NOKIA-1100"),
            )
            self.assertEqual(tuple(variant[:2]), ("NOKIA-1100-STD", "Standard"))
            self.assertEqual(tuple(float(value) for value in variant[2:]), (0.12, 10.6, 4.6, 2.0))

    def test_revision_four_normalizes_legacy_seller_account_role(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            database_path = Path(directory) / "seller-role.sqlite3"
            database_url = _sqlite_url(database_path)
            _upgrade_to_head(database_url, "20260730_03")
            engine = create_engine(database_url)
            with engine.begin() as connection:
                connection.execute(
                    text(
                        """
                        INSERT INTO accounts_users (
                            id, username, email, password_hash, role, is_active,
                            is_staff, is_superuser, failed_login_attempts,
                            auth_version, mfa_enabled, mfa_recovery_hashes
                        )
                        VALUES (
                            999, 'legacy-seller', 'legacy-seller@example.test',
                            'not-used', 'seller', 1, 1, 1, 0, 3, 0, '[]'
                        )
                        """
                    )
                )
            engine.dispose()

            _upgrade_to_head(database_url)
            engine = create_engine(database_url)
            with engine.connect() as connection:
                role = connection.execute(
                    text(
                        """
                        SELECT role, is_staff, is_superuser, auth_version
                        FROM accounts_users
                        WHERE id = 999
                        """
                    )
                ).one()
            self.assertEqual(tuple(role), ("customer", 0, 0, 4))
            engine.dispose()

    def test_upgrade_head_creates_fresh_sqlite_schema(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            database_path = Path(directory) / "fresh.sqlite3"
            database_url = _sqlite_url(database_path)

            _upgrade_to_head(database_url)
            # A second invocation must be a no-op rather than reapplying DDL.
            _upgrade_to_head(database_url)

            engine = create_engine(database_url)
            inspector = inspect(engine)
            self.assertTrue(EXPECTED_TABLES.issubset(set(inspector.get_table_names())))
            self.assertEqual(
                {
                    column["name"]
                    for column in inspector.get_columns("orders_manual_payments")
                },
                {
                    "id",
                    "order_id",
                    "channel",
                    "trx_id",
                    "trx_normalized",
                    "screenshot_url",
                    "verified",
                    "verified_at",
                    "decision",
                    "decision_reason",
                    "decided_at",
                    "decided_by_user_id",
                    "created_at",
                },
            )
            with engine.connect() as connection:
                self.assertEqual(
                    connection.scalar(text("SELECT version_num FROM alembic_version")),
                    HEAD_REVISION,
                )
            engine.dispose()

    def test_upgrade_head_preserves_and_upgrades_legacy_sqlite(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            database_path = Path(directory) / "legacy.sqlite3"
            database_url = _sqlite_url(database_path)
            engine = create_engine(database_url)
            with engine.begin() as connection:
                connection.execute(
                    text(
                        """
                        CREATE TABLE orders_saved_quotes (
                            id INTEGER PRIMARY KEY,
                            user_id INTEGER NOT NULL,
                            variant_id INTEGER NOT NULL,
                            product_name VARCHAR(200) NOT NULL,
                            variant_name VARCHAR(120) NOT NULL,
                            country_code VARCHAR(2) NOT NULL,
                            mode VARCHAR(10) NOT NULL,
                            delivery_type VARCHAR(10) NOT NULL,
                            qty INTEGER NOT NULL,
                            response JSON NOT NULL,
                            created_at DATETIME
                        )
                        """
                    )
                )
                connection.execute(
                    text(
                        """
                        CREATE TABLE orders_orders (
                            id INTEGER PRIMARY KEY,
                            user_id INTEGER NOT NULL,
                            country_code VARCHAR(2) NOT NULL,
                            mode VARCHAR(10) NOT NULL,
                            delivery_type VARCHAR(10) NOT NULL,
                            status VARCHAR(20),
                            total_bdt NUMERIC(12, 2),
                            shipping_bdt NUMERIC(12, 2),
                            advance_bdt NUMERIC(12, 2),
                            remaining_bdt NUMERIC(12, 2),
                            created_at DATETIME
                        )
                        """
                    )
                )
                connection.execute(
                    text(
                        """
                        CREATE TABLE orders_manual_payments (
                            id INTEGER PRIMARY KEY,
                            order_id INTEGER NOT NULL UNIQUE,
                            channel VARCHAR(20),
                            trx_id VARCHAR(80) NOT NULL,
                            screenshot_url VARCHAR(500),
                            verified BOOLEAN,
                            verified_at DATETIME,
                            created_at DATETIME
                        )
                        """
                    )
                )
                connection.execute(
                    text(
                        """
                        INSERT INTO orders_saved_quotes (
                            id, user_id, variant_id, product_name, variant_name,
                            country_code, mode, delivery_type, qty, response, created_at
                        )
                        VALUES (
                            7, 15, 20, 'Legacy monitor', 'Standard',
                            'CN', 'LOCAL', 'DOOR', 2,
                            '{"status":"approved","expires_at":"2030-01-01T00:00:00+00:00"}',
                            CURRENT_TIMESTAMP
                        )
                        """
                    )
                )
                connection.execute(
                    text(
                        """
                        INSERT INTO orders_orders (
                            id, user_id, country_code, mode, delivery_type,
                            status, total_bdt, shipping_bdt, advance_bdt,
                            remaining_bdt, created_at
                        )
                        VALUES (
                            11, 15, 'CN', 'LOCAL', 'DOOR', 'PENDING',
                            1000.00, 100.00, 600.00, 400.00, CURRENT_TIMESTAMP
                        )
                        """
                    )
                )
                connection.execute(
                    text(
                        """
                        INSERT INTO orders_manual_payments (
                            id, order_id, channel, trx_id, verified,
                            verified_at, created_at
                        )
                        VALUES (
                            13, 11, 'bKash', 'TX- LEGACY-01', 1,
                            CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
                        )
                        """
                    )
                )
            engine.dispose()

            _upgrade_to_head(database_url)
            _upgrade_to_head(database_url)

            engine = create_engine(database_url)
            inspector = inspect(engine)
            self.assertTrue(EXPECTED_TABLES.issubset(set(inspector.get_table_names())))
            self.assertTrue(
                {
                    "saved_quote_id",
                    "quote_snapshot",
                    "idempotency_key",
                    "updated_at",
                }.issubset(
                    {
                        column["name"]
                        for column in inspector.get_columns("orders_orders")
                    }
                )
            )
            with engine.connect() as connection:
                legacy_order = connection.execute(
                    text(
                        """
                        SELECT status, total_bdt
                        FROM orders_orders
                        WHERE id = 11
                        """
                    )
                ).one()
                payment = connection.execute(
                    text(
                        """
                        SELECT trx_id, trx_normalized, decision
                        FROM orders_manual_payments
                        WHERE id = 13
                        """
                    )
                ).one()
                quote_status = connection.scalar(
                    text("SELECT status FROM orders_saved_quotes WHERE id = 7")
                )
                payment_attempt = connection.execute(
                    text(
                        """
                        SELECT attempt.attempt_number, attempt.trx_id, decision.decision
                        FROM orders_payment_proof_attempts AS attempt
                        JOIN orders_payment_proof_decisions AS decision
                          ON decision.attempt_id = attempt.id
                        WHERE attempt.payment_id = 13
                        """
                    )
                ).one()
                revision = connection.scalar(
                    text("SELECT version_num FROM alembic_version")
                )

            self.assertEqual(tuple(legacy_order), ("PENDING", 1000))
            self.assertEqual(
                tuple(payment),
                ("TX- LEGACY-01", "txlegacy01", "APPROVED"),
            )
            self.assertEqual(quote_status, "approved")
            self.assertEqual(tuple(payment_attempt), (1, "TX- LEGACY-01", "APPROVED"))
            self.assertEqual(revision, HEAD_REVISION)
            engine.dispose()


if __name__ == "__main__":
    unittest.main()
