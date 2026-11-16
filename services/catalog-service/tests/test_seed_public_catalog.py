from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

from app.db import Base
from app.models import AccountUser, Order, Product
from scripts import seed_public_catalog as script

SERVICE_ROOT = Path(__file__).resolve().parents[1]


def _empty_database(tmp_path: Path) -> str:
    url = f"sqlite:///{(tmp_path / 'catalog.sqlite3').as_posix()}"
    engine = create_engine(url)
    Base.metadata.create_all(engine)
    engine.dispose()
    return url


def test_fills_an_empty_database_with_the_catalog_only(tmp_path: Path) -> None:
    url = _empty_database(tmp_path)

    counts = script.seed_public_catalog(url)

    assert (counts["categories"], counts["products"]) == (27, 610)
    assert counts["offers"] > 0
    engine = create_engine(url)
    with Session(engine) as session:
        assert session.scalar(select(func.count(AccountUser.id))) == 0
        assert session.scalar(select(func.count(Order.id))) == 0
    engine.dispose()


def test_running_again_keeps_rows_an_operator_changed(tmp_path: Path) -> None:
    url = _empty_database(tmp_path)
    first = script.seed_public_catalog(url)
    engine = create_engine(url)
    with Session(engine) as session:
        product = session.scalar(select(Product).where(Product.slug == "iphone-14"))
        assert product is not None
        product.name = "Operator renamed listing"
        session.commit()
    engine.dispose()

    second = script.seed_public_catalog(url)

    assert second == first
    engine = create_engine(url)
    with Session(engine) as session:
        assert session.scalar(select(Product.name).where(Product.slug == "iphone-14")) == "Operator renamed listing"
    engine.dispose()


def test_does_nothing_unless_enabled(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    monkeypatch.delenv(script.ENABLE_FLAG, raising=False)
    called = []
    monkeypatch.setattr(script, "seed_public_catalog", lambda url: called.append(url))

    assert script.main() == 0
    assert called == []
    assert "skipped" in capsys.readouterr().out

    monkeypatch.setenv(script.ENABLE_FLAG, "true")
    monkeypatch.setattr(script, "seed_public_catalog", lambda url: {"categories": 1, "products": 2, "offers": 3})
    assert script.main() == 0
    assert "products=2" in capsys.readouterr().out


def test_a_failed_seed_fails_the_deploy(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(script.ENABLE_FLAG, "true")

    def broken(url: str) -> dict[str, int]:
        raise RuntimeError("database unreachable")

    monkeypatch.setattr(script, "seed_public_catalog", broken)
    assert script.main() == 1


def test_container_entry_point_and_blueprint_enable_the_seed() -> None:
    entry_point = (SERVICE_ROOT / "docker-entrypoint.sh").read_text(encoding="utf-8")
    assert entry_point.index("alembic upgrade head") < entry_point.index("scripts.seed_public_catalog")
    assert entry_point.index("scripts.seed_public_catalog") < entry_point.index('exec "$@"')

    # Text checks keep the test free of a YAML dependency.
    blueprint = (SERVICE_ROOT.parents[1] / "render.yaml").read_text(encoding="utf-8")
    assert '- key: CATALOG_SEED_PUBLIC_CATALOG\n        value: "true"' in blueprint
    assert "fromDatabase:\n          name: cross-border-product-sourcing-db\n          property: connectionString" in blueprint
    databases = blueprint[blueprint.index("\ndatabases:"):]
    assert "  - name: cross-border-product-sourcing-db\n" in databases
