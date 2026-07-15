from __future__ import annotations
from typing import Any
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from ...auth import get_current_user
from ...db import get_session
from ...models import Order, Product, SavedQuote, Seller, SellerOffer

router = APIRouter()

def require_admin(user: dict[str, Any]) -> None:
    if user.get("role") not in {"admin", "operator"}:
        raise HTTPException(status_code=403, detail="Admin or operator access required")

@router.get("/api/admin/overview/")
def overview(session: Session = Depends(get_session), user: dict[str, Any] = Depends(get_current_user)) -> dict[str, Any]:
    require_admin(user)
    sellers = session.scalars(select(Seller).order_by(Seller.rating.asc())).all()
    quotes = session.scalar(select(func.count(SavedQuote.id))) or 0
    orders = session.scalars(select(Order)).all()
    return {"cards": {"products": session.scalar(select(func.count(Product.id))) or 0,
                       "suppliers": len(sellers), "offers": session.scalar(select(func.count(SellerOffer.id))) or 0,
                       "pending_quotes": quotes, "active_orders": sum(1 for item in orders if item.status not in {"DELIVERED", "CANCELLED"}),
                       "quote_to_order_percent": round(len(orders) / quotes * 100, 2) if quotes else 0},
            "supplier_alerts": [{"id": item.id, "name": item.name, "country": item.country.name,
                                  "rating": float(item.rating), "risk": "High" if item.rating < 3.5 else "Medium" if item.rating < 4.2 else "Low"}
                                 for item in sellers[:10]]}
