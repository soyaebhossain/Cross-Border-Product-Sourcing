from __future__ import annotations

import argparse
import getpass
import os
import sys
from pathlib import Path

from sqlalchemy import inspect
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session


SERVICE_ROOT = Path(__file__).resolve().parents[1]
if str(SERVICE_ROOT) not in sys.path:
    sys.path.insert(0, str(SERVICE_ROOT))

from app.auth import login_identifier_exists, make_password, validate_password_strength  # noqa: E402
from app.db import engine  # noqa: E402
from app.identity import normalize_email_address, normalize_identifier_key, normalize_username  # noqa: E402
from app.models import AccountUser, AdminAuditEvent  # noqa: E402


def provision_admin(
    session: Session,
    *,
    username: str,
    email: str,
    password: str,
) -> AccountUser:
    normalized_username = normalize_username(username)
    normalized_email = normalize_email_address(email)
    if not 3 <= len(normalized_username) <= 150:
        raise ValueError("Username must be between 3 and 150 characters")
    if "@" not in normalized_email or len(normalized_email) > 254:
        raise ValueError("A valid admin email is required")
    if login_identifier_exists(session, normalized_username, normalized_email):
        raise ValueError("The username or email is already provisioned; no account was changed")
    validate_password_strength(password, (normalized_username, normalized_email))
    admin = AccountUser(
        username=normalized_username,
        username_normalized=normalize_identifier_key(normalized_username),
        email=normalized_email,
        email_normalized=normalize_identifier_key(normalized_email),
        phone=None,
        phone_normalized=None,
        password_hash=make_password(password),
        role="admin",
        is_active=True,
        is_staff=True,
        is_superuser=True,
    )
    session.add(admin)
    session.flush()
    session.add(
        AdminAuditEvent(
            actor_user_id=admin.id,
            actor_role="admin",
            action="auth.admin.provisioned",
            entity_type="account",
            entity_id=str(admin.id),
            note="Secure out-of-band CLI provisioning; MFA enrollment required at first login.",
        )
    )
    session.commit()
    return admin


def _read_password() -> str:
    environment_password = os.environ.pop("SOURCEAI_ADMIN_PASSWORD", None)
    if environment_password is not None:
        return environment_password
    first = getpass.getpass("New admin password: ")
    confirmation = getpass.getpass("Confirm admin password: ")
    if first != confirmation:
        raise ValueError("Passwords did not match")
    return first


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Provision a new admin without any built-in/default credential.",
    )
    parser.add_argument(
        "--username",
        default=os.getenv("SOURCEAI_ADMIN_USERNAME"),
        help="Admin username (or SOURCEAI_ADMIN_USERNAME; otherwise prompt).",
    )
    parser.add_argument(
        "--email",
        default=os.getenv("SOURCEAI_ADMIN_EMAIL"),
        help="Admin email (or SOURCEAI_ADMIN_EMAIL; otherwise prompt).",
    )
    args = parser.parse_args()
    username = args.username or input("New admin username: ").strip()
    email = args.email or input("New admin email: ").strip()
    if not username or not email:
        parser.error("Admin username and email are required")
    if not inspect(engine).has_table("accounts_users"):
        parser.error("Database schema is missing. Run `alembic upgrade head` first.")
    try:
        password = _read_password()
        with Session(engine, expire_on_commit=False) as session:
            admin = provision_admin(
                session,
                username=username,
                email=email,
                password=password,
            )
    except (IntegrityError, ValueError) as exc:
        print(f"Admin was not provisioned: {exc}", file=sys.stderr)
        return 1
    finally:
        password = ""
    print(f"Admin user {admin.id} provisioned. MFA enrollment is required at first admin login.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
