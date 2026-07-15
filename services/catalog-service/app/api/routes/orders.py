from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.orm import Session

from ...auth import get_current_user
from ...db import get_session
from ...schemas import CreateOrderIn, SaveQuoteIn, UpdateOrderStatusIn, UpdateQuoteStatusIn
from ...serializers import serialize_order, serialize_saved_quote
from ...services.orders import (
    create_manual_order_record,
    delete_saved_quote_record,
    get_saved_quote_or_404,
    get_order_or_404,
    list_orders_for_user,
    list_saved_quotes_for_user,
    save_quote_record,
    update_saved_quote_status,
    update_order_status_record,
)


router = APIRouter()


@router.post("/api/quote/save/", status_code=status.HTTP_201_CREATED)
def save_quote(
    payload: SaveQuoteIn,
    session: Session = Depends(get_session),
    current_user: dict[str, Any] = Depends(get_current_user),
) -> dict[str, int]:
    saved_quote = save_quote_record(session, payload, current_user)
    return {"id": saved_quote.id}


@router.get("/api/quote/saved/")
def saved_quotes(
    session: Session = Depends(get_session),
    current_user: dict[str, Any] = Depends(get_current_user),
) -> list[dict[str, Any]]:
    return [
        serialize_saved_quote(saved_quote)
        for saved_quote in list_saved_quotes_for_user(session, current_user)
    ]


@router.delete("/api/quote/saved/{quote_id}/", status_code=status.HTTP_204_NO_CONTENT, response_class=Response)
def delete_saved_quote(quote_id: int, session: Session = Depends(get_session),
                       current_user: dict[str, Any] = Depends(get_current_user)) -> Response:
    delete_saved_quote_record(session, quote_id, current_user)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.patch("/api/quote/saved/{quote_id}/status/")
def update_quote_status(quote_id: int, payload: UpdateQuoteStatusIn, session: Session = Depends(get_session),
                        current_user: dict[str, Any] = Depends(get_current_user)) -> dict[str, Any]:
    quote = update_saved_quote_status(session, quote_id, payload.status, current_user)
    return {"id": quote.id, "status": (quote.response or {}).get("status")}


def _simple_pdf(lines: list[str]) -> bytes:
    safe = [line.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)") for line in lines]
    stream = "BT /F1 12 Tf 50 790 Td " + " 0 -22 Td ".join(f"({line}) Tj" for line in safe) + " ET"
    objects = ["1 0 obj << /Type /Catalog /Pages 2 0 R >> endobj", "2 0 obj << /Type /Pages /Kids [3 0 R] /Count 1 >> endobj", "3 0 obj << /Type /Page /Parent 2 0 R /MediaBox [0 0 612 842] /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >> endobj", "4 0 obj << /Type /Font /Subtype /Type1 /BaseFont /Helvetica >> endobj", f"5 0 obj << /Length {len(stream.encode())} >> stream\n{stream}\nendstream endobj"]
    result = b"%PDF-1.4\n"; offsets = [0]
    for obj in objects: offsets.append(len(result)); result += (obj + "\n").encode()
    xref = len(result); result += f"xref\n0 {len(objects)+1}\n0000000000 65535 f \n".encode()
    for offset in offsets[1:]: result += f"{offset:010d} 00000 n \n".encode()
    result += f"trailer << /Size {len(objects)+1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF".encode(); return result


@router.get("/api/quote/saved/{quote_id}/pdf/")
def quote_pdf(quote_id: int, session: Session = Depends(get_session),
              current_user: dict[str, Any] = Depends(get_current_user)) -> Response:
    quote = get_saved_quote_or_404(session, quote_id, current_user); breakdown = (quote.response or {}).get("breakdown", {})
    pdf = _simple_pdf(["SourceAI Sourcing Quotation", f"Quote #{quote.id}", f"Product: {quote.product_name}",
                       f"Variant: {quote.variant_name}", f"Country: {quote.country_code}", f"Quantity: {quote.qty}",
                       f"Total landed cost: BDT {breakdown.get('total_bdt', 'N/A')}", f"Status: {(quote.response or {}).get('status', 'requested')}"])
    return Response(pdf, media_type="application/pdf", headers={"Content-Disposition": f"attachment; filename=sourceai-quote-{quote.id}.pdf"})


@router.post("/api/orders/create-manual/")
def create_manual_order(
    payload: CreateOrderIn,
    session: Session = Depends(get_session),
    current_user: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
    order = create_manual_order_record(session, payload, current_user)
    return {"order_id": order.id, "status": order.status}


@router.get("/api/orders/me/")
def my_orders(
    session: Session = Depends(get_session),
    current_user: dict[str, Any] = Depends(get_current_user),
) -> list[dict[str, Any]]:
    return [serialize_order(order) for order in list_orders_for_user(session, current_user)]


@router.get("/api/orders/{order_id}/")
def order_detail(
    order_id: int,
    session: Session = Depends(get_session),
    current_user: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
    return serialize_order(get_order_or_404(session, order_id, current_user))


@router.post("/api/orders/{order_id}/status/")
def update_order_status(
    order_id: int,
    payload: UpdateOrderStatusIn,
    session: Session = Depends(get_session),
    current_user: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
    order = update_order_status_record(session, order_id, payload, current_user)
    return {"id": order.id, "status": order.status}
