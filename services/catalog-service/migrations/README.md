# Database migrations

This directory contains the production database migration history.

- The container entrypoint runs `alembic upgrade head` before starting Uvicorn.
- `CATALOG_DATABASE_URL` overrides the local SQLite URL in `alembic.ini`.
- The first revision is introspection-aware. It creates a complete schema in an
  empty database and adds only missing operations fields to a legacy or
  `metadata.create_all` database.
- Existing SQLite installations continue to use the additive compatibility
  upgrader. It never rebuilds a table, so existing rows remain intact.
- Re-running `alembic upgrade head` is safe after the revision is recorded.

No migration in this directory deletes live order, quote, payment, or audit
data.
