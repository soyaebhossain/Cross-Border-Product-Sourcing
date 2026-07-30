from __future__ import annotations

from typing import Any
from urllib.parse import urlsplit, urlunsplit

import sentry_sdk

from .security import request_id_context


def _strip_query(value: object) -> object:
    if not isinstance(value, str):
        return value
    try:
        parsed = urlsplit(value)
    except ValueError:
        return "<redacted-url>"
    return urlunsplit((parsed.scheme, parsed.netloc, parsed.path, "", ""))


def scrub_error_event(event: dict[str, Any], _hint: dict[str, Any]) -> dict[str, Any]:
    """Remove browser/customer data before an exception leaves the service."""

    request = event.get("request")
    if isinstance(request, dict):
        if "url" in request:
            request["url"] = _strip_query(request["url"])
        for key in ("cookies", "data", "env", "headers", "query_string"):
            request.pop(key, None)
    event.pop("user", None)

    request_id = request_id_context.get()
    if request_id:
        event.setdefault("tags", {})["request_id"] = request_id
    return event


def configure_error_monitoring(settings: Any) -> bool:
    dsn = (getattr(settings, "error_monitoring_dsn", None) or "").strip()
    if not dsn:
        return False

    sample_rate = float(getattr(settings, "error_monitoring_traces_sample_rate", 0.0))
    sentry_sdk.init(
        dsn=dsn,
        environment=getattr(settings, "error_monitoring_environment", None)
        or getattr(settings, "environment", None),
        release=getattr(settings, "release_version", None) or None,
        send_default_pii=False,
        max_request_body_size="never",
        include_local_variables=False,
        include_source_context=False,
        traces_sample_rate=max(0.0, min(1.0, sample_rate)),
        before_send=scrub_error_event,
    )
    return True
