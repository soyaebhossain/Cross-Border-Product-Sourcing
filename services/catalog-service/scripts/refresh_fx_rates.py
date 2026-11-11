"""Refresh active currency rates from the live FX provider once.

Use this from a scheduler (cron, Render cron job, Kubernetes CronJob) when the
API's in-process refresh (CATALOG_FX_AUTO_REFRESH_ENABLED) is not used:

    python -m scripts.refresh_fx_rates
"""

from __future__ import annotations

import json
import sys

from app.config import get_settings
from app.db import SessionLocal
from app.services.pricing import refresh_currency_rates


def main() -> int:
    settings = get_settings()
    with SessionLocal() as session:
        result = refresh_currency_rates(session, settings)
    print(json.dumps(result.as_dict(), indent=2))
    return 0 if result.ok else 1


if __name__ == "__main__":
    sys.exit(main())
