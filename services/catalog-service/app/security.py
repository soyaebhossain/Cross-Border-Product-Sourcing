from __future__ import annotations

import contextvars
import hashlib
import json
import logging
import math
import re
import secrets
import threading
import time
from collections import defaultdict, deque
from collections.abc import Callable
from datetime import UTC, datetime
from urllib.parse import urlsplit

from fastapi import HTTPException, Request, status
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import JSONResponse, Response

from .config import Settings


SAFE_METHODS = {"GET", "HEAD", "OPTIONS", "TRACE"}
AUTH_COOKIE_NAMES = {"sourceai_access", "sourceai_refresh"}
PRIVATE_CACHE_PATHS = (
    "/api/auth/",
    "/api/admin/",
    "/api/account/",
    "/api/ready",
    "/api/research/",
    "/api/orders/",
    "/api/quote/saved/",
    "/api/quote/save/",
)
REQUEST_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,63}$")
REQUEST_LOG_LEVELS = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
request_id_context: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "request_id",
    default=None,
)
request_logger = logging.getLogger("catalog.request")


def configure_request_logging(level: str = "INFO") -> None:
    """Emit one JSON object per line without relying on Uvicorn's access log."""

    normalized_level = level.strip().upper()
    if normalized_level not in REQUEST_LOG_LEVELS:
        normalized_level = "INFO"
    request_logger.setLevel(normalized_level)
    request_logger.propagate = False

    if any(getattr(handler, "_catalog_json_handler", False) for handler in request_logger.handlers):
        return
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("%(message)s"))
    handler._catalog_json_handler = True  # type: ignore[attr-defined]
    request_logger.addHandler(handler)


def validate_payment_proof_host(value: str | None, settings: Settings) -> None:
    if not value:
        return
    allowed_hosts = {
        item.strip().casefold().rstrip(".")
        for item in settings.payment_proof_allowed_hosts.split(",")
        if item.strip()
    }
    if not allowed_hosts:
        return
    hostname = (urlsplit(value).hostname or "").casefold().rstrip(".")
    if hostname not in allowed_hosts:
        raise HTTPException(
            status_code=422,
            detail="Payment proof URL host is not approved",
        )


def _request_id(request: Request) -> str:
    candidate = (
        request.headers.get("x-request-id")
        or request.headers.get("x-correlation-id")
        or ""
    ).strip()
    if REQUEST_ID_PATTERN.fullmatch(candidate):
        return candidate
    return secrets.token_hex(16)


def _route_template(request: Request) -> str:
    route = request.scope.get("route")
    template = getattr(route, "path", None)
    if isinstance(template, str) and template.startswith("/"):
        return template
    # Never log an unmatched raw path: it may contain a reset token or other secret.
    return "<unmatched>"


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Correlated JSON request logs with sensitive request data excluded."""

    def __init__(self, app, *, logger: logging.Logger | None = None) -> None:
        super().__init__(app)
        self.logger = logger or request_logger

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        request_id = _request_id(request)
        request.state.request_id = request_id
        context_token = request_id_context.set(request_id)
        started_at = time.perf_counter()
        response_status = status.HTTP_500_INTERNAL_SERVER_ERROR
        exception_type: str | None = None

        try:
            response = await call_next(request)
            response_status = response.status_code
            response.headers["X-Request-ID"] = request_id
            return response
        except Exception as exc:
            exception_type = type(exc).__name__
            raise
        finally:
            log_level = logging.INFO
            if response_status >= 500:
                log_level = logging.ERROR
            elif response_status >= 400:
                log_level = logging.WARNING
            event: dict[str, str | int | float] = {
                "timestamp": datetime.now(UTC).isoformat(timespec="milliseconds"),
                "event": "http_request",
                "level": logging.getLevelName(log_level).lower(),
                "service": "catalog-service",
                "request_id": request_id,
                "method": request.method.upper(),
                "route": _route_template(request),
                "status_code": response_status,
                "duration_ms": round((time.perf_counter() - started_at) * 1000, 3),
            }
            if exception_type is not None:
                # Log only the exception class. Messages can contain SQL or user data.
                event["exception_type"] = exception_type
            self.logger.log(log_level, json.dumps(event, separators=(",", ":"), sort_keys=True))
            request_id_context.reset(context_token)


def normalize_origin(value: str | None) -> str | None:
    if not value:
        return None
    try:
        parsed = urlsplit(value.strip())
        port = parsed.port
    except ValueError:
        return None
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        return None
    if parsed.username or parsed.password or parsed.path not in {"", "/"} or parsed.query or parsed.fragment:
        return None

    host = parsed.hostname.lower()
    if ":" in host:
        host = f"[{host}]"
    default_port = 80 if parsed.scheme == "http" else 443
    port_suffix = f":{port}" if port is not None and port != default_port else ""
    return f"{parsed.scheme.lower()}://{host}{port_suffix}"


def request_origin_from_referer(request: Request) -> str | None:
    value = request.headers.get("referer")
    if not value:
        return None
    try:
        parsed = urlsplit(value.strip())
        port = parsed.port
    except ValueError:
        return None
    if parsed.scheme not in {"http", "https"} or not parsed.hostname or parsed.username or parsed.password:
        return None
    host = parsed.hostname.lower()
    if ":" in host:
        host = f"[{host}]"
    default_port = 80 if parsed.scheme == "http" else 443
    port_suffix = f":{port}" if port is not None and port != default_port else ""
    return f"{parsed.scheme.lower()}://{host}{port_suffix}"


class SlidingWindowRateLimiter:
    """Small in-process guard. A shared limiter should replace it for multi-replica deployments."""

    def __init__(
        self,
        *,
        clock: Callable[[], float] = time.monotonic,
        max_buckets: int = 10_000,
    ) -> None:
        self._clock = clock
        self._max_buckets = max_buckets
        self._buckets: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def clear(self) -> None:
        with self._lock:
            self._buckets.clear()

    def enforce(self, key: str, *, limit: int, window_seconds: int) -> None:
        if limit <= 0 or window_seconds <= 0:
            return
        now = self._clock()
        cutoff = now - window_seconds
        with self._lock:
            bucket = self._buckets[key]
            while bucket and bucket[0] <= cutoff:
                bucket.popleft()
            if len(bucket) >= limit:
                retry_after = max(1, math.ceil(window_seconds - (now - bucket[0])))
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail="Too many requests. Please try again later.",
                    headers={"Retry-After": str(retry_after)},
                )
            bucket.append(now)
            if len(self._buckets) > self._max_buckets:
                self._prune(cutoff)

    def _prune(self, cutoff: float) -> None:
        expired_keys = [
            key
            for key, bucket in self._buckets.items()
            if not bucket or bucket[-1] <= cutoff
        ]
        for key in expired_keys:
            self._buckets.pop(key, None)
        while len(self._buckets) > self._max_buckets:
            self._buckets.pop(next(iter(self._buckets)))


auth_rate_limiter = SlidingWindowRateLimiter()


def client_rate_key(request: Request, scope: str, discriminator: str | None = None) -> str:
    client_host = request.client.host if request.client else "unknown"
    key = f"{scope}:{client_host}"
    if discriminator:
        digest = hashlib.sha256(discriminator.strip().lower().encode()).hexdigest()[:24]
        key = f"{key}:{digest}"
    return key


class BrowserSecurityMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, *, settings: Settings) -> None:
        super().__init__(app)
        self.settings = settings
        self.allowed_origins = {
            normalized
            for value in settings.allowed_browser_origins
            if (normalized := normalize_origin(value))
        }

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        rejection = self._origin_rejection(request)
        if rejection is not None:
            return self._apply_headers(request, rejection)

        response = await call_next(request)
        return self._apply_headers(request, response)

    def _origin_rejection(self, request: Request) -> JSONResponse | None:
        if request.method.upper() in SAFE_METHODS:
            return None

        origin_header = request.headers.get("origin")
        if origin_header:
            origin = normalize_origin(origin_header)
            if origin is None or origin not in self.allowed_origins:
                return JSONResponse(
                    {"detail": "Request origin is not allowed"},
                    status_code=status.HTTP_403_FORBIDDEN,
                )
            return None

        has_auth_cookie = any(name in request.cookies for name in AUTH_COOKIE_NAMES)
        if not has_auth_cookie:
            return None

        referer_origin = request_origin_from_referer(request)
        if referer_origin is None or referer_origin not in self.allowed_origins:
            return JSONResponse(
                {"detail": "Origin verification is required"},
                status_code=status.HTTP_403_FORBIDDEN,
            )
        return None

    def _apply_headers(self, request: Request, response: Response) -> Response:
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "no-referrer")
        response.headers.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=(), payment=()")
        response.headers.setdefault("Cross-Origin-Opener-Policy", "same-origin")
        response.headers.setdefault("Content-Security-Policy", "default-src 'none'; frame-ancestors 'none'; base-uri 'none'")
        if request.url.path.startswith(PRIVATE_CACHE_PATHS):
            response.headers.setdefault("Cache-Control", "no-store")
        if self.settings.is_production or request.url.scheme == "https":
            response.headers.setdefault("Strict-Transport-Security", "max-age=31536000; includeSubDomains")
        return response
