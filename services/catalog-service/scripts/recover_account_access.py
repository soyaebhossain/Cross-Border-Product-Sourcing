from __future__ import annotations

import argparse
import getpass
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import inspect, select, update
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session


SERVICE_ROOT = Path(__file__).resolve().parents[1]
if str(SERVICE_ROOT) not in sys.path:
    sys.path.insert(0, str(SERVICE_ROOT))

from app.auth import (  # noqa: E402
    AmbiguousLoginIdentifierError,
    check_password,
    find_unique_user_by_identifier,
    make_password,
    validate_password_strength,
)
from app.db import engine  # noqa: E402
from app.models import AccountUser, AdminAuditEvent, AuthChallenge, RefreshSession  # noqa: E402


RECOVERY_REASON = "account_recovery"


def _now() -> datetime:
    return datetime.now(timezone.utc)


def recover_account_access(
    session: Session,
    *,
    account: AccountUser,
    password: str,
    unlock: bool = False,
    reactivate: bool = False,
    clear_mfa: bool = False,
) -> AccountUser:
    """Reset one account credential and invalidate all outstanding authentication state."""

    validate_password_strength(password, (account.username, account.email, account.phone))
    if check_password(password, account.password_hash):
        raise ValueError("New password must differ from the current password")

    now = _now()
    before_data = {
        "active": bool(account.is_active),
        "locked": account.locked_until is not None,
        "mfa_enabled": bool(account.mfa_enabled),
        "auth_version": int(account.auth_version),
    }

    account.password_hash = make_password(password)
    account.auth_version += 1
    if unlock:
        account.failed_login_attempts = 0
        account.locked_until = None
        account.last_failed_login_at = None
    if reactivate:
        account.is_active = True
    if clear_mfa:
        account.mfa_enabled = False
        account.mfa_secret_encrypted = None
        account.mfa_recovery_hashes = []
        account.mfa_enrolled_at = None

    revoked_sessions = session.execute(
        update(RefreshSession)
        .where(RefreshSession.user_id == account.id, RefreshSession.revoked_at.is_(None))
        .values(revoked_at=now, revoke_reason=RECOVERY_REASON)
    ).rowcount
    consumed_challenges = session.execute(
        update(AuthChallenge)
        .where(AuthChallenge.user_id == account.id, AuthChallenge.consumed_at.is_(None))
        .values(consumed_at=now)
    ).rowcount

    session.add(
        AdminAuditEvent(
            actor_user_id=0,
            actor_role="system",
            action="auth.account.access_recovered",
            entity_type="account",
            entity_id=str(account.id),
            before_data=before_data,
            after_data={
                "active": bool(account.is_active),
                "locked": account.locked_until is not None,
                "mfa_enabled": bool(account.mfa_enabled),
                "auth_version": int(account.auth_version),
                "sessions_revoked": int(revoked_sessions or 0),
                "challenges_consumed": int(consumed_challenges or 0),
                "unlock_requested": unlock,
                "reactivate_requested": reactivate,
                "mfa_clear_requested": clear_mfa,
            },
            note="Out-of-band account recovery; authentication state invalidated.",
        )
    )
    session.commit()
    session.refresh(account)
    return account


def _read_password() -> str:
    environment_password = os.environ.pop("SOURCEAI_ACCOUNT_PASSWORD", None)
    if environment_password is not None:
        return environment_password
    first = getpass.getpass("New account password: ")
    confirmation = getpass.getpass("Confirm account password: ")
    if first != confirmation:
        raise ValueError("Passwords did not match")
    return first


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Securely reset account access without accepting a password argument.",
    )
    selector = parser.add_mutually_exclusive_group()
    selector.add_argument("--identifier", help="Username, email, or phone; otherwise prompt.")
    selector.add_argument("--user-id", type=int, help="Numeric account ID (recommended for an ambiguous identifier).")
    parser.add_argument(
        "--unlock",
        action="store_true",
        help="Also clear login failure counters and the temporary lock.",
    )
    parser.add_argument(
        "--reactivate",
        action="store_true",
        help="Also reactivate a disabled account.",
    )
    parser.add_argument(
        "--clear-mfa",
        action="store_true",
        help="Also erase MFA enrollment and recovery codes; MFA is preserved by default.",
    )
    return parser


def _resolve_account(
    session: Session,
    *,
    identifier: str | None,
    user_id: int | None,
) -> AccountUser | None:
    if user_id is not None:
        return session.scalar(
            select(AccountUser)
            .where(AccountUser.id == user_id)
            .with_for_update()
        )
    if identifier is None:
        return None
    return find_unique_user_by_identifier(session, identifier, for_update=True)


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    identifier = args.identifier
    if args.user_id is None and identifier is None:
        identifier = input("Account username, email, or phone: ").strip()
    if args.user_id is None and not identifier:
        parser.error("An account identifier or --user-id is required")

    password = ""
    try:
        if not inspect(engine).has_table("accounts_users"):
            parser.error("Database schema is missing. Run `alembic upgrade head` first.")
        password = _read_password()
        with Session(engine, expire_on_commit=False) as session:
            account = _resolve_account(
                session,
                identifier=identifier,
                user_id=args.user_id,
            )
            if account is None:
                raise ValueError("No matching account was found; no account was changed")
            account = recover_account_access(
                session,
                account=account,
                password=password,
                unlock=args.unlock,
                reactivate=args.reactivate,
                clear_mfa=args.clear_mfa,
            )
    except AmbiguousLoginIdentifierError:
        print(
            "Account was not changed: identifier is ambiguous; retry with --user-id.",
            file=sys.stderr,
        )
        return 1
    except SQLAlchemyError:
        print(
            "Account was not changed because the database operation failed.",
            file=sys.stderr,
        )
        return 1
    except ValueError as exc:
        print(f"Account was not changed: {exc}", file=sys.stderr)
        return 1
    finally:
        password = ""

    state = "active" if account.is_active else "disabled"
    lock_state = "locked" if account.locked_until is not None else "unlocked"
    mfa_state = "enabled" if account.mfa_enabled else "not enrolled"
    print(
        f"Account {account.id} ({account.role}) recovered; "
        f"state={state}, lock={lock_state}, MFA={mfa_state}.",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
