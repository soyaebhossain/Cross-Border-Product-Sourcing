#!/bin/sh
set -eu

attempt=1
max_attempts="${MIGRATION_MAX_ATTEMPTS:-10}"
retry_seconds="${MIGRATION_RETRY_SECONDS:-3}"

until alembic upgrade head; do
    if [ "$attempt" -ge "$max_attempts" ]; then
        echo "Database migration failed after ${attempt} attempts." >&2
        exit 1
    fi

    echo "Database migration attempt ${attempt} failed; retrying in ${retry_seconds}s." >&2
    attempt=$((attempt + 1))
    sleep "$retry_seconds"
done

# A fresh database has no catalog. When enabled, load the PII-free demo
# catalog; it only adds missing rows, so it is safe on every deploy.
case "${CATALOG_SEED_PUBLIC_CATALOG:-false}" in
    1|true|TRUE|True|yes)
        python -m scripts.seed_public_catalog
        ;;
esac

# Hosts without a shell (such as Render's free plan) can create the first
# administrator by setting SOURCEAI_ADMIN_USERNAME, SOURCEAI_ADMIN_EMAIL and
# SOURCEAI_ADMIN_PASSWORD. An existing account is never changed, and MFA
# enrollment is still required at the first admin sign-in. Remove the three
# variables once the administrator has signed in.
if [ -n "${SOURCEAI_ADMIN_USERNAME:-}" ] && [ -n "${SOURCEAI_ADMIN_EMAIL:-}" ] && [ -n "${SOURCEAI_ADMIN_PASSWORD:-}" ]; then
    python -m scripts.provision_admin || echo "Administrator not created; see the message above. Continuing startup." >&2
fi
unset SOURCEAI_ADMIN_PASSWORD

exec "$@"
