from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from math import ceil
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import String, cast, func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload, selectinload

from ...admin_schemas import (
    ArchiveIn,
    BulkArchiveIn,
    CategoryCreateIn,
    CategoryUpdateIn,
    CurrencyRateIn,
    DutyRuleIn,
    ETARuleIn,
    OfferCreateIn,
    OfferUpdateIn,
    OrderSettlementIn,
    PaymentReversalIn,
    ProductCreateIn,
    ProductUpdateIn,
    RefundCreateIn,
    RefundReverseIn,
    ServiceFeeRuleIn,
    ShippingRateCardIn,
    SupplierCreateIn,
    SupplierUpdateIn,
    UserAdminUpdateIn,
    VariantCreateIn,
    VariantUpdateIn,
)
from ...analytics_cache import invalidate_admin_analytics
from ...auth import get_current_user
from ...db import get_session
from ...models import (
    AccountUser,
    AIDecisionExplanation,
    Category,
    Country,
    CurrencyRate,
    DutyRule,
    ETARule,
    ManualPaymentProof,
    Order,
    PaymentAdjustment,
    Product,
    ProductVariant,
    RefreshSession,
    SavedQuote,
    Seller,
    SellerOffer,
    ServiceFeeRule,
    ShippingRateCard,
)
from ...schemas import AIReviewDecisionIn
from ...services.financial_operations import (
    create_refund,
    financial_snapshot,
    reverse_payment,
    reverse_refund,
    serialize_adjustment,
)
from ...services.orders import (
    get_order_or_404,
    order_loader_options,
    record_admin_audit,
    utc_now,
)


router = APIRouter()
ROLE_CAPABILITIES = {
    "customer": [
        "own_profile",
        "own_saved_quotes",
        "own_orders",
        "own_payments",
    ],
    "operator": [
        "admin_overview",
        "orders_operate",
        "payments_decide",
        "refunds_operate",
        "quotes_read",
        "catalog_read",
        "supplier_read",
    ],
    "admin": [
        "all_operator_capabilities",
        "research_analytics",
        "catalog_manage",
        "settings_manage",
        "users_manage",
        "roles_read",
        "audit_read",
    ],
}


def _ai_review_json(review: AIDecisionExplanation) -> dict[str, Any]:
    quote = review.saved_quote
    return {
        "id": review.id,
        "saved_quote_id": review.saved_quote_id,
        "product_name": quote.product_name,
        "variant_name": quote.variant_name,
        "country": quote.country_code,
        "mode": quote.mode,
        "qty": quote.qty,
        "provider": review.provider,
        "model": review.model,
        "prompt_version": review.prompt_version,
        "explanation": review.explanation,
        "confidence": review.confidence,
        "human_review_required": review.human_review_required,
        "review_status": review.review_status,
        "review_note": review.review_note,
        "reviewed_by_user_id": review.reviewed_by_user_id,
        "reviewed_at": review.reviewed_at,
        "created_at": review.created_at,
        "updated_at": review.updated_at,
    }


@router.get("/api/admin/ai-reviews/")
def list_ai_reviews(
    status_filter: str | None = Query(default=None, alias="status", max_length=20),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=100),
    session: Session = Depends(get_session),
    user: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
    require_operator(user)
    statement = select(AIDecisionExplanation).options(joinedload(AIDecisionExplanation.saved_quote))
    if status_filter:
        statement = statement.where(AIDecisionExplanation.review_status == status_filter.upper())
    statement = statement.order_by(
        AIDecisionExplanation.human_review_required.desc(),
        AIDecisionExplanation.created_at.desc(),
    )
    total = int(session.scalar(select(func.count()).select_from(statement.subquery())) or 0)
    reviews = session.scalars(statement.offset((page - 1) * page_size).limit(page_size)).all()
    return {
        "items": [_ai_review_json(review) for review in reviews],
        "total": total,
        "page": page,
        "page_size": page_size,
        "pages": ceil(total / page_size) if total else 0,
    }


@router.patch("/api/admin/ai-reviews/{review_id}/")
def decide_ai_review(
    review_id: int,
    payload: AIReviewDecisionIn,
    session: Session = Depends(get_session),
    user: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
    require_operator(user)
    review = _not_found(
        session.scalar(
            select(AIDecisionExplanation)
            .options(joinedload(AIDecisionExplanation.saved_quote))
            .where(AIDecisionExplanation.id == review_id)
        ),
        "AI review",
    )
    before = {"review_status": review.review_status, "review_note": review.review_note}
    review.review_status = payload.decision
    review.review_note = payload.note.strip()
    review.reviewed_by_user_id = int(user["sub"])
    review.reviewed_at = utc_now()
    review.updated_at = utc_now()
    record_admin_audit(
        session,
        user,
        action="ai_explanation.reviewed",
        entity_type="ai_decision_explanation",
        entity_id=review.id,
        before=before,
        after={"review_status": review.review_status, "review_note": review.review_note},
        note=payload.note,
        request_id=payload.request_id,
    )
    session.commit()
    session.refresh(review)
    return _ai_review_json(review)


def require_operator(user: dict[str, Any]) -> None:
    if user.get("role") not in {"admin", "operator"}:
        raise HTTPException(status_code=403, detail="Admin or operator access required")


def require_admin(user: dict[str, Any]) -> None:
    if user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Administrator access required")


def _money(value: Any) -> str:
    return format(Decimal(str(value or 0)), ".2f")


def _page(items: list[dict[str, Any]], total: int, page: int, page_size: int) -> dict[str, Any]:
    return {
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
        "pages": max(1, ceil(total / page_size)),
    }


def _paginate(session: Session, statement, page: int, page_size: int) -> tuple[list[Any], int]:
    total = int(
        session.scalar(select(func.count()).select_from(statement.order_by(None).subquery()))
        or 0
    )
    records = session.scalars(
        statement.offset((page - 1) * page_size).limit(page_size)
    ).unique().all()
    return records, total


def _not_found(record: Any, label: str) -> Any:
    if not record:
        raise HTTPException(status_code=404, detail=f"{label} not found")
    return record


def _commit_unique(session: Session, detail: str) -> None:
    try:
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        raise HTTPException(status_code=409, detail=detail) from exc


def _archive(
    session: Session,
    entity: Any,
    payload: ArchiveIn,
    user: dict[str, Any],
    *,
    entity_type: str,
) -> None:
    before = {
        "is_active": entity.is_active,
        "archived_at": entity.archived_at,
        "archived_by_user_id": entity.archived_by_user_id,
    }
    entity.is_active = not payload.archived
    entity.archived_at = utc_now() if payload.archived else None
    entity.archived_by_user_id = int(user["sub"]) if payload.archived else None
    if hasattr(entity, "updated_at"):
        entity.updated_at = utc_now()
    record_admin_audit(
        session,
        user,
        action=f"{entity_type}.{'archived' if payload.archived else 'restored'}",
        entity_type=entity_type,
        entity_id=entity.id,
        before=before,
        after={
            "is_active": entity.is_active,
            "archived_at": entity.archived_at,
            "archived_by_user_id": entity.archived_by_user_id,
        },
        note=payload.note,
        request_id=payload.request_id,
    )
    session.commit()
    invalidate_admin_analytics()


def _category_json(item: Category) -> dict[str, Any]:
    return {
        "id": item.id,
        "name": item.name,
        "slug": item.slug,
        "is_active": item.is_active,
        "archived_at": item.archived_at,
        "archived_by_user_id": item.archived_by_user_id,
        "product_count": len(item.products),
    }


def _variant_json(item: ProductVariant) -> dict[str, Any]:
    return {
        "id": item.id,
        "product_id": item.product_id,
        "product_name": item.product.name if item.product else None,
        "sku": item.sku,
        "variant_name": item.variant_name,
        "weight_kg": format(item.weight_kg or 0, ".3f"),
        "length_cm": _money(item.length_cm),
        "width_cm": _money(item.width_cm),
        "height_cm": _money(item.height_cm),
        "is_active": item.is_active,
        "archived_at": item.archived_at,
        "archived_by_user_id": item.archived_by_user_id,
        "offer_count": len(item.offers),
    }


def _product_json(item: Product) -> dict[str, Any]:
    return {
        "id": item.id,
        "name": item.name,
        "slug": item.slug,
        "model": item.model,
        "description": item.description,
        "image": item.image,
        "category": _category_json(item.category),
        "is_active": item.is_active,
        "archived_at": item.archived_at,
        "archived_by_user_id": item.archived_by_user_id,
        "variants": [_variant_json(variant) for variant in item.variants],
    }


def _supplier_json(item: Seller) -> dict[str, Any]:
    return {
        "id": item.id,
        "name": item.name,
        "country": {
            "id": item.country.id,
            "code": item.country.code,
            "name": item.country.name,
        },
        "rating": float(item.rating or 0),
        "note": item.note,
        "is_active": item.is_active,
        "archived_at": item.archived_at,
        "archived_by_user_id": item.archived_by_user_id,
        "offer_count": len(item.offers),
    }


def _offer_json(item: SellerOffer) -> dict[str, Any]:
    return {
        "id": item.id,
        "variant": {
            "id": item.variant.id,
            "sku": item.variant.sku,
            "name": item.variant.variant_name,
            "product_id": item.variant.product_id,
            "product_name": item.variant.product.name,
        },
        "supplier": {"id": item.seller.id, "name": item.seller.name},
        "country": {"id": item.country.id, "code": item.country.code, "name": item.country.name},
        "mode": item.mode,
        "price_origin": _money(item.price_origin),
        "currency": item.currency,
        "stock": item.stock,
        "moq": item.moq,
        "source_url": item.source_url,
        "is_active": item.is_active,
        "archived_at": item.archived_at,
        "archived_by_user_id": item.archived_by_user_id,
        "updated_at": item.updated_at,
    }


def _user_json(item: AccountUser) -> dict[str, Any]:
    return {
        "id": item.id,
        "username": item.username,
        "email": item.email,
        "phone": item.phone,
        "role": item.role,
        "is_active": item.is_active,
        "is_staff": item.is_staff,
        "is_superuser": item.is_superuser,
        "created_at": item.created_at,
    }


def _adjustments(session: Session, order_id: int) -> list[PaymentAdjustment]:
    return session.scalars(
        select(PaymentAdjustment)
        .where(PaymentAdjustment.order_id == order_id)
        .order_by(PaymentAdjustment.created_at.desc(), PaymentAdjustment.id.desc())
    ).all()


def _admin_order_json(session: Session, order: Order) -> dict[str, Any]:
    customer = session.get(AccountUser, order.user_id)
    payment = order.manual_payment
    verifier = (
        session.get(AccountUser, payment.decided_by_user_id)
        if payment and payment.decided_by_user_id
        else None
    )
    return {
        "id": order.id,
        "customer": _user_json(customer) if customer else {"id": order.user_id},
        "saved_quote_id": order.saved_quote_id,
        "status": order.status,
        "country": order.country_code,
        "mode": order.mode,
        "delivery_type": order.delivery_type,
        "total_bdt": _money(order.total_bdt),
        "shipping_bdt": _money(order.shipping_bdt),
        "advance_bdt": _money(order.advance_bdt),
        "remaining_bdt": _money(order.remaining_bdt),
        "actual_cost_bdt": _money(order.actual_cost_bdt) if order.actual_cost_bdt is not None else None,
        "promised_delivery_at": order.promised_delivery_at,
        "delivered_at": order.delivered_at,
        "quality_defect_reported": order.quality_defect_reported,
        "quote_snapshot": order.quote_snapshot,
        "items": [
            {
                "id": item.id,
                "variant_id": item.variant_id,
                "offer_id": item.offer_id,
                "product_name": item.product_name,
                "variant_name": item.variant_name,
                "qty": item.qty,
            }
            for item in order.items
        ],
        "payment": {
            "id": payment.id,
            "channel": payment.channel,
            "transaction_id": payment.trx_id,
            "proof_url": payment.screenshot_url,
            "decision": payment.decision,
            "reason": payment.decision_reason,
            "verified": payment.verified,
            "verified_at": payment.verified_at,
            "decided_at": payment.decided_at,
            "verifier": _user_json(verifier) if verifier else None,
            "submitted_at": payment.created_at,
        }
        if payment
        else None,
        "financials": financial_snapshot(session, order),
        "adjustments": [serialize_adjustment(item) for item in _adjustments(session, order.id)],
        "history": [
            {
                "id": item.id,
                "status": item.status,
                "note": item.note,
                "actor_user_id": item.actor_user_id,
                "actor_role": item.actor_role,
                "request_id": item.request_id,
                "created_at": item.created_at,
            }
            for item in sorted(order.history, key=lambda event: (event.created_at, event.id))
        ],
        "shipment": {
            "tracking_number": order.shipment.tracking_number,
            "events": [
                {
                    "id": event.id,
                    "status": event.status,
                    "note": event.note,
                    "created_at": event.created_at,
                }
                for event in order.shipment.events
            ],
        }
        if order.shipment
        else None,
        "created_at": order.created_at,
        "updated_at": order.updated_at,
    }


@router.get("/api/admin/categories/")
def list_categories(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=100),
    q: str = Query(default="", max_length=120),
    active: bool | None = Query(default=None),
    session: Session = Depends(get_session),
    user: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
    require_operator(user)
    statement = select(Category).options(selectinload(Category.products))
    if active is not None:
        statement = statement.where(Category.is_active.is_(active))
    if q.strip():
        pattern = f"%{q.strip()}%"
        statement = statement.where(or_(Category.name.ilike(pattern), Category.slug.ilike(pattern)))
    statement = statement.order_by(Category.name.asc(), Category.id.asc())
    items, total = _paginate(session, statement, page, page_size)
    return _page([_category_json(item) for item in items], total, page, page_size)


@router.post("/api/admin/categories/", status_code=status.HTTP_201_CREATED)
def create_category(
    payload: CategoryCreateIn,
    session: Session = Depends(get_session),
    user: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
    require_admin(user)
    category = Category(name=payload.name.strip(), slug=payload.slug, is_active=True)
    session.add(category)
    session.flush()
    record_admin_audit(
        session,
        user,
        action="category.created",
        entity_type="category",
        entity_id=category.id,
        after={"name": category.name, "slug": category.slug, "is_active": True},
        note="Category created",
    )
    _commit_unique(session, "Category slug already exists")
    session.refresh(category)
    invalidate_admin_analytics()
    return _category_json(category)


@router.get("/api/admin/categories/{category_id}/")
def category_detail(
    category_id: int,
    session: Session = Depends(get_session),
    user: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
    require_operator(user)
    category = _not_found(
        session.scalar(
            select(Category)
            .options(selectinload(Category.products))
            .where(Category.id == category_id)
        ),
        "Category",
    )
    return _category_json(category)


@router.patch("/api/admin/categories/{category_id}/")
def update_category(
    category_id: int,
    payload: CategoryUpdateIn,
    session: Session = Depends(get_session),
    user: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
    require_admin(user)
    category = _not_found(session.get(Category, category_id), "Category")
    before = {"name": category.name, "slug": category.slug}
    for field, value in payload.model_dump(
        exclude_unset=True, exclude={"note", "request_id"}
    ).items():
        setattr(category, field, value.strip() if isinstance(value, str) else value)
    record_admin_audit(
        session,
        user,
        action="category.updated",
        entity_type="category",
        entity_id=category.id,
        before=before,
        after={"name": category.name, "slug": category.slug},
        note=payload.note,
        request_id=payload.request_id,
    )
    _commit_unique(session, "Category slug already exists")
    invalidate_admin_analytics()
    return category_detail(category.id, session, user)


@router.delete("/api/admin/categories/{category_id}/", status_code=status.HTTP_204_NO_CONTENT)
def archive_category(
    category_id: int,
    payload: ArchiveIn,
    session: Session = Depends(get_session),
    user: dict[str, Any] = Depends(get_current_user),
) -> Response:
    require_admin(user)
    category = _not_found(session.get(Category, category_id), "Category")
    _archive(session, category, payload, user, entity_type="category")
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/api/admin/products/{product_id}/")
def product_detail(
    product_id: int,
    session: Session = Depends(get_session),
    user: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
    require_operator(user)
    product = _not_found(
        session.scalar(
            select(Product)
            .options(
                joinedload(Product.category),
                selectinload(Product.variants).selectinload(ProductVariant.offers),
            )
            .where(Product.id == product_id)
        ),
        "Product",
    )
    return _product_json(product)


@router.post("/api/admin/products/", status_code=status.HTTP_201_CREATED)
def create_product(
    payload: ProductCreateIn,
    session: Session = Depends(get_session),
    user: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
    require_admin(user)
    category = _not_found(session.get(Category, payload.category_id), "Category")
    if not category.is_active:
        raise HTTPException(status_code=409, detail="Cannot add a product to an archived category")
    product = Product(**payload.model_dump(), is_active=True)
    session.add(product)
    session.flush()
    record_admin_audit(
        session,
        user,
        action="product.created",
        entity_type="product",
        entity_id=product.id,
        after=payload.model_dump(mode="json"),
        note="Product created",
    )
    _commit_unique(session, "Product slug already exists")
    invalidate_admin_analytics()
    return product_detail(product.id, session, user)


@router.patch("/api/admin/products/{product_id}/")
def update_product(
    product_id: int,
    payload: ProductUpdateIn,
    session: Session = Depends(get_session),
    user: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
    require_admin(user)
    product = _not_found(session.get(Product, product_id), "Product")
    before = {
        "name": product.name,
        "slug": product.slug,
        "category_id": product.category_id,
        "model": product.model,
        "description": product.description,
        "image": product.image,
    }
    values = payload.model_dump(exclude_unset=True, exclude={"note", "request_id"})
    if "category_id" in values:
        category = _not_found(session.get(Category, values["category_id"]), "Category")
        if not category.is_active:
            raise HTTPException(status_code=409, detail="Cannot move a product to an archived category")
    for field, value in values.items():
        setattr(product, field, value.strip() if isinstance(value, str) else value)
    product.updated_at = utc_now()
    record_admin_audit(
        session,
        user,
        action="product.updated",
        entity_type="product",
        entity_id=product.id,
        before=before,
        after=values,
        note=payload.note,
        request_id=payload.request_id,
    )
    _commit_unique(session, "Product slug already exists")
    invalidate_admin_analytics()
    return product_detail(product.id, session, user)


@router.delete("/api/admin/products/{product_id}/", status_code=status.HTTP_204_NO_CONTENT)
def archive_product(
    product_id: int,
    payload: ArchiveIn,
    session: Session = Depends(get_session),
    user: dict[str, Any] = Depends(get_current_user),
) -> Response:
    require_admin(user)
    product = _not_found(session.get(Product, product_id), "Product")
    if not payload.archived and not product.category.is_active:
        raise HTTPException(status_code=409, detail="Restore the parent category first")
    _archive(session, product, payload, user, entity_type="product")
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/api/admin/variants/")
def list_variants(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=100),
    q: str = Query(default="", max_length=120),
    product_id: int | None = Query(default=None, ge=1),
    active: bool | None = Query(default=None),
    session: Session = Depends(get_session),
    user: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
    require_operator(user)
    statement = select(ProductVariant).options(
        joinedload(ProductVariant.product), selectinload(ProductVariant.offers)
    )
    if product_id:
        statement = statement.where(ProductVariant.product_id == product_id)
    if active is not None:
        statement = statement.where(ProductVariant.is_active.is_(active))
    if q.strip():
        pattern = f"%{q.strip()}%"
        statement = statement.where(
            or_(
                ProductVariant.sku.ilike(pattern),
                ProductVariant.variant_name.ilike(pattern),
                ProductVariant.product.has(Product.name.ilike(pattern)),
            )
        )
    statement = statement.order_by(ProductVariant.id.desc())
    items, total = _paginate(session, statement, page, page_size)
    return _page([_variant_json(item) for item in items], total, page, page_size)


@router.post("/api/admin/variants/", status_code=status.HTTP_201_CREATED)
def create_variant(
    payload: VariantCreateIn,
    session: Session = Depends(get_session),
    user: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
    require_admin(user)
    product = _not_found(session.get(Product, payload.product_id), "Product")
    if not product.is_active or not product.category.is_active:
        raise HTTPException(status_code=409, detail="Cannot add a variant to an archived product")
    variant = ProductVariant(**payload.model_dump(), is_active=True)
    session.add(variant)
    session.flush()
    record_admin_audit(
        session,
        user,
        action="variant.created",
        entity_type="product_variant",
        entity_id=variant.id,
        after=payload.model_dump(mode="json"),
        note="Product variant created",
    )
    _commit_unique(session, "Variant could not be created")
    session.refresh(variant)
    invalidate_admin_analytics()
    return _variant_json(variant)


@router.get("/api/admin/variants/{variant_id}/")
def variant_detail(
    variant_id: int,
    session: Session = Depends(get_session),
    user: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
    require_operator(user)
    variant = _not_found(
        session.scalar(
            select(ProductVariant)
            .options(joinedload(ProductVariant.product), selectinload(ProductVariant.offers))
            .where(ProductVariant.id == variant_id)
        ),
        "Variant",
    )
    return _variant_json(variant)


@router.patch("/api/admin/variants/{variant_id}/")
def update_variant(
    variant_id: int,
    payload: VariantUpdateIn,
    session: Session = Depends(get_session),
    user: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
    require_admin(user)
    variant = _not_found(session.get(ProductVariant, variant_id), "Variant")
    before = {
        key: getattr(variant, key)
        for key in ("sku", "variant_name", "weight_kg", "length_cm", "width_cm", "height_cm")
    }
    values = payload.model_dump(exclude_unset=True, exclude={"note", "request_id"})
    for field, value in values.items():
        setattr(variant, field, value.strip() if isinstance(value, str) else value)
    variant.updated_at = utc_now()
    record_admin_audit(
        session,
        user,
        action="variant.updated",
        entity_type="product_variant",
        entity_id=variant.id,
        before=before,
        after=values,
        note=payload.note,
        request_id=payload.request_id,
    )
    session.commit()
    invalidate_admin_analytics()
    return variant_detail(variant.id, session, user)


@router.delete("/api/admin/variants/{variant_id}/", status_code=status.HTTP_204_NO_CONTENT)
def archive_variant(
    variant_id: int,
    payload: ArchiveIn,
    session: Session = Depends(get_session),
    user: dict[str, Any] = Depends(get_current_user),
) -> Response:
    require_admin(user)
    variant = _not_found(session.get(ProductVariant, variant_id), "Variant")
    if not payload.archived and (not variant.product.is_active or not variant.product.category.is_active):
        raise HTTPException(status_code=409, detail="Restore the parent category and product first")
    _archive(session, variant, payload, user, entity_type="product_variant")
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/api/admin/suppliers/", status_code=status.HTTP_201_CREATED)
def create_supplier(
    payload: SupplierCreateIn,
    session: Session = Depends(get_session),
    user: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
    require_admin(user)
    _not_found(session.get(Country, payload.country_id), "Country")
    supplier = Seller(**payload.model_dump(), is_active=True)
    session.add(supplier)
    session.flush()
    record_admin_audit(
        session,
        user,
        action="supplier.created",
        entity_type="supplier",
        entity_id=supplier.id,
        after=payload.model_dump(mode="json"),
        note="Supplier created",
    )
    session.commit()
    invalidate_admin_analytics()
    return supplier_detail(supplier.id, session, user)


@router.get("/api/admin/suppliers/{supplier_id}/")
def supplier_detail(
    supplier_id: int,
    session: Session = Depends(get_session),
    user: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
    require_operator(user)
    supplier = _not_found(
        session.scalar(
            select(Seller)
            .options(joinedload(Seller.country), selectinload(Seller.offers))
            .where(Seller.id == supplier_id)
        ),
        "Supplier",
    )
    return _supplier_json(supplier)


@router.patch("/api/admin/suppliers/{supplier_id}/")
def update_supplier(
    supplier_id: int,
    payload: SupplierUpdateIn,
    session: Session = Depends(get_session),
    user: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
    require_admin(user)
    supplier = _not_found(session.get(Seller, supplier_id), "Supplier")
    before = {
        "country_id": supplier.country_id,
        "name": supplier.name,
        "rating": supplier.rating,
        "note": supplier.note,
    }
    values = payload.model_dump(exclude_unset=True, exclude={"note", "request_id"})
    if "supplier_note" in values:
        values["note"] = values.pop("supplier_note")
    if "country_id" in values:
        _not_found(session.get(Country, values["country_id"]), "Country")
    for field, value in values.items():
        setattr(supplier, field, value.strip() if isinstance(value, str) else value)
    supplier.updated_at = utc_now()
    record_admin_audit(
        session,
        user,
        action="supplier.updated",
        entity_type="supplier",
        entity_id=supplier.id,
        before=before,
        after=values,
        note=payload.note,
        request_id=payload.request_id,
    )
    session.commit()
    invalidate_admin_analytics()
    return supplier_detail(supplier.id, session, user)


@router.delete("/api/admin/suppliers/{supplier_id}/", status_code=status.HTTP_204_NO_CONTENT)
def archive_supplier(
    supplier_id: int,
    payload: ArchiveIn,
    session: Session = Depends(get_session),
    user: dict[str, Any] = Depends(get_current_user),
) -> Response:
    require_admin(user)
    supplier = _not_found(session.get(Seller, supplier_id), "Supplier")
    _archive(session, supplier, payload, user, entity_type="supplier")
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/api/admin/offers/")
def list_offers(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=100),
    q: str = Query(default="", max_length=120),
    supplier_id: int | None = Query(default=None, ge=1),
    variant_id: int | None = Query(default=None, ge=1),
    product_id: int | None = Query(default=None, ge=1),
    country: str | None = Query(default=None, min_length=2, max_length=2),
    mode: str | None = Query(default=None),
    active: bool | None = Query(default=None),
    session: Session = Depends(get_session),
    user: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
    require_operator(user)
    statement = select(SellerOffer).options(
        joinedload(SellerOffer.seller),
        joinedload(SellerOffer.country),
        joinedload(SellerOffer.variant).joinedload(ProductVariant.product),
    )
    if supplier_id:
        statement = statement.where(SellerOffer.seller_id == supplier_id)
    if variant_id:
        statement = statement.where(SellerOffer.variant_id == variant_id)
    if product_id:
        statement = statement.where(SellerOffer.variant.has(ProductVariant.product_id == product_id))
    if country:
        statement = statement.where(SellerOffer.country.has(Country.code == country.upper()))
    if mode:
        if mode not in {"LOCAL", "BULK"}:
            raise HTTPException(status_code=422, detail="Unknown sourcing mode")
        statement = statement.where(SellerOffer.mode == mode)
    if active is not None:
        statement = statement.where(SellerOffer.is_active.is_(active))
    if q.strip():
        pattern = f"%{q.strip()}%"
        statement = statement.where(
            or_(
                cast(SellerOffer.id, String).ilike(pattern),
                SellerOffer.currency.ilike(pattern),
                SellerOffer.seller.has(Seller.name.ilike(pattern)),
                SellerOffer.variant.has(ProductVariant.sku.ilike(pattern)),
                SellerOffer.variant.has(
                    ProductVariant.product.has(Product.name.ilike(pattern))
                ),
            )
        )
    statement = statement.order_by(SellerOffer.updated_at.desc(), SellerOffer.id.desc())
    items, total = _paginate(session, statement, page, page_size)
    return _page([_offer_json(item) for item in items], total, page, page_size)


def _validate_offer_links(
    session: Session,
    *,
    variant_id: int,
    country_id: int,
    seller_id: int,
) -> tuple[ProductVariant, Country, Seller]:
    variant = _not_found(session.get(ProductVariant, variant_id), "Variant")
    country = _not_found(session.get(Country, country_id), "Country")
    supplier = _not_found(session.get(Seller, seller_id), "Supplier")
    if supplier.country_id != country.id:
        raise HTTPException(status_code=409, detail="Offer country must match supplier country")
    if (
        not variant.is_active
        or not variant.product.is_active
        or not variant.product.category.is_active
        or not supplier.is_active
    ):
        raise HTTPException(status_code=409, detail="Offer parents must all be active")
    return variant, country, supplier


@router.post("/api/admin/offers/", status_code=status.HTTP_201_CREATED)
def create_offer(
    payload: OfferCreateIn,
    session: Session = Depends(get_session),
    user: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
    require_admin(user)
    _validate_offer_links(
        session,
        variant_id=payload.variant_id,
        country_id=payload.country_id,
        seller_id=payload.seller_id,
    )
    values = payload.model_dump()
    values["currency"] = payload.currency.upper()
    offer = SellerOffer(**values, is_active=True)
    session.add(offer)
    session.flush()
    record_admin_audit(
        session,
        user,
        action="offer.created",
        entity_type="seller_offer",
        entity_id=offer.id,
        after=payload.model_dump(mode="json"),
        note="Supplier offer created",
    )
    session.commit()
    invalidate_admin_analytics()
    return offer_detail(offer.id, session, user)


@router.get("/api/admin/offers/{offer_id}/")
def offer_detail(
    offer_id: int,
    session: Session = Depends(get_session),
    user: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
    require_operator(user)
    offer = _not_found(
        session.scalar(
            select(SellerOffer)
            .options(
                joinedload(SellerOffer.seller),
                joinedload(SellerOffer.country),
                joinedload(SellerOffer.variant).joinedload(ProductVariant.product),
            )
            .where(SellerOffer.id == offer_id)
        ),
        "Offer",
    )
    return _offer_json(offer)


@router.patch("/api/admin/offers/{offer_id}/")
def update_offer(
    offer_id: int,
    payload: OfferUpdateIn,
    session: Session = Depends(get_session),
    user: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
    require_admin(user)
    offer = _not_found(session.get(SellerOffer, offer_id), "Offer")
    before = {
        key: getattr(offer, key)
        for key in (
            "variant_id",
            "country_id",
            "seller_id",
            "mode",
            "price_origin",
            "currency",
            "stock",
            "moq",
            "source_url",
        )
    }
    values = payload.model_dump(exclude_unset=True, exclude={"note", "request_id"})
    variant_id = int(values.get("variant_id", offer.variant_id))
    country_id = int(values.get("country_id", offer.country_id))
    seller_id = int(values.get("seller_id", offer.seller_id))
    _validate_offer_links(
        session,
        variant_id=variant_id,
        country_id=country_id,
        seller_id=seller_id,
    )
    if "currency" in values and values["currency"]:
        values["currency"] = values["currency"].upper()
    for field, value in values.items():
        setattr(offer, field, value.strip() if isinstance(value, str) else value)
    offer.updated_at = utc_now()
    record_admin_audit(
        session,
        user,
        action="offer.updated",
        entity_type="seller_offer",
        entity_id=offer.id,
        before=before,
        after=values,
        note=payload.note,
        request_id=payload.request_id,
    )
    session.commit()
    invalidate_admin_analytics()
    return offer_detail(offer.id, session, user)


@router.delete("/api/admin/offers/{offer_id}/", status_code=status.HTTP_204_NO_CONTENT)
def archive_offer(
    offer_id: int,
    payload: ArchiveIn,
    session: Session = Depends(get_session),
    user: dict[str, Any] = Depends(get_current_user),
) -> Response:
    require_admin(user)
    offer = _not_found(session.get(SellerOffer, offer_id), "Offer")
    if not payload.archived:
        _validate_offer_links(
            session,
            variant_id=offer.variant_id,
            country_id=offer.country_id,
            seller_id=offer.seller_id,
        )
    _archive(session, offer, payload, user, entity_type="seller_offer")
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/api/admin/catalog/{entity_type}/bulk-archive/")
def bulk_archive_catalog(
    entity_type: str,
    payload: BulkArchiveIn,
    session: Session = Depends(get_session),
    user: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
    require_admin(user)
    entity_map = {
        "categories": (Category, "category"),
        "products": (Product, "product"),
        "variants": (ProductVariant, "product_variant"),
        "suppliers": (Seller, "supplier"),
        "offers": (SellerOffer, "seller_offer"),
    }
    if entity_type not in entity_map:
        raise HTTPException(status_code=404, detail="Unknown catalog entity")
    model, audit_type = entity_map[entity_type]
    records = session.scalars(select(model).where(model.id.in_(set(payload.ids)))).all()
    found = {record.id for record in records}
    missing = sorted(set(payload.ids) - found)
    if missing:
        raise HTTPException(status_code=404, detail={"message": "Some records were not found", "ids": missing})
    now = utc_now()
    for record in records:
        if not payload.archived:
            if isinstance(record, Product) and not record.category.is_active:
                raise HTTPException(status_code=409, detail="Restore parent categories first")
            if isinstance(record, ProductVariant) and (
                not record.product.is_active or not record.product.category.is_active
            ):
                raise HTTPException(status_code=409, detail="Restore parent products and categories first")
            if isinstance(record, SellerOffer):
                _validate_offer_links(
                    session,
                    variant_id=record.variant_id,
                    country_id=record.country_id,
                    seller_id=record.seller_id,
                )
        before = {"is_active": record.is_active, "archived_at": record.archived_at}
        record.is_active = not payload.archived
        record.archived_at = now if payload.archived else None
        record.archived_by_user_id = int(user["sub"]) if payload.archived else None
        if hasattr(record, "updated_at"):
            record.updated_at = now
        record_admin_audit(
            session,
            user,
            action=f"{audit_type}.{'archived' if payload.archived else 'restored'}",
            entity_type=audit_type,
            entity_id=record.id,
            before=before,
            after={"is_active": record.is_active, "archived_at": record.archived_at},
            note=payload.note,
            request_id=payload.request_id,
        )
    session.commit()
    invalidate_admin_analytics()
    return {
        "entity_type": entity_type,
        "updated": len(records),
        "ids": sorted(found),
        "archived": payload.archived,
    }


@router.get("/api/admin/users/{user_id}/")
def user_detail(
    user_id: int,
    session: Session = Depends(get_session),
    user: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
    require_admin(user)
    account = _not_found(session.get(AccountUser, user_id), "User")
    order_summary = session.execute(
        select(func.count(Order.id), func.coalesce(func.sum(Order.total_bdt), 0)).where(
            Order.user_id == account.id, Order.status != "CANCELLED"
        )
    ).one()
    quote_count = int(
        session.scalar(select(func.count(SavedQuote.id)).where(SavedQuote.user_id == account.id))
        or 0
    )
    return {
        **_user_json(account),
        "orders": int(order_summary[0] or 0),
        "lifetime_order_value_bdt": _money(order_summary[1]),
        "saved_quotes": quote_count,
    }


@router.patch("/api/admin/users/{user_id}/")
def update_user(
    user_id: int,
    payload: UserAdminUpdateIn,
    session: Session = Depends(get_session),
    user: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
    require_admin(user)
    account = _not_found(session.get(AccountUser, user_id), "User")
    actor_id = int(user["sub"])
    if account.id == actor_id and (
        payload.is_active is False or (payload.role is not None and payload.role != "admin")
    ):
        raise HTTPException(status_code=409, detail="Administrators cannot demote or deactivate themselves")
    removes_admin = account.role == "admin" and (
        payload.is_active is False or (payload.role is not None and payload.role != "admin")
    )
    if removes_admin:
        active_admins = int(
            session.scalar(
                select(func.count(AccountUser.id)).where(
                    AccountUser.role == "admin", AccountUser.is_active.is_(True)
                )
            )
            or 0
        )
        if active_admins <= 1:
            raise HTTPException(status_code=409, detail="The last active administrator cannot be removed")
    before = {"role": account.role, "is_active": account.is_active}
    if payload.role is not None:
        account.role = payload.role
        account.is_staff = payload.role in {"admin", "operator"}
        account.is_superuser = payload.role == "admin"
    if payload.is_active is not None:
        account.is_active = payload.is_active
    account.auth_version = int(account.auth_version or 1) + 1
    now = utc_now()
    active_sessions = session.scalars(
        select(RefreshSession).where(
            RefreshSession.user_id == account.id,
            RefreshSession.revoked_at.is_(None),
        )
    ).all()
    for auth_session in active_sessions:
        auth_session.revoked_at = now
        auth_session.revoke_reason = "admin_access_change"
    record_admin_audit(
        session,
        user,
        action="user.access_updated",
        entity_type="user",
        entity_id=account.id,
        before=before,
        after={
            "role": account.role,
            "is_active": account.is_active,
            "auth_version": account.auth_version,
            "revoked_sessions": len(active_sessions),
        },
        note=payload.note,
        request_id=payload.request_id,
    )
    session.commit()
    return user_detail(account.id, session, user)


@router.get("/api/admin/roles/")
def list_roles(
    session: Session = Depends(get_session),
    user: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
    require_admin(user)
    counts = {
        role: int(count)
        for role, count in session.execute(
            select(AccountUser.role, func.count(AccountUser.id)).group_by(AccountUser.role)
        ).all()
    }
    return {
        "items": [
            {
                "role": role,
                "capabilities": capabilities,
                "users": counts.get(role, 0),
                "system_managed": True,
            }
            for role, capabilities in ROLE_CAPABILITIES.items()
        ],
        "policy": (
            "Roles are system-managed and deny by default. User role assignment is audited "
            "through PATCH /api/admin/users/{id}/."
        ),
    }


@router.get("/api/admin/orders/{order_id}/")
def admin_order_detail(
    order_id: int,
    session: Session = Depends(get_session),
    user: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
    require_operator(user)
    order = get_order_or_404(session, order_id, user)
    return _admin_order_json(session, order)


@router.get("/api/admin/payments/{payment_id}/")
def admin_payment_detail(
    payment_id: int,
    session: Session = Depends(get_session),
    user: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
    require_operator(user)
    payment = _not_found(session.get(ManualPaymentProof, payment_id), "Payment proof")
    order = get_order_or_404(session, payment.order_id, user)
    return {
        "payment": _admin_order_json(session, order)["payment"],
        "order": _admin_order_json(session, order),
    }


@router.get("/api/admin/quotes/{quote_id}/")
def admin_quote_detail(
    quote_id: int,
    session: Session = Depends(get_session),
    user: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
    require_operator(user)
    quote = _not_found(
        session.scalar(
            select(SavedQuote)
            .options(selectinload(SavedQuote.orders), joinedload(SavedQuote.ai_explanation))
            .where(SavedQuote.id == quote_id)
        ),
        "Saved quote",
    )
    customer = session.get(AccountUser, quote.user_id)
    return {
        "id": quote.id,
        "customer": _user_json(customer) if customer else {"id": quote.user_id},
        "variant_id": quote.variant_id,
        "product_name": quote.product_name,
        "variant_name": quote.variant_name,
        "country": quote.country_code,
        "mode": quote.mode,
        "delivery_type": quote.delivery_type,
        "qty": quote.qty,
        "status": quote.status,
        "expires_at": quote.expires_at,
        "snapshot": quote.response,
        "order_ids": [order.id for order in quote.orders],
        "created_at": quote.created_at,
        "updated_at": quote.updated_at,
        "ai_review": _ai_review_json(quote.ai_explanation) if quote.ai_explanation else None,
    }


@router.patch("/api/admin/orders/{order_id}/settlement/")
def update_order_settlement(
    order_id: int,
    payload: OrderSettlementIn,
    session: Session = Depends(get_session),
    user: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
    require_operator(user)
    order = get_order_or_404(session, order_id, user)
    if payload.delivered_at is not None and order.status != "DELIVERED":
        raise HTTPException(status_code=409, detail="Only a delivered order can receive delivered_at")
    before = {
        "actual_cost_bdt": order.actual_cost_bdt,
        "promised_delivery_at": order.promised_delivery_at,
        "delivered_at": order.delivered_at,
        "quality_defect_reported": order.quality_defect_reported,
    }
    values = payload.model_dump(exclude_unset=True, exclude={"note", "request_id"})
    for field, value in values.items():
        setattr(order, field, value)
    order.updated_at = utc_now()
    record_admin_audit(
        session,
        user,
        action="order.settlement_updated",
        entity_type="order",
        entity_id=order.id,
        before=before,
        after=values,
        note=payload.note,
        request_id=payload.request_id,
    )
    session.commit()
    session.refresh(order)
    invalidate_admin_analytics()
    return _admin_order_json(session, order)


@router.post("/api/admin/payments/{payment_id}/reverse/")
def reverse_payment_endpoint(
    payment_id: int,
    payload: PaymentReversalIn,
    session: Session = Depends(get_session),
    user: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
    order, reversal = reverse_payment(session, payment_id, payload, user)
    return {
        "order": _admin_order_json(session, order),
        "reversal": serialize_adjustment(reversal),
    }


@router.post("/api/admin/orders/{order_id}/refunds/", status_code=status.HTTP_201_CREATED)
def create_refund_endpoint(
    order_id: int,
    payload: RefundCreateIn,
    session: Session = Depends(get_session),
    user: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
    adjustment = create_refund(session, order_id, payload, user)
    order = get_order_or_404(session, order_id, user)
    return {
        "refund": serialize_adjustment(adjustment),
        "financials": financial_snapshot(session, order),
    }


@router.post("/api/admin/refunds/{refund_id}/reverse/")
def reverse_refund_endpoint(
    refund_id: int,
    payload: RefundReverseIn,
    session: Session = Depends(get_session),
    user: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
    adjustment = reverse_refund(session, refund_id, payload, user)
    order = get_order_or_404(session, adjustment.order_id, user)
    return {
        "refund": serialize_adjustment(adjustment),
        "financials": financial_snapshot(session, order),
    }


def _setting_rows(session: Session, model: Any) -> list[Any]:
    return session.scalars(select(model).order_by(model.id.asc())).all()


def _setting_json(item: Any) -> dict[str, Any]:
    if isinstance(item, CurrencyRate):
        return {
            "id": item.id,
            "currency": item.currency,
            "rate_to_bdt": format(item.rate_to_bdt, ".4f"),
            "is_active": item.is_active,
            "updated_at": item.updated_at,
        }
    if isinstance(item, ServiceFeeRule):
        return {
            "id": item.id,
            "mode": item.mode,
            "fee_bdt": _money(item.fee_bdt),
            "percent": _money(item.percent),
            "is_active": item.is_active,
            "updated_at": item.updated_at,
        }
    if isinstance(item, ShippingRateCard):
        return {
            "id": item.id,
            "country_id": item.country_id,
            "country": item.country.code,
            "method": item.method,
            "min_kg": format(item.min_kg, ".3f"),
            "max_kg": format(item.max_kg, ".3f"),
            "cost_bdt": _money(item.cost_bdt),
            "is_active": item.is_active,
            "updated_at": item.updated_at,
        }
    if isinstance(item, ETARule):
        return {
            "id": item.id,
            "country_id": item.country_id,
            "country": item.country.code,
            "mode": item.mode,
            "delivery_type": item.delivery_type,
            "min_days": item.min_days,
            "max_days": item.max_days,
            "is_active": item.is_active,
            "updated_at": item.updated_at,
        }
    if isinstance(item, DutyRule):
        return {
            "id": item.id,
            "country_id": item.country_id,
            "country": item.country.code,
            "category_id": item.category_id,
            "category": item.category.name if item.category else None,
            "percent": _money(item.percent),
            "fixed_bdt": _money(item.fixed_bdt),
            "effective_from": item.effective_from,
            "effective_to": item.effective_to,
            "is_active": item.is_active,
            "updated_at": item.updated_at,
        }
    raise TypeError(f"Unsupported setting type {type(item)!r}")


def _setting_type(setting_type: str) -> tuple[Any, str]:
    setting_map = {
        "currencies": (CurrencyRate, "currency_rate"),
        "service-fees": (ServiceFeeRule, "service_fee_rule"),
        "shipping-rates": (ShippingRateCard, "shipping_rate"),
        "eta-rules": (ETARule, "eta_rule"),
        "duty-rules": (DutyRule, "duty_rule"),
    }
    if setting_type not in setting_map:
        raise HTTPException(status_code=404, detail="Unknown setting type")
    return setting_map[setting_type]


@router.get("/api/admin/settings/")
def settings_summary(
    session: Session = Depends(get_session),
    user: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
    require_admin(user)
    return {
        "currencies": [_setting_json(item) for item in _setting_rows(session, CurrencyRate)],
        "service_fees": [_setting_json(item) for item in _setting_rows(session, ServiceFeeRule)],
        "shipping_rates": [_setting_json(item) for item in _setting_rows(session, ShippingRateCard)],
        "eta_rules": [_setting_json(item) for item in _setting_rows(session, ETARule)],
        "duty_rules": [_setting_json(item) for item in _setting_rows(session, DutyRule)],
    }


@router.get("/api/admin/settings/{setting_type}/{record_id}/")
def setting_detail(
    setting_type: str,
    record_id: int,
    session: Session = Depends(get_session),
    user: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
    require_admin(user)
    model, _ = _setting_type(setting_type)
    return _setting_json(_not_found(session.get(model, record_id), "Setting"))


def _upsert_setting(
    session: Session,
    user: dict[str, Any],
    *,
    model: Any,
    record_id: int | None,
    values: dict[str, Any],
    entity_type: str,
    note: str,
    request_id: str | None,
) -> Any:
    item = session.get(model, record_id) if record_id else None
    if record_id and not item:
        raise HTTPException(status_code=404, detail=f"{entity_type.replace('_', ' ').title()} not found")
    before = None
    action = f"{entity_type}.created"
    if item:
        before = {key: getattr(item, key) for key in values}
        action = f"{entity_type}.updated"
    else:
        item = model()
        session.add(item)
    for field, value in values.items():
        setattr(item, field, value)
    item.is_active = True
    item.updated_at = utc_now()
    session.flush()
    record_admin_audit(
        session,
        user,
        action=action,
        entity_type=entity_type,
        entity_id=item.id,
        before=before,
        after=values,
        note=note,
        request_id=request_id,
    )
    _commit_unique(session, f"Conflicting {entity_type.replace('_', ' ')}")
    session.refresh(item)
    invalidate_admin_analytics()
    return item


@router.put("/api/admin/settings/currencies/{record_id}/")
def put_currency(
    record_id: int,
    payload: CurrencyRateIn,
    session: Session = Depends(get_session),
    user: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
    require_admin(user)
    item = _upsert_setting(
        session,
        user,
        model=CurrencyRate,
        record_id=record_id,
        values={"currency": payload.currency.upper(), "rate_to_bdt": payload.rate_to_bdt},
        entity_type="currency_rate",
        note=payload.note,
        request_id=payload.request_id,
    )
    return _setting_json(item)


@router.post("/api/admin/settings/currencies/", status_code=status.HTTP_201_CREATED)
def create_currency(
    payload: CurrencyRateIn,
    session: Session = Depends(get_session),
    user: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
    require_admin(user)
    item = _upsert_setting(
        session,
        user,
        model=CurrencyRate,
        record_id=None,
        values={"currency": payload.currency.upper(), "rate_to_bdt": payload.rate_to_bdt},
        entity_type="currency_rate",
        note=payload.note,
        request_id=payload.request_id,
    )
    return _setting_json(item)


@router.put("/api/admin/settings/service-fees/{record_id}/")
def put_service_fee(
    record_id: int,
    payload: ServiceFeeRuleIn,
    session: Session = Depends(get_session),
    user: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
    require_admin(user)
    return _setting_json(
        _upsert_setting(
            session,
            user,
            model=ServiceFeeRule,
            record_id=record_id,
            values={
                "mode": payload.mode,
                "fee_bdt": payload.fee_bdt,
                "percent": payload.percent,
            },
            entity_type="service_fee_rule",
            note=payload.note,
            request_id=payload.request_id,
        )
    )


@router.post("/api/admin/settings/service-fees/", status_code=status.HTTP_201_CREATED)
def create_service_fee(
    payload: ServiceFeeRuleIn,
    session: Session = Depends(get_session),
    user: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
    require_admin(user)
    return _setting_json(
        _upsert_setting(
            session,
            user,
            model=ServiceFeeRule,
            record_id=None,
            values={
                "mode": payload.mode,
                "fee_bdt": payload.fee_bdt,
                "percent": payload.percent,
            },
            entity_type="service_fee_rule",
            note=payload.note,
            request_id=payload.request_id,
        )
    )


@router.put("/api/admin/settings/shipping-rates/{record_id}/")
def put_shipping_rate(
    record_id: int,
    payload: ShippingRateCardIn,
    session: Session = Depends(get_session),
    user: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
    require_admin(user)
    _not_found(session.get(Country, payload.country_id), "Country")
    return _setting_json(
        _upsert_setting(
            session,
            user,
            model=ShippingRateCard,
            record_id=record_id,
            values=payload.model_dump(exclude={"note", "request_id"}),
            entity_type="shipping_rate",
            note=payload.note,
            request_id=payload.request_id,
        )
    )


@router.post("/api/admin/settings/shipping-rates/", status_code=status.HTTP_201_CREATED)
def create_shipping_rate(
    payload: ShippingRateCardIn,
    session: Session = Depends(get_session),
    user: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
    require_admin(user)
    _not_found(session.get(Country, payload.country_id), "Country")
    return _setting_json(
        _upsert_setting(
            session,
            user,
            model=ShippingRateCard,
            record_id=None,
            values=payload.model_dump(exclude={"note", "request_id"}),
            entity_type="shipping_rate",
            note=payload.note,
            request_id=payload.request_id,
        )
    )


@router.put("/api/admin/settings/eta-rules/{record_id}/")
def put_eta_rule(
    record_id: int,
    payload: ETARuleIn,
    session: Session = Depends(get_session),
    user: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
    require_admin(user)
    _not_found(session.get(Country, payload.country_id), "Country")
    return _setting_json(
        _upsert_setting(
            session,
            user,
            model=ETARule,
            record_id=record_id,
            values=payload.model_dump(exclude={"note", "request_id"}),
            entity_type="eta_rule",
            note=payload.note,
            request_id=payload.request_id,
        )
    )


@router.post("/api/admin/settings/eta-rules/", status_code=status.HTTP_201_CREATED)
def create_eta_rule(
    payload: ETARuleIn,
    session: Session = Depends(get_session),
    user: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
    require_admin(user)
    _not_found(session.get(Country, payload.country_id), "Country")
    return _setting_json(
        _upsert_setting(
            session,
            user,
            model=ETARule,
            record_id=None,
            values=payload.model_dump(exclude={"note", "request_id"}),
            entity_type="eta_rule",
            note=payload.note,
            request_id=payload.request_id,
        )
    )


@router.put("/api/admin/settings/duty-rules/{record_id}/")
def put_duty_rule(
    record_id: int,
    payload: DutyRuleIn,
    session: Session = Depends(get_session),
    user: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
    require_admin(user)
    _not_found(session.get(Country, payload.country_id), "Country")
    if payload.category_id:
        _not_found(session.get(Category, payload.category_id), "Category")
    return _setting_json(
        _upsert_setting(
            session,
            user,
            model=DutyRule,
            record_id=record_id,
            values=payload.model_dump(exclude={"note", "request_id"}),
            entity_type="duty_rule",
            note=payload.note,
            request_id=payload.request_id,
        )
    )


@router.post("/api/admin/settings/duty-rules/", status_code=status.HTTP_201_CREATED)
def create_duty_rule(
    payload: DutyRuleIn,
    session: Session = Depends(get_session),
    user: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
    require_admin(user)
    _not_found(session.get(Country, payload.country_id), "Country")
    if payload.category_id:
        _not_found(session.get(Category, payload.category_id), "Category")
    return _setting_json(
        _upsert_setting(
            session,
            user,
            model=DutyRule,
            record_id=None,
            values=payload.model_dump(exclude={"note", "request_id"}),
            entity_type="duty_rule",
            note=payload.note,
            request_id=payload.request_id,
        )
    )


@router.delete("/api/admin/settings/{setting_type}/{record_id}/", status_code=status.HTTP_204_NO_CONTENT)
def archive_setting(
    setting_type: str,
    record_id: int,
    payload: ArchiveIn,
    session: Session = Depends(get_session),
    user: dict[str, Any] = Depends(get_current_user),
) -> Response:
    require_admin(user)
    model, entity_type = _setting_type(setting_type)
    item = _not_found(session.get(model, record_id), "Setting")
    _archive(session, item, payload, user, entity_type=entity_type)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
