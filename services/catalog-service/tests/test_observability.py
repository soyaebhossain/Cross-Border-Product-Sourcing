from __future__ import annotations

from app.observability import configure_error_monitoring, scrub_error_event


class SettingsWithoutMonitoring:
    error_monitoring_dsn = None


def test_monitoring_stays_disabled_without_dsn() -> None:
    assert configure_error_monitoring(SettingsWithoutMonitoring()) is False


def test_error_event_scrubber_removes_request_and_user_data() -> None:
    event = scrub_error_event(
        {
            "request": {
                "url": "https://example.com/api/orders/1?token=secret",
                "headers": {"authorization": "secret"},
                "cookies": {"session": "secret"},
                "data": {"password": "secret"},
                "query_string": "token=secret",
            },
            "user": {"email": "private@example.com"},
        },
        {},
    )

    assert event["request"] == {"url": "https://example.com/api/orders/1"}
    assert "user" not in event
