from __future__ import annotations

import io
import json
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.admin_schemas import CurrencyRateIn
from app.api.routes.admin_operations import pricing_freshness, put_currency
from app.config import Settings
from app.models import (
    AdminAuditEvent,
    Base,
    Category,
    Country,
    CurrencyRate,
    DutyRule,
    Product,
    ProductVariant,
    Seller,
    SellerOffer,
    ShippingRateCard,
)
from app.schemas import QuoteRequestIn
from app.services import automation, pricing
from app.services.sourcing import build_quote

ADMIN = {"sub": 9001, "role": "admin"}
NOW = datetime.now(timezone.utc)


@pytest.fixture()
def session():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    with Session(engine, expire_on_commit=False) as db:
        category = Category(name="Office", slug="office")
        product = Product(name="Desk Lamp", slug="desk-lamp", category=category)
        variant = ProductVariant(product=product, sku="LAMP-1", variant_name="Standard", weight_kg=Decimal("1.000"))
        country = Country(code="CN", name="China")
        seller = Seller(country=country, name="Lamp Works", rating=Decimal("4.60"))
        db.add_all(
            [
                product,
                variant,
                country,
                seller,
                SellerOffer(
                    variant=variant,
                    country=country,
                    seller=seller,
                    mode="LOCAL",
                    price_origin=Decimal("10.00"),
                    currency="USD",
                    stock=50,
                    moq=1,
                    source_url="https://supplier.example.com/lamp",
                ),
                CurrencyRate(currency="USD", rate_to_bdt=Decimal("120")),
                CurrencyRate(currency="CNY", rate_to_bdt=Decimal("16.5")),
                CurrencyRate(currency="BDT", rate_to_bdt=Decimal("1")),
                ShippingRateCard(
                    country=country, method="AIR", min_kg=Decimal("0"), max_kg=Decimal("50"), cost_bdt=Decimal("300")
                ),
                DutyRule(country=country, percent=Decimal("10"), fixed_bdt=Decimal("0")),
            ]
        )
        db.commit()
        yield db
    engine.dispose()


def _quote(db: Session) -> dict:
    return build_quote(db, QuoteRequestIn(variant_id=1, country="CN", mode="LOCAL", qty=2, delivery_type="DOOR"))


def _verify_all(db: Session, when: datetime) -> None:
    for model in (SellerOffer, CurrencyRate, ShippingRateCard, DutyRule):
        for row in db.scalars(select(model)).all():
            row.price_source = "admin"
            row.verified_at = when
    db.commit()


def test_seeded_prices_are_reported_as_unverified_and_indicative(session: Session) -> None:
    pricing_block = _quote(session)["pricing"]

    assert pricing_block["status"] == "indicative"
    assert [item["component"] for item in pricing_block["components"]] == [
        "supplier_offer",
        "fx_rate",
        "freight",
        "customs_duty",
    ]
    assert all(item["stale_reasons"] == ["unverified"] for item in pricing_block["components"])
    assert all(item["source"] == "seeded" for item in pricing_block["components"])
    offer = pricing_block["components"][0]
    assert offer["reference"] == "https://supplier.example.com/lamp"
    assert pricing_block["components"][1]["rate_to_bdt"] == "120.00000000"


def test_recently_verified_prices_make_the_quote_verified(session: Session) -> None:
    _verify_all(session, NOW - timedelta(hours=1))

    pricing_block = _quote(session)["pricing"]

    assert pricing_block["status"] == "verified"
    assert pricing_block["stale_components"] == []
    assert pricing_block["policy"]["fx_max_age_hours"] == 48


def test_each_component_uses_its_own_maximum_age(session: Session) -> None:
    _verify_all(session, NOW - timedelta(hours=1))
    offer = session.scalar(select(SellerOffer))
    offer.verified_at = NOW - timedelta(days=8)  # offer policy is 7 days
    freight = session.scalar(select(ShippingRateCard))
    freight.verified_at = NOW - timedelta(days=20)  # freight policy is 30 days
    session.commit()

    pricing_block = _quote(session)["pricing"]

    assert pricing_block["status"] == "indicative"
    assert pricing_block["stale_components"] == ["supplier_offer"]
    offer_component = pricing_block["components"][0]
    assert offer_component["stale_reasons"] == ["older_than_policy"]
    assert offer_component["age_hours"] >= 8 * 24


def test_expired_validity_period_marks_component_stale(session: Session) -> None:
    _verify_all(session, NOW - timedelta(hours=1))
    rate = session.scalar(select(CurrencyRate).where(CurrencyRate.currency == "USD"))
    rate.valid_until = NOW - timedelta(minutes=1)
    session.commit()

    pricing_block = _quote(session)["pricing"]

    assert pricing_block["stale_components"] == ["fx_rate"]
    assert pricing_block["components"][1]["stale_reasons"] == ["validity_ended"]


def test_live_fx_refresh_updates_rates_and_provenance(session: Session) -> None:
    def fake_fetch(_url: str):
        return {"USD": Decimal("1"), "BDT": Decimal("124.6"), "CNY": Decimal("7.12")}, NOW

    result = pricing.refresh_currency_rates(session, Settings(database_url="sqlite://"), fetch=fake_fetch, now=NOW)

    assert result.ok
    assert {item["currency"] for item in result.updated} == {"USD", "CNY"}
    usd = session.scalar(select(CurrencyRate).where(CurrencyRate.currency == "USD"))
    cny = session.scalar(select(CurrencyRate).where(CurrencyRate.currency == "CNY"))
    bdt = session.scalar(select(CurrencyRate).where(CurrencyRate.currency == "BDT"))
    assert usd.rate_to_bdt == Decimal("124.6")
    assert cny.rate_to_bdt == (Decimal("124.6") / Decimal("7.12")).quantize(Decimal("0.00000001"))
    assert usd.price_source == "api"
    assert "ExchangeRate-API" in usd.source_reference
    assert pricing.as_aware_utc(usd.verified_at) == NOW
    assert bdt.price_source == "seeded"

    fx_component = _quote(session)["pricing"]["components"][1]
    assert fx_component["fresh"] is True
    assert fx_component["source"] == "api"


def test_large_move_against_recent_live_rate_is_rejected(session: Session) -> None:
    usd = session.scalar(select(CurrencyRate).where(CurrencyRate.currency == "USD"))
    usd.price_source = "api"
    usd.verified_at = NOW - timedelta(hours=12)
    session.commit()

    def spiking_fetch(_url: str):
        return {"USD": Decimal("1"), "BDT": Decimal("160"), "CNY": Decimal("9.6")}, NOW

    result = pricing.refresh_currency_rates(session, Settings(database_url="sqlite://"), fetch=spiking_fetch, now=NOW)

    assert [item["currency"] for item in result.rejected] == ["USD"]
    assert usd.rate_to_bdt == Decimal("120")
    # CNY had only a seeded baseline, so the live value replaces it.
    assert [item["currency"] for item in result.updated] == ["CNY"]


def test_provider_failure_changes_nothing(session: Session) -> None:
    def failing_fetch(_url: str):
        raise OSError("network down")

    result = pricing.refresh_currency_rates(session, Settings(database_url="sqlite://"), fetch=failing_fetch)

    assert result.ok is False
    assert "FX provider unavailable" in result.error
    assert session.scalar(select(CurrencyRate).where(CurrencyRate.currency == "USD")).price_source == "seeded"


def test_fetch_usd_rates_parses_provider_payload(monkeypatch: pytest.MonkeyPatch) -> None:
    payload = {
        "result": "success",
        "base_code": "USD",
        "time_last_update_unix": 1_762_819_352,
        "rates": {"USD": 1, "BDT": 124.61, "CNY": 6.68, "BAD": "x", "ZERO": 0},
    }

    class Response(io.BytesIO):
        status = 200

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return None

    monkeypatch.setattr(pricing, "urlopen", lambda *_a, **_k: Response(json.dumps(payload).encode()))

    rates, updated_at = pricing.fetch_usd_rates("https://open.er-api.com/v6/latest/USD")

    assert rates == {"USD": Decimal("1"), "BDT": Decimal("124.61"), "CNY": Decimal("6.68")}
    assert updated_at == datetime.fromtimestamp(1_762_819_352, tz=timezone.utc)


def test_fx_refresh_is_due_until_every_rate_is_recently_live(session: Session) -> None:
    interval = timedelta(hours=12)
    assert pricing.fx_refresh_due(session, interval, NOW) is True

    for rate in session.scalars(select(CurrencyRate)).all():
        rate.price_source = "api"
        rate.verified_at = NOW - timedelta(hours=1)
    session.commit()
    assert pricing.fx_refresh_due(session, interval, NOW) is False
    assert pricing.fx_refresh_due(session, interval, NOW + timedelta(hours=12)) is True


def test_admin_rate_change_is_stamped_as_admin_verified(session: Session) -> None:
    usd = session.scalar(select(CurrencyRate).where(CurrencyRate.currency == "USD"))

    response = put_currency(
        usd.id,
        CurrencyRateIn(currency="USD", rate_to_bdt=Decimal("121.25"), note="Bank rate confirmed by phone"),
        session,
        ADMIN,
    )

    assert response["price_source"] == "admin"
    assert response["verified_at"] is not None
    assert response["rate_to_bdt"] == "121.25"
    assert session.scalar(select(AdminAuditEvent.action)) == "currency_rate.updated"


def test_freshness_report_counts_stale_inputs(session: Session) -> None:
    _verify_all(session, NOW - timedelta(hours=1))
    offer = session.scalar(select(SellerOffer))
    offer.verified_at = None
    session.commit()

    report = pricing_freshness(session, ADMIN)

    by_component = {item["component"]: item for item in report["components"]}
    assert by_component["supplier_offer"]["stale"] == 1
    assert by_component["fx_rate"]["stale"] == 0
    assert by_component["fx_rate"]["active"] == 3


def test_indicative_prices_raise_risk_and_reach_the_explanation_context() -> None:
    quote = {
        "offers_top": [{"seller": "Lamp Works", "rating": "4.6"}],
        "breakdown": {"total_bdt": "3000.00"},
        "eta": {"min_days": 5, "max_days": 9},
        "pricing": {"status": "indicative", "stale_components": ["supplier_offer"]},
    }

    context = automation.quote_automation_context(quote, country_code="CN", mode="LOCAL", language="bn")
    fallback = automation.fallback_explanation(context)

    route = context["recommendations"][0]
    assert context["pricing_status"] == "indicative"
    assert route["risk_level"] == "Medium"
    assert route["stale_price_components"] == ["supplier_offer"]
    assert context["data_gaps"][0] == automation.INDICATIVE_PRICE_GAP
    assert fallback["human_review_required"] is True
    assert fallback["missing_information"][0].startswith("দাম আনুমানিক")
    assert "pricing_status" in automation._CLAUDE_SYSTEM_PROMPT
