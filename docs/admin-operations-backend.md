# Admin operations backend

The admin API is role-gated: catalog, settings, user access, and bulk archive
mutations require `admin`; payment, order, quote, fulfilment, and analytics
operations allow `admin` or `operator`. Customers cannot call any endpoint in
this document.

## Financial integrity

- Manual payment transaction IDs are normalized and unique per channel.
- `POST /api/admin/payments/{payment_id}/reverse/` reverses approval only before
  supplier purchase. Purchased or fulfilled orders must use a refund.
- `POST /api/admin/orders/{order_id}/refunds/` posts a refund against verified
  cash and rejects over-refunds.
- `POST /api/admin/refunds/{refund_id}/reverse/` reverses a posted refund
  without deleting the original ledger record.
- Every refund and reversal has a unique transaction reference, actor, time,
  reason, before/after audit snapshot, and request/correlation ID.
- The order detail response recomputes gross collected, posted refunds, net
  verified cash, and outstanding balance from the ledger.

## Catalog and configuration

Categories, products, variants, suppliers, and offers use soft archive. Public
catalog, quote, and recommendation queries exclude an archived record and any
record whose parent is archived. Restoring a child before its parent is
rejected. Seed jobs never set an existing record back to active.

Configuration endpoints manage currency rates, service fees, shipping rate
cards, ETA rules, and category/country duty rules. Archived configuration is
excluded from quote calculation.

## Analytics

`GET /api/admin/analytics/overview/` accepts `days`, `date_from`, `date_to`,
`timezone`, `status`, `country`, and `mode`. It returns:

- booked order value, verified cash, outstanding, refunds, shipping, and
  realized margin;
- prior-period comparison;
- zero-filled daily financial buckets;
- quote-to-order-to-delivered funnel;
- delivery duration and late/overdue counts;
- supplier defect, SLA, and reliability outcomes;
- country profitability preview;
- metric definitions, data coverage, selected timezone, generated time, and
  data freshness.

Paginated drill-down endpoints:

- `GET /api/admin/analytics/suppliers/`
- `GET /api/admin/analytics/profitability/?dimension=country|category|product`
- `GET /api/admin/analytics/delays/`

Profit and margin are `null`/empty when actual-cost settlement is unavailable;
the API does not substitute quoted cost. Category and product profitability
allocate order totals by item quantity, preventing duplicated order value on
multi-item joins.

Aggregates execute in SQL. The overview uses a bounded 30-second process-local
TTL cache and invalidates it after quote, order, payment, refund, settlement,
catalog, or settings writes. A multi-worker deployment should replace this
adapter with Redis or another shared cache; the short TTL is only a safety net,
not cross-process invalidation.

## Database rollout

Alembic revision `20260730_03` follows identity-security revision
`20260730_02`. It is additive and non-destructive. It creates refund/adjustment
and duty-rule tables, archive fields, fulfilment outcome fields, audit
attribution fields, and supporting indexes. If a legacy database already has
duplicate `saved_quote_id` links, the migration preserves the rows and skips
the physical unique index; operators must reconcile those historical
duplicates before adding the constraint.
