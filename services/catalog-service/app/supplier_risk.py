from __future__ import annotations

from decimal import Decimal


HIGH_RISK_RATING_CUTOFF = Decimal("3.50")
MEDIUM_RISK_RATING_CUTOFF = Decimal("4.20")


def supplier_risk_label(rating: Decimal | float | int | str) -> str:
    value = Decimal(str(rating))
    if value < HIGH_RISK_RATING_CUTOFF:
        return "High"
    if value < MEDIUM_RISK_RATING_CUTOFF:
        return "Medium"
    return "Low"
