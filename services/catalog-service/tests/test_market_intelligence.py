from __future__ import annotations

import math
from datetime import date, timedelta
from decimal import Decimal

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.config import Settings
from app.models import (
    Base,
    Category,
    Country,
    CountryRiskIndicator,
    CurrencyRate,
    DutyRule,
    FxRateHistory,
    Product,
    ProductVariant,
    Seller,
    SellerOffer,
    ServiceFeeRule,
    ShippingRateCard,
)
from app.schemas import CheapestCountryRecommendIn, QuoteRequestIn
from app.services import market_intelligence as mi
from app.services.sourcing import build_country_recommendations, build_quote, risk_assessment

TODAY = date(2026, 11, 12)


@pytest.fixture()
def session():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    with Session(engine, expire_on_commit=False) as db:
        category = Category(name="Office", slug="office")
        product = Product(name="Desk Lamp", slug="desk-lamp", category=category)
        variant = ProductVariant(product=product, sku="LAMP-1", variant_name="Standard", weight_kg=Decimal("1.000"))
        china = Country(code="CN", name="China")
        turkey = Country(code="TR", name="Turkey")
        db.add_all([product, variant, china, turkey])
        for country, price in ((china, "10.00"), (turkey, "10.00")):
            seller = Seller(country=country, name=f"{country.name} Works", rating=Decimal("4.60"))
            db.add_all(
                [
                    seller,
                    SellerOffer(variant=variant, country=country, seller=seller, mode="LOCAL",
                                price_origin=Decimal(price), currency="USD", stock=500, moq=1),
                    ShippingRateCard(country=country, method="AIR", min_kg=Decimal("0"), max_kg=Decimal("50"),
                                     cost_bdt=Decimal("300")),
                    DutyRule(country=country, percent=Decimal("10"), fixed_bdt=Decimal("0")),
                ]
            )
        db.add_all(
            [
                CurrencyRate(currency="USD", rate_to_bdt=Decimal("120")),
                ServiceFeeRule(mode="LOCAL", fee_bdt=Decimal("100"), percent=Decimal("5")),
            ]
        )
        db.commit()
        yield db
    engine.dispose()


def _add_history(db: Session, days: int, rate_for_day) -> None:
    for offset in range(days, 0, -1):
        day = TODAY - timedelta(days=offset)
        db.add(FxRateHistory(currency="USD", rate_date=day, rate_to_bdt=Decimal(str(rate_for_day(days - offset))),
                             source="test"))
    db.commit()


def test_outlook_needs_enough_history(session: Session) -> None:
    _add_history(session, 10, lambda index: 120 + index * 0.01)

    outlook = mi.fx_outlook(session, "usd", 30)

    assert outlook["available"] is False
    assert outlook["reason"] == "insufficient_history"
    assert outlook["history_points"] == 10


def test_outlook_follows_drift_and_reports_interval_and_backtest(session: Session) -> None:
    # Steady 0.02% daily rise with a small alternating wobble.
    _add_history(session, 120, lambda index: 120 * math.exp(0.0002 * index) * (1 + (0.0005 if index % 2 else -0.0005)))

    outlook = mi.fx_outlook(session, "USD", 30)

    assert outlook["available"] is True
    assert outlook["history_points"] == 120
    assert outlook["low_rate_to_bdt"] < outlook["expected_rate_to_bdt"] < outlook["high_rate_to_bdt"]
    assert outlook["expected_rate_to_bdt"] > outlook["last_rate_to_bdt"]
    assert outlook["expected_rate_to_bdt"] == pytest.approx(outlook["last_rate_to_bdt"] * math.exp(0.0002 * 30), rel=0.01)
    assert outlook["backtest"]["forecasts_scored"] >= 5
    assert outlook["backtest"]["mean_absolute_percent_error"] < 1


def test_backfill_stores_cross_rates_and_skips_existing_days(session: Session) -> None:
    session.add(CurrencyRate(currency="CNY", rate_to_bdt=Decimal("16.5")))
    session.commit()
    calls: list[date] = []

    def fake_fetch(_template: str, day: date):
        calls.append(day)
        return None if day.day == 1 else {"USD": 1.0, "BDT": 124.0, "CNY": 6.2}

    settings = Settings(database_url="sqlite://", fx_history_days=40)
    added = mi.backfill_fx_history(session, settings, fetch=fake_fetch, today=TODAY)

    assert added == 39 * 2  # one day unavailable, two currencies
    cny = session.scalar(select(FxRateHistory).where(FxRateHistory.currency == "CNY").limit(1))
    assert cny.rate_to_bdt == Decimal("20.00000000")
    calls.clear()
    assert mi.backfill_fx_history(session, settings, fetch=fake_fetch, today=TODAY) == 0
    assert calls == [date(2026, 11, 1)]  # only the still-missing day is requested again


def test_quote_reports_landed_cost_range_from_fx_outlook(session: Session) -> None:
    _add_history(session, 120, lambda index: 120 * (1 + (0.002 if index % 2 else -0.002)))

    quote = build_quote(session, QuoteRequestIn(variant_id=1, country="CN", mode="LOCAL", qty=10, delivery_type="DOOR"))

    outlook = quote["fx_outlook"]
    total = Decimal(quote["breakdown"]["total_bdt"])
    assert outlook["available"] is True
    assert Decimal(outlook["total_low_bdt"]) < total < Decimal(outlook["total_high_bdt"])
    # Product cost 12000 BDT; duty 10% + VAT 5% + fee 5% ride on it, freight does not.
    expected_high = total + Decimal("12000") * Decimal(str(outlook["high_change_percent"])) / 100 * Decimal("1.20")
    assert Decimal(outlook["total_high_bdt"]) == expected_high.quantize(Decimal("0.01"))


def _fake_world_bank(indicator: str, codes: list[str]):
    assert codes == ["CN", "TR"]
    values = {
        "GOV_WGI_PV.SC": {"CN": 80.0, "TR": 40.0},
        "GOV_WGI_RQ.SC": {"CN": 70.0, "TR": 50.0},
        "LP.LPI.OVRL.XQ": {"CN": 3.8, "TR": 3.0},
    }[indicator]
    return [(code, 2025, value) for code, value in values.items()]


def test_country_risk_combines_published_indicators(session: Session) -> None:
    assert mi.refresh_country_risk(session, fetch=_fake_world_bank) == 6
    # A second refresh updates in place instead of duplicating rows.
    assert mi.refresh_country_risk(session, fetch=_fake_world_bank) == 6
    assert len(session.scalars(select(CountryRiskIndicator)).all()) == 6

    risks = {session.get(Country, country_id).code: risk for country_id, risk in mi.country_risk_map(session).items()}

    assert risks["CN"]["score"] == pytest.approx((80 + 70 + 70) / 3, abs=0.1)
    assert risks["CN"]["level"] == "Low"
    assert risks["TR"]["score"] == pytest.approx((40 + 50 + 50) / 3, abs=0.1)
    assert risks["TR"]["level"] == "High"
    assert {item["year"] for item in risks["TR"]["indicators"]} == {2025}
    assert risks["TR"]["source"] == "World Bank"


def test_country_risk_changes_route_risk_and_ranking(session: Session) -> None:
    payload = CheapestCountryRecommendIn(variant_id=1, qty=10, delivery_type="DOOR", priority="balanced")
    before = build_country_recommendations(session, payload)["recommendations"]
    assert {item["risk_level"] for item in before} == {"Low"}
    assert all(item["country_risk"] is None for item in before)

    mi.refresh_country_risk(session, fetch=_fake_world_bank)
    after = build_country_recommendations(session, payload)["recommendations"]

    by_code = {item["country"]["code"]: item for item in after}
    assert after[0]["country"]["code"] == "CN"
    assert by_code["CN"]["country_risk"]["level"] == "Low"
    assert by_code["TR"]["country_risk"]["level"] == "High"
    assert "country risk is elevated" in by_code["TR"]["weaknesses"]
    assert Decimal(by_code["TR"]["risk_score"]) > Decimal(by_code["CN"]["risk_score"])


def test_risk_assessment_country_levels() -> None:
    base = risk_assessment(Decimal("0.9"), Decimal("9"), 10, "LOCAL")
    medium = risk_assessment(Decimal("0.9"), Decimal("9"), 10, "LOCAL", "Medium")
    high = risk_assessment(Decimal("0.9"), Decimal("9"), 10, "BULK", "High")
    assert base == ("Low", Decimal("0"), [])
    assert medium[1] == Decimal("0.10") and medium[2] == ["country risk is moderate"]
    assert high[0] == "Medium" and high[1] == Decimal("0.35")


def test_recommended_sort_mixes_categories_and_keeps_order_within_one() -> None:
    from types import SimpleNamespace

    from app.services.catalog import _interleave_categories

    ranked = [SimpleNamespace(name=name, category_id=category) for name, category in (
        ("m1", 1), ("m2", 1), ("m3", 1), ("o1", 2), ("o2", 2), ("k1", 3),
    )]

    mixed = [item.name for item in _interleave_categories(ranked)]

    assert mixed == ["m1", "o1", "k1", "m2", "o2", "m3"]
