from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from app import auth
from app.db import Base
from app.models import AccountUser, AdminAuditEvent, AuthChallenge, RefreshSession
from scripts import recover_account_access as recovery
from scripts.recover_account_access import (
    _resolve_account,
    build_parser,
    recover_account_access,
)


CURRENT_PASSWORD = "G7!vB2#qL9@xSecure"
NEW_PASSWORD = "V8!nM4@qZ7#cSecure"


@pytest.fixture
def session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine, expire_on_commit=False) as value:
        yield value
    engine.dispose()


def _account_with_auth_state(session: Session, *, role: str = "admin") -> AccountUser:
    now = datetime.now(timezone.utc)
    account = AccountUser(
        username="recovery-target",
        email="recovery@example.test",
        phone="+8801700000000",
        password_hash=auth.make_password(CURRENT_PASSWORD),
        role=role,
        is_active=False,
        is_staff=role == "admin",
        is_superuser=role == "admin",
        failed_login_attempts=4,
        locked_until=now + timedelta(minutes=10),
        last_failed_login_at=now,
        auth_version=7,
        mfa_enabled=True,
        mfa_secret_encrypted="encrypted-mfa-secret",
        mfa_recovery_hashes=["recovery-code-hash"],
        mfa_enrolled_at=now,
    )
    session.add(account)
    session.flush()
    session.add_all(
        (
            RefreshSession(
                id="active-refresh",
                user_id=account.id,
                family_id="refresh-family",
                token_hash="a" * 64,
                remember=True,
                expires_at=now + timedelta(days=1),
            ),
            AuthChallenge(
                id="active-challenge",
                user_id=account.id,
                purpose="login",
                remember=True,
                expires_at=now + timedelta(minutes=5),
            ),
        )
    )
    session.commit()
    return account


def test_recovery_resets_password_and_preserves_account_controls_by_default(
    session: Session,
) -> None:
    account = _account_with_auth_state(session)
    original_lock = account.locked_until
    original_mfa_enrolled_at = account.mfa_enrolled_at

    recovered = recover_account_access(
        session,
        account=account,
        password=NEW_PASSWORD,
    )

    assert not auth.check_password(CURRENT_PASSWORD, recovered.password_hash)
    assert auth.check_password(NEW_PASSWORD, recovered.password_hash)
    assert recovered.auth_version == 8
    assert recovered.is_active is False
    assert recovered.failed_login_attempts == 4
    assert recovered.locked_until == original_lock.replace(tzinfo=None)
    assert recovered.mfa_enabled is True
    assert recovered.mfa_secret_encrypted == "encrypted-mfa-secret"
    assert recovered.mfa_recovery_hashes == ["recovery-code-hash"]
    assert recovered.mfa_enrolled_at == original_mfa_enrolled_at.replace(tzinfo=None)

    refresh = session.get(RefreshSession, "active-refresh")
    challenge = session.get(AuthChallenge, "active-challenge")
    assert refresh is not None and refresh.revoked_at is not None
    assert refresh.revoke_reason == "account_recovery"
    assert challenge is not None and challenge.consumed_at is not None

    audit = session.scalar(
        select(AdminAuditEvent).where(
            AdminAuditEvent.action == "auth.account.access_recovered",
        )
    )
    assert audit is not None
    assert audit.actor_user_id == 0
    assert audit.actor_role == "system"
    assert audit.entity_id == str(account.id)
    assert audit.after_data["sessions_revoked"] == 1
    assert audit.after_data["challenges_consumed"] == 1
    assert audit.after_data["unlock_requested"] is False
    assert audit.after_data["reactivate_requested"] is False
    assert audit.after_data["mfa_clear_requested"] is False
    serialized_audit = json.dumps(
        {
            "before": audit.before_data,
            "after": audit.after_data,
            "note": audit.note,
        }
    )
    for sensitive_value in (
        CURRENT_PASSWORD,
        NEW_PASSWORD,
        account.password_hash,
        account.username,
        account.email,
        account.phone,
        account.mfa_secret_encrypted,
    ):
        assert sensitive_value not in serialized_audit


def test_recovery_applies_explicit_unlock_reactivate_and_mfa_clear(
    session: Session,
) -> None:
    account = _account_with_auth_state(session, role="customer")

    recovered = recover_account_access(
        session,
        account=account,
        password=NEW_PASSWORD,
        unlock=True,
        reactivate=True,
        clear_mfa=True,
    )

    assert recovered.is_active is True
    assert recovered.role == "customer"
    assert recovered.failed_login_attempts == 0
    assert recovered.locked_until is None
    assert recovered.last_failed_login_at is None
    assert recovered.mfa_enabled is False
    assert recovered.mfa_secret_encrypted is None
    assert recovered.mfa_recovery_hashes == []
    assert recovered.mfa_enrolled_at is None
    audit = session.scalar(select(AdminAuditEvent))
    assert audit is not None
    assert audit.after_data["unlock_requested"] is True
    assert audit.after_data["reactivate_requested"] is True
    assert audit.after_data["mfa_clear_requested"] is True


def test_recovery_rejects_the_existing_password_without_mutation(
    session: Session,
) -> None:
    account = _account_with_auth_state(session)

    with pytest.raises(ValueError, match="must differ"):
        recover_account_access(
            session,
            account=account,
            password=CURRENT_PASSWORD,
            unlock=True,
            reactivate=True,
            clear_mfa=True,
        )

    assert account.auth_version == 7
    assert account.is_active is False
    assert account.mfa_enabled is True
    assert session.scalar(select(AdminAuditEvent)) is None
    assert session.get(RefreshSession, "active-refresh").revoked_at is None
    assert session.get(AuthChallenge, "active-challenge").consumed_at is None


def test_recovery_cli_has_no_password_argument() -> None:
    option_strings = {
        option
        for action in build_parser()._actions
        for option in action.option_strings
    }
    assert "--password" not in option_strings


def test_user_id_resolution_requests_a_database_row_lock() -> None:
    account = AccountUser(
        id=42,
        username="locked-selection",
        password_hash="not-used-by-this-test",
        role="customer",
    )
    session = Mock()
    session.scalar.return_value = account

    resolved = _resolve_account(
        session,
        identifier=None,
        user_id=42,
    )

    assert resolved is account
    statement = session.scalar.call_args.args[0]
    assert statement._for_update_arg is not None


def test_cli_sanitizes_generic_database_errors(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    sensitive_parameter = "sensitive-password-hash"

    class SessionContext:
        def __enter__(self):
            return Mock()

        def __exit__(self, exc_type, exc, traceback):
            return False

    def raise_database_error(*args, **kwargs):
        raise OperationalError(
            "UPDATE accounts_users SET password_hash=:password_hash",
            {"password_hash": sensitive_parameter},
            RuntimeError("database unavailable"),
        )

    monkeypatch.setattr(
        recovery,
        "inspect",
        lambda engine: SimpleNamespace(has_table=lambda table: True),
    )
    monkeypatch.setattr(recovery, "_read_password", lambda: NEW_PASSWORD)
    monkeypatch.setattr(recovery, "Session", lambda *args, **kwargs: SessionContext())
    monkeypatch.setattr(recovery, "_resolve_account", raise_database_error)

    assert recovery.main(["--user-id", "42"]) == 1
    error_output = capsys.readouterr().err
    assert error_output == "Account was not changed because the database operation failed.\n"
    assert sensitive_parameter not in error_output
    assert "password_hash" not in error_output
