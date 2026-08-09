from __future__ import annotations

import pytest

from app.config import Settings


@pytest.fixture(autouse=True)
def isolate_settings_from_local_dotenv(monkeypatch: pytest.MonkeyPatch) -> None:
    """Keep developer-only .env values from changing test behavior."""

    monkeypatch.setitem(Settings.model_config, "env_file", None)
