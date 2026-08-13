from __future__ import annotations

from types import SimpleNamespace

import pytest
import resend
from resend.exceptions import ResendError

from app.config import Settings
from app.services.notifications import (
    DeliveryError,
    ResendEmailAdapter,
    SMTPEmailAdapter,
    email_adapter_for,
)


def _settings(**overrides) -> Settings:
    values = {
        "environment": "development",
        "database_url": "sqlite:///:memory:",
        "resend_api_key": "re_test_only_not_a_secret",
        "resend_from_email": "security@example.test",
        "notification_sender_name": "SourceAI",
    }
    values.update(overrides)
    return Settings(**values)


def _message(*, body: str = "Your order is ready.", action_url: str = "") -> SimpleNamespace:
    return SimpleNamespace(
        id=42,
        destination="buyer@example.test",
        payload={"title": "SourceAI update", "body": body, "action_url": action_url},
    )


def test_resend_adapter_sends_text_and_escaped_html_with_idempotency(monkeypatch) -> None:
    captured: dict[str, object] = {}

    def fake_send(params, options=None):
        captured.update({"params": params, "options": options, "api_key": resend.api_key})
        return {"id": "email_provider_42"}

    monkeypatch.setattr(resend.Emails, "send", fake_send)
    adapter = ResendEmailAdapter(_settings())
    receipt = adapter.send(
        _message(
            body="Hello <script>alert('x')</script>",
            action_url="https://app.example.test/reset#safe-test-token",
        )
    )

    assert receipt.provider_message_id == "email_provider_42"
    params = captured["params"]
    assert params["from"] == "SourceAI <security@example.test>"
    assert params["to"] == ["buyer@example.test"]
    assert params["subject"] == "SourceAI update"
    assert params["text"] == "Hello <script>alert('x')</script>"
    assert "<script>" not in params["html"]
    assert "&lt;script&gt;" in params["html"]
    assert 'href="https://app.example.test/reset#safe-test-token"' in params["html"]
    assert captured["options"] == {"idempotency_key": "sourceai-outbox-42"}
    assert captured["api_key"] == "re_test_only_not_a_secret"
    assert "re_test_only_not_a_secret" not in str(params)


def test_resend_adapter_maps_provider_failures_to_secret_free_error(monkeypatch) -> None:
    leaked_key = "re_test_key_that_must_not_escape"
    leaked_destination = "private-recipient@example.test"
    leaked_token = "password-reset-token-that-must-not-escape"

    def reject_send(_params, _options=None):
        raise ResendError(
            401,
            "validation_error",
            f"rejected {leaked_key} {leaked_destination} {leaked_token}",
            "rotate credentials",
        )

    monkeypatch.setattr(resend.Emails, "send", reject_send)
    adapter = ResendEmailAdapter(
        _settings(resend_api_key=leaked_key, resend_from_email="security@example.test")
    )

    with pytest.raises(DeliveryError) as raised:
        adapter.send(_message(body=f"https://app.example/reset#{leaked_token}"))

    assert raised.value.code == "provider_delivery_failed"
    assert raised.value.safe_detail == "Email provider rejected the delivery"
    serialized = f"{raised.value} {vars(raised.value)}"
    assert leaked_key not in serialized
    assert leaked_destination not in serialized
    assert leaked_token not in serialized


def test_resend_is_preferred_and_smtp_remains_configuration_fallback(monkeypatch) -> None:
    both = _settings(
        smtp_host="smtp.example.test",
        smtp_from_email="fallback@example.test",
    )
    assert isinstance(email_adapter_for(both), ResendEmailAdapter)

    smtp_only = _settings(
        resend_api_key=None,
        resend_from_email=None,
        smtp_host="smtp.example.test",
        smtp_from_email="fallback@example.test",
    )
    assert isinstance(email_adapter_for(smtp_only), SMTPEmailAdapter)

    smtp_called = False

    def smtp_send(_self, _message):
        nonlocal smtp_called
        smtp_called = True
        raise AssertionError("Resend failures must not fall through to SMTP and duplicate mail")

    monkeypatch.setattr(SMTPEmailAdapter, "send", smtp_send)
    monkeypatch.setattr(
        resend.Emails,
        "send",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            ResendError(500, "internal_server_error", "ambiguous failure", "retry")
        ),
    )
    with pytest.raises(DeliveryError):
        email_adapter_for(both).send(_message())
    assert smtp_called is False


def test_resend_requires_provider_message_id(monkeypatch) -> None:
    monkeypatch.setattr(resend.Emails, "send", lambda *_args, **_kwargs: {})
    with pytest.raises(DeliveryError, match="Email provider rejected the delivery") as raised:
        ResendEmailAdapter(_settings()).send(_message())
    assert raised.value.code == "provider_delivery_failed"
