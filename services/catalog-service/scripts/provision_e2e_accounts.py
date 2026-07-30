from __future__ import annotations

"""Provision isolated role-routing accounts for CI only.

The command refuses to run unless CATALOG_ENVIRONMENT is exactly ``test``.
Passwords are required through environment variables and are never printed.
"""

import os
import sys
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session


SERVICE_ROOT = Path(__file__).resolve().parents[1]
if str(SERVICE_ROOT) not in sys.path:
    sys.path.insert(0, str(SERVICE_ROOT))

from app.auth import make_password, validate_password_strength  # noqa: E402
from app.config import get_settings  # noqa: E402
from app.db import engine  # noqa: E402
from app.models import AccountUser  # noqa: E402


def _upsert_test_account(
    session: Session,
    *,
    username: str,
    email: str,
    password: str,
    role: str,
) -> AccountUser:
    validate_password_strength(password, (username, email))
    account = session.scalar(select(AccountUser).where(AccountUser.username == username))
    if account is None:
        account = AccountUser(
            username=username,
            email=email,
            phone=None,
            password_hash=make_password(password),
            role=role,
            is_active=True,
            is_staff=role == "admin",
            is_superuser=role == "admin",
        )
        session.add(account)
    else:
        account.email = email
        account.password_hash = make_password(password)
        account.role = role
        account.is_active = True
        account.is_staff = role == "admin"
        account.is_superuser = role == "admin"
        account.failed_login_attempts = 0
        account.locked_until = None
        account.auth_version += 1
    account.mfa_enabled = False
    account.mfa_secret_encrypted = None
    account.mfa_recovery_hashes = []
    session.flush()
    return account


def main() -> int:
    settings = get_settings()
    if settings.environment.strip().lower() != "test":
        print("Refusing to provision E2E accounts outside CATALOG_ENVIRONMENT=test", file=sys.stderr)
        return 1
    if settings.privileged_mfa_required:
        print(
            "Set CATALOG_PRIVILEGED_MFA_REQUIRED=false for the role-routing CI fixture",
            file=sys.stderr,
        )
        return 1

    customer_password = os.getenv("E2E_CUSTOMER_PASSWORD") or ""
    admin_password = os.getenv("E2E_ADMIN_PASSWORD") or ""
    if not customer_password or not admin_password:
        print(
            "E2E_CUSTOMER_PASSWORD and E2E_ADMIN_PASSWORD are required",
            file=sys.stderr,
        )
        return 1

    customer_identifier = os.getenv("E2E_CUSTOMER_IDENTIFIER") or "e2e-customer"
    admin_identifier = os.getenv("E2E_ADMIN_IDENTIFIER") or "e2e-admin"
    try:
        with Session(engine) as session:
            customer = _upsert_test_account(
                session,
                username=customer_identifier,
                email="customer@e2e.invalid",
                password=customer_password,
                role="customer",
            )
            admin = _upsert_test_account(
                session,
                username=admin_identifier,
                email="admin@e2e.invalid",
                password=admin_password,
                role="admin",
            )
            session.commit()
            customer_id = customer.id
            admin_id = admin.id
    except ValueError as exc:
        print(f"E2E account provisioning failed: {exc}", file=sys.stderr)
        return 1
    finally:
        customer_password = ""
        admin_password = ""

    print(f"Provisioned isolated E2E users customer={customer_id}, admin={admin_id}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
