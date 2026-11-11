"""Price provenance, freshness policy and live exchange-rate refresh.

Every quote reports, for each price input (supplier offer, FX rate, freight,
customs duty), where the value came from and when it was last verified. An
input older than its maximum age makes the whole quote "indicative" instead of
"verified". FX rates can be refreshed from a live provider; the other inputs
are refreshed by administrators or supplier/carrier feeds and are stamped with
their source when they change.
"""

from __future__ import annotations

import json
import logging
import threading
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from typing import Any, Callable
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import Settings
from ..models import CurrencyRate

logger = logging.getLogger(__name__)

FX_PROVIDER_NAME = "ExchangeRate-API"
FX_PROVIDER_URL = "https://www.exchangerate-api.com"
RATE_PRECISION = Decimal("0.00000001")

PRICE_SOURCES = ("seeded", "csv_import", "admin", "supplier_quote", "api")


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def as_aware_utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


@dataclass(frozen=True)
class FreshnessPolicy:
    fx_max_age: timedelta
    offer_max_age: timedelta
    freight_max_age: timedelta
    duty_max_age: timedelta

    @classmethod
    def from_settings(cls, settings: Settings) -> "FreshnessPolicy":
        return cls(
            fx_max_age=timedelta(hours=settings.pricing_fx_max_age_hours),
            offer_max_age=timedelta(days=settings.pricing_offer_max_age_days),
            freight_max_age=timedelta(days=settings.pricing_freight_max_age_days),
            duty_max_age=timedelta(days=settings.pricing_duty_max_age_days),
        )

    def as_dict(self) -> dict[str, int]:
        return {
            "fx_max_age_hours": int(self.fx_max_age.total_seconds() // 3600),
            "offer_max_age_hours": int(self.offer_max_age.total_seconds() // 3600),
            "freight_max_age_hours": int(self.freight_max_age.total_seconds() // 3600),
            "duty_max_age_hours": int(self.duty_max_age.total_seconds() // 3600),
        }


def price_component(
    component: str,
    row: Any,
    *,
    max_age: timedelta,
    now: datetime,
    reference: str | None = None,
    valid_until: datetime | None = None,
    details: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Describe one price input and decide whether it is still fresh."""

    verified_at = as_aware_utc(getattr(row, "verified_at", None))
    expiry = as_aware_utc(valid_until or getattr(row, "valid_until", None))
    stale_reasons: list[str] = []
    if verified_at is None:
        stale_reasons.append("unverified")
    elif now - verified_at > max_age:
        stale_reasons.append("older_than_policy")
    if expiry is not None and expiry <= now:
        stale_reasons.append("validity_ended")
    return {
        "component": component,
        "source": getattr(row, "price_source", None) or "seeded",
        "reference": reference if reference is not None else getattr(row, "source_reference", None),
        "verified_at": verified_at.isoformat() if verified_at else None,
        "valid_until": expiry.isoformat() if expiry else None,
        "max_age_hours": int(max_age.total_seconds() // 3600),
        "age_hours": int((now - verified_at).total_seconds() // 3600) if verified_at else None,
        "fresh": not stale_reasons,
        "stale_reasons": stale_reasons,
        **(details or {}),
    }


def pricing_summary(
    components: list[dict[str, Any]],
    *,
    now: datetime,
    policy: FreshnessPolicy,
) -> dict[str, Any]:
    stale = [item["component"] for item in components if not item["fresh"]]
    return {
        "status": "indicative" if stale else "verified",
        "calculated_at": now.isoformat(),
        "components": components,
        "stale_components": stale,
        "policy": policy.as_dict(),
    }


@dataclass
class FxRefreshResult:
    provider: str = FX_PROVIDER_NAME
    provider_updated_at: str | None = None
    updated: list[dict[str, Any]] = field(default_factory=list)
    rejected: list[dict[str, Any]] = field(default_factory=list)
    missing: list[str] = field(default_factory=list)
    error: str | None = None

    @property
    def ok(self) -> bool:
        return self.error is None

    def as_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "provider": self.provider,
            "provider_url": FX_PROVIDER_URL,
            "provider_updated_at": self.provider_updated_at,
            "updated": self.updated,
            "rejected": self.rejected,
            "missing": self.missing,
            "error": self.error,
        }


def fetch_usd_rates(url: str, timeout_seconds: float = 15.0) -> tuple[dict[str, Decimal], datetime | None]:
    """Return units of each currency per 1 USD from an ExchangeRate-API style feed."""

    request = Request(
        url,
        headers={"Accept": "application/json", "User-Agent": "SourceAI-Pricing/1.0"},
        method="GET",
    )
    with urlopen(request, timeout=timeout_seconds) as response:  # noqa: S310 - URL is operator configured
        if not 200 <= int(response.status) < 300:
            raise ValueError(f"FX provider returned HTTP {response.status}")
        body = json.loads(response.read(1_000_000).decode("utf-8"))
    if not isinstance(body, dict) or body.get("result") != "success":
        raise ValueError("FX provider did not report success")
    if str(body.get("base_code", "USD")).upper() != "USD":
        raise ValueError("FX provider base currency must be USD")
    raw_rates = body.get("rates")
    if not isinstance(raw_rates, dict):
        raise ValueError("FX provider response has no rates")
    rates: dict[str, Decimal] = {}
    for code, value in raw_rates.items():
        try:
            rate = Decimal(str(value))
        except (InvalidOperation, ValueError):
            continue
        if rate > 0:
            rates[str(code).upper()] = rate
    updated_unix = body.get("time_last_update_unix")
    provider_updated_at = (
        datetime.fromtimestamp(int(updated_unix), tz=timezone.utc) if isinstance(updated_unix, (int, float)) else None
    )
    return rates, provider_updated_at


def refresh_currency_rates(
    session: Session,
    settings: Settings,
    *,
    fetch: Callable[[str], tuple[dict[str, Decimal], datetime | None]] | None = None,
    now: datetime | None = None,
) -> FxRefreshResult:
    """Update every active currency's BDT rate from the live provider.

    A rate that moves more than fx_max_change_percent against a recent live
    rate is rejected and left for an administrator to confirm, so a bad feed
    value can never silently reprice every quote.
    """

    now = now or utc_now()
    result = FxRefreshResult()
    fetcher = fetch or fetch_usd_rates
    try:
        rates, provider_updated_at = fetcher(settings.fx_rates_url)
    except (HTTPError, URLError, OSError, TimeoutError, ValueError, json.JSONDecodeError, UnicodeDecodeError) as error:
        result.error = f"FX provider unavailable: {error.__class__.__name__}"
        logger.warning("FX refresh failed: %s", error)
        return result
    result.provider_updated_at = provider_updated_at.isoformat() if provider_updated_at else None
    bdt_per_usd = rates.get("BDT")
    if not bdt_per_usd:
        result.error = "FX provider response has no BDT rate"
        return result

    reference = f"{FX_PROVIDER_NAME} ({urlsplit(settings.fx_rates_url).netloc})"
    recent_live_cutoff = now - timedelta(days=7)
    for row in session.scalars(select(CurrencyRate).where(CurrencyRate.is_active.is_(True))).all():
        code = row.currency.strip().upper()
        if code == "BDT":
            continue
        units_per_usd = rates.get(code)
        if not units_per_usd:
            result.missing.append(code)
            continue
        new_rate = (bdt_per_usd / units_per_usd).quantize(RATE_PRECISION)
        old_rate = Decimal(row.rate_to_bdt)
        change_percent = (abs(new_rate - old_rate) / old_rate * 100) if old_rate > 0 else Decimal("0")
        previous_verified = as_aware_utc(row.verified_at)
        has_recent_live_baseline = (
            row.price_source == "api" and previous_verified is not None and previous_verified >= recent_live_cutoff
        )
        entry = {
            "currency": code,
            "previous_rate_to_bdt": format(old_rate, "f"),
            "rate_to_bdt": format(new_rate, "f"),
            "change_percent": format(change_percent.quantize(Decimal("0.01")), "f"),
        }
        if has_recent_live_baseline and change_percent > Decimal(str(settings.fx_max_change_percent)):
            result.rejected.append(entry)
            logger.warning(
                "FX refresh rejected %s: %s%% move exceeds the %s%% guard",
                code,
                entry["change_percent"],
                settings.fx_max_change_percent,
            )
            continue
        row.rate_to_bdt = new_rate
        row.price_source = "api"
        row.source_reference = reference
        row.verified_at = now
        row.valid_until = None
        row.updated_at = now
        result.updated.append(entry)
    session.commit()
    logger.info(
        "FX refresh: %d updated, %d rejected, %d missing", len(result.updated), len(result.rejected), len(result.missing)
    )
    return result


def fx_refresh_due(session: Session, interval: timedelta, now: datetime | None = None) -> bool:
    """True when any active foreign currency has not been refreshed within the interval."""

    now = now or utc_now()
    for row in session.scalars(select(CurrencyRate).where(CurrencyRate.is_active.is_(True))).all():
        if row.currency.strip().upper() == "BDT":
            continue
        verified_at = as_aware_utc(row.verified_at)
        if row.price_source != "api" or verified_at is None or now - verified_at >= interval:
            return True
    return False


class FxRefreshScheduler:
    """Background thread that keeps FX rates fresh inside the API process.

    The free hosting plan has no separate worker, so the API refreshes rates
    itself. Refreshing is idempotent, so several API instances are harmless.
    """

    def __init__(self, settings: Settings, session_factory: Callable[[], Session]) -> None:
        self._settings = settings
        self._session_factory = session_factory
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    @property
    def interval(self) -> timedelta:
        return timedelta(hours=max(self._settings.fx_refresh_interval_hours, 0.25))

    def start(self) -> None:
        if self._thread is not None:
            return
        self._thread = threading.Thread(target=self._run, name="fx-refresh", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=5)

    def run_once(self) -> FxRefreshResult | None:
        with self._session_factory() as session:
            if not fx_refresh_due(session, self.interval):
                return None
            return refresh_currency_rates(session, self._settings)

    def sync_market_data_if_due(self) -> dict[str, int] | None:
        # Imported here because market_intelligence depends on this module.
        from .market_intelligence import market_data_due, sync_market_data

        with self._session_factory() as session:
            if not market_data_due(session):
                return None
            return sync_market_data(session, self._settings)

    def _run(self) -> None:
        # Let the API finish starting before the first network call.
        if self._stop.wait(5):
            return
        while not self._stop.is_set():
            try:
                self.run_once()
            except Exception:  # noqa: BLE001 - a failed refresh must never stop the scheduler
                logger.exception("FX refresh scheduler iteration failed")
            try:
                self.sync_market_data_if_due()
            except Exception:  # noqa: BLE001
                logger.exception("Market data sync failed")
            # Check hourly; run_once only calls the provider when rates are due.
            if self._stop.wait(min(self.interval.total_seconds(), 3600)):
                return
