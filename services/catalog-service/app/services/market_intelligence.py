"""Exchange-rate outlook and country risk built from published external data.

Nothing here is generated or assumed by the application:

- FX history is one observed rate per currency per day from the open
  fawazahmed0 currency-api dataset. The outlook is a random walk with drift
  fitted on that history, reported with a 90% interval and a walk-forward
  backtest so its accuracy is visible. It is an estimate, not a promise.
- Country risk combines three World Bank indicators (political stability,
  regulatory quality, logistics performance), each stored with its year.
"""

from __future__ import annotations

import json
import logging
import math
import statistics
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Any, Callable
from urllib.request import Request, urlopen

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..config import Settings
from ..models import Country, CountryRiskIndicator, CurrencyRate, FxRateHistory
from .pricing import utc_now

logger = logging.getLogger(__name__)

FX_HISTORY_SOURCE = "fawazahmed0 currency-api"
WORLD_BANK_SOURCE = "World Bank"
MIN_HISTORY_POINTS = 30
INTERVAL_Z = 1.645  # two-sided 90% interval under a normal approximation

# code -> (name, converter to a 0-100 score where higher is better)
WORLD_BANK_INDICATORS: dict[str, tuple[str, Callable[[float], float]]] = {
    "GOV_WGI_PV.SC": ("Political stability and absence of violence (WGI, 0-100)", lambda value: value),
    "GOV_WGI_RQ.SC": ("Regulatory quality (WGI, 0-100)", lambda value: value),
    "LP.LPI.OVRL.XQ": ("Logistics Performance Index (1-5, rescaled to 0-100)", lambda value: (value - 1) / 4 * 100),
}
RISK_LOW_FROM = 70.0
RISK_MEDIUM_FROM = 55.0


def _get_json(url: str, timeout_seconds: float = 20.0) -> Any:
    request = Request(url, headers={"Accept": "application/json", "User-Agent": "SourceAI-Market/1.0"})
    with urlopen(request, timeout=timeout_seconds) as response:  # noqa: S310 - operator-configured HTTPS sources
        return json.loads(response.read(5_000_000).decode("utf-8"))


# ---------------------------------------------------------------- FX history


def fetch_usd_rates_for_date(template: str, day: date) -> dict[str, float] | None:
    """Units of each currency per 1 USD on a given day, or None when unavailable."""

    try:
        body = _get_json(template.format(date=day.isoformat()))
    except Exception as error:  # noqa: BLE001 - a missing day must not stop the backfill
        logger.info("FX history unavailable for %s: %s", day, error.__class__.__name__)
        return None
    rates = body.get("usd") if isinstance(body, dict) else None
    return {str(code).upper(): float(value) for code, value in rates.items()} if isinstance(rates, dict) else None


def backfill_fx_history(
    session: Session,
    settings: Settings,
    *,
    fetch: Callable[[str, date], dict[str, float] | None] | None = None,
    today: date | None = None,
) -> int:
    """Store any missing daily rates for the active currencies. Returns rows added."""

    today = today or utc_now().date()
    currencies = [
        code
        for code in (
            row.strip().upper()
            for row in session.scalars(select(CurrencyRate.currency).where(CurrencyRate.is_active.is_(True))).all()
        )
        if code != "BDT"
    ]
    if not currencies:
        return 0
    wanted = [today - timedelta(days=offset) for offset in range(1, settings.fx_history_days + 1)]
    existing = {
        (currency, rate_date)
        for currency, rate_date in session.execute(
            select(FxRateHistory.currency, FxRateHistory.rate_date).where(FxRateHistory.rate_date >= wanted[-1])
        ).all()
    }
    missing_days = [day for day in wanted if any((code, day) not in existing for code in currencies)]
    if not missing_days:
        return 0
    fetcher = fetch or fetch_usd_rates_for_date
    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(lambda day: (day, fetcher(settings.fx_history_url_template, day)), missing_days))
    added = 0
    for day, rates in results:
        bdt_per_usd = (rates or {}).get("BDT")
        if not bdt_per_usd:
            continue
        for code in currencies:
            units = rates.get(code)
            if not units or (code, day) in existing:
                continue
            session.add(
                FxRateHistory(
                    currency=code,
                    rate_date=day,
                    rate_to_bdt=Decimal(str(bdt_per_usd / units)).quantize(Decimal("0.00000001")),
                    source=FX_HISTORY_SOURCE,
                )
            )
            added += 1
    session.commit()
    logger.info("FX history backfill added %d rows", added)
    return added


def _history(session: Session, currency: str) -> list[tuple[date, float]]:
    rows = session.execute(
        select(FxRateHistory.rate_date, FxRateHistory.rate_to_bdt)
        .where(FxRateHistory.currency == currency.strip().upper())
        .order_by(FxRateHistory.rate_date.asc())
    ).all()
    return [(rate_date, float(rate)) for rate_date, rate in rows]


def _project(series: list[tuple[date, float]], horizon_days: int) -> tuple[float, float, float, float] | None:
    """Random walk with drift on daily log returns: (expected, low, high, daily volatility)."""

    if len(series) < MIN_HISTORY_POINTS:
        return None
    returns: list[float] = []
    for (previous_day, previous), (current_day, current) in zip(series, series[1:]):
        gap = max((current_day - previous_day).days, 1)
        if previous > 0 and current > 0:
            returns.append(math.log(current / previous) / gap)
    if len(returns) < MIN_HISTORY_POINTS - 1:
        return None
    drift = statistics.fmean(returns)
    volatility = statistics.stdev(returns)
    last = series[-1][1]
    centre = drift * horizon_days
    spread = INTERVAL_Z * volatility * math.sqrt(horizon_days)
    return last * math.exp(centre), last * math.exp(centre - spread), last * math.exp(centre + spread), volatility


def _backtest(series: list[tuple[date, float]], horizon_days: int) -> dict[str, Any] | None:
    """Walk forward through history and score past forecasts against what happened."""

    by_day = dict(series)
    errors: list[float] = []
    covered = 0
    for index in range(MIN_HISTORY_POINTS, len(series)):
        origin_day = series[index - 1][0]
        actual = by_day.get(origin_day + timedelta(days=horizon_days))
        projection = _project(series[:index], horizon_days)
        if actual is None or projection is None:
            continue
        expected, low, high, _ = projection
        errors.append(abs(expected - actual) / actual * 100)
        covered += 1 if low <= actual <= high else 0
    if len(errors) < 5:
        return None
    return {
        "forecasts_scored": len(errors),
        "mean_absolute_percent_error": round(statistics.fmean(errors), 2),
        "interval_coverage_percent": round(covered / len(errors) * 100, 1),
    }


def fx_outlook(session: Session, currency: str, horizon_days: int = 30) -> dict[str, Any]:
    code = (currency or "").strip().upper()
    series = _history(session, code)
    base = {
        "currency": code,
        "horizon_days": horizon_days,
        "history_points": len(series),
        "source": FX_HISTORY_SOURCE,
        "method": "Random walk with drift on daily log returns; 90% interval",
    }
    projection = _project(series, horizon_days)
    if projection is None:
        return {**base, "available": False, "reason": "insufficient_history"}
    expected, low, high, volatility = projection
    last_day, last_rate = series[-1]
    return {
        **base,
        "available": True,
        "history_from": series[0][0].isoformat(),
        "history_to": last_day.isoformat(),
        "last_rate_to_bdt": round(last_rate, 6),
        "expected_rate_to_bdt": round(expected, 6),
        "low_rate_to_bdt": round(low, 6),
        "high_rate_to_bdt": round(high, 6),
        "low_change_percent": round((low / last_rate - 1) * 100, 2),
        "high_change_percent": round((high / last_rate - 1) * 100, 2),
        "daily_volatility_percent": round(volatility * 100, 3),
        "backtest": _backtest(series, horizon_days),
    }


# -------------------------------------------------------------- country risk


def fetch_world_bank_indicator(indicator: str, country_codes: list[str]) -> list[tuple[str, int, float]]:
    """Most recent published value per country: (ISO2 code, year, raw value)."""

    url = (
        f"https://api.worldbank.org/v2/country/{';'.join(country_codes)}/indicator/{indicator}"
        f"?format=json&mrnev=1&per_page=200" + ("&source=3" if indicator.startswith("GOV_WGI_") else "")
    )
    body = _get_json(url)
    rows = body[1] if isinstance(body, list) and len(body) > 1 and isinstance(body[1], list) else []
    return [
        (str(row["country"]["id"]).upper(), int(row["date"]), float(row["value"]))
        for row in rows
        if row.get("value") is not None
    ]


def refresh_country_risk(
    session: Session,
    *,
    fetch: Callable[[str, list[str]], list[tuple[str, int, float]]] | None = None,
) -> int:
    """Replace stored indicators with the latest published values. Returns rows written."""

    countries = {country.code.upper(): country for country in session.scalars(select(Country)).all()}
    if not countries:
        return 0
    fetcher = fetch or fetch_world_bank_indicator
    stored = {
        (row.country_id, row.indicator_code): row for row in session.scalars(select(CountryRiskIndicator)).all()
    }
    written = 0
    now = utc_now()
    for code, (name, to_score) in WORLD_BANK_INDICATORS.items():
        try:
            values = fetcher(code, sorted(countries))
        except Exception as error:  # noqa: BLE001 - keep previously stored indicators on failure
            logger.warning("World Bank indicator %s unavailable: %s", code, error.__class__.__name__)
            continue
        for country_code, year, raw in values:
            country = countries.get(country_code)
            if country is None:
                continue
            score = Decimal(str(max(0.0, min(100.0, to_score(raw))))).quantize(Decimal("0.01"))
            row = stored.get((country.id, code))
            if row is None:
                row = CountryRiskIndicator(country_id=country.id, indicator_code=code)
                session.add(row)
                stored[(country.id, code)] = row
            row.indicator_name = name
            row.score = score
            row.data_year = year
            row.source = WORLD_BANK_SOURCE
            row.fetched_at = now
            written += 1
    session.commit()
    logger.info("Country risk refresh wrote %d indicator rows", written)
    return written


def risk_level_for_score(score: float) -> str:
    return "Low" if score >= RISK_LOW_FROM else "Medium" if score >= RISK_MEDIUM_FROM else "High"


def country_risk_map(session: Session) -> dict[int, dict[str, Any]]:
    """Composite country risk per country id; countries without data are omitted."""

    grouped: dict[int, list[CountryRiskIndicator]] = {}
    for row in session.scalars(select(CountryRiskIndicator).order_by(CountryRiskIndicator.indicator_code)).all():
        grouped.setdefault(row.country_id, []).append(row)
    result: dict[int, dict[str, Any]] = {}
    for country_id, rows in grouped.items():
        score = statistics.fmean(float(row.score) for row in rows)
        result[country_id] = {
            "score": round(score, 1),
            "level": risk_level_for_score(score),
            "source": WORLD_BANK_SOURCE,
            "method": "Mean of the listed indicators (0-100, higher is safer); Low >= 70, Medium >= 55",
            "indicators": [
                {"code": row.indicator_code, "name": row.indicator_name, "score": float(row.score), "year": row.data_year}
                for row in rows
            ],
        }
    return result


# ------------------------------------------------------------------ syncing


def market_data_due(session: Session, today: date | None = None) -> bool:
    today = today or utc_now().date()
    latest_history = session.scalar(select(func.max(FxRateHistory.rate_date)))
    latest_risk: datetime | None = session.scalar(select(func.max(CountryRiskIndicator.fetched_at)))
    history_stale = latest_history is None or latest_history < today - timedelta(days=2)
    risk_stale = latest_risk is None or latest_risk.replace(tzinfo=None) < datetime.combine(
        today - timedelta(days=30), datetime.min.time()
    )
    return history_stale or risk_stale


def sync_market_data(session: Session, settings: Settings) -> dict[str, int]:
    return {
        "fx_history_rows_added": backfill_fx_history(session, settings),
        "country_risk_rows_written": refresh_country_risk(session),
    }
