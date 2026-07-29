from __future__ import annotations

from logging.config import fileConfig
import os

from alembic import context
from sqlalchemy import engine_from_config, pool

from app.config import SERVICE_DIR, Settings

config = context.config
if config.config_file_name:
    fileConfig(config.config_file_name)

# Use the same pydantic-settings resolution as the API. This loads the local
# service .env for operator-run migrations while still allowing deployment
# environment variables to take precedence. A programmatically overridden
# Alembic URL remains authoritative for isolated migration tests and tooling.
configured_url = config.get_main_option("sqlalchemy.url")
fallback_url = "sqlite:///./catalog.sqlite3"
if os.getenv("CATALOG_DATABASE_URL"):
    runtime_settings = Settings()
    runtime_settings.validate_runtime_security()
    database_url = runtime_settings.database_url
elif configured_url != fallback_url:
    database_url = configured_url
elif (SERVICE_DIR / ".env").is_file():
    runtime_settings = Settings()
    runtime_settings.validate_runtime_security()
    database_url = runtime_settings.database_url
else:
    database_url = configured_url
# ConfigParser treats percent signs in escaped database passwords as
# interpolation tokens. Doubling them preserves the actual URL.
config.set_main_option("sqlalchemy.url", database_url.replace("%", "%%"))

from app import models  # noqa: E402, F401 - registers SQLAlchemy metadata
from app.db import Base  # noqa: E402


target_metadata = Base.metadata


def run_migrations_offline() -> None:
    context.configure(
        url=config.get_main_option("sqlalchemy.url"),
        target_metadata=target_metadata,
        literal_binds=True,
        compare_type=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
            transaction_per_migration=True,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
