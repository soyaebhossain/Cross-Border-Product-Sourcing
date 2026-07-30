# SourceAI dashboard metric contract

This contract keeps the admin overview, research analytics, exports, and
operational work queues aligned. All timestamps are stored in UTC. Reader-facing
dates default to `Asia/Dhaka` and can be changed by the viewer.

## Audience and access

- `admin`: full overview, finance, catalog, supplier, user, configuration, and
  audit access.
- `operator`: operational orders, payments, quotes, suppliers, and non-sensitive
  overview metrics. User administration and security settings remain admin-only.
- `customer`: only records owned by the authenticated customer.
- anonymous: public catalog only. No quote-, order-, payment-, user-, or
  supplier-level analytics.

## Global filters

- `from` and `to` are an inclusive local-date reporting window converted to UTC
  before querying.
- `days` is a convenience preset used only when `from` and `to` are absent.
- Country, delivery mode, and order status filters apply to charts and tables
  that use the order grain.
- Point-in-time cards explicitly say `as of` and do not pretend to be
  window-scoped.

## Hero metrics

### Gross order value

Sum of `orders_orders.total_bdt` for non-cancelled orders whose `created_at`
falls inside the selected reporting window.

Grain: one order. Unit: BDT. Excludes cancelled orders. This is booked order
value, not recognized revenue or cash received.

### Verified advance

Sum of `orders_orders.advance_bdt` for non-cancelled orders whose payment proof
was approved and whose `orders_manual_payments.verified_at` falls inside the
selected reporting window.

Grain: one approved payment per order. Unit: BDT. The trend date is payment
verification date, not order creation date.

### Outstanding balance

Sum of `orders_orders.remaining_bdt` for orders currently in an active state:
`CONFIRMED`, `PURCHASED`, `IN_TRANSIT`, `CUSTOMS`, or `LOCAL_DISPATCH`.

Grain: one active order. Unit: BDT. This is a point-in-time balance and must show
an `as of` timestamp.

### Active orders

Distinct orders currently in `PENDING`, `CONFIRMED`, `PURCHASED`, `IN_TRANSIT`,
`CUSTOMS`, or `LOCAL_DISPATCH`. Cancelled and delivered orders are excluded.

Grain: one order. Unit: count. This is a point-in-time workload measure.

### Quote-to-order conversion

Distinct eligible saved quotes linked to at least one non-cancelled order,
divided by distinct eligible saved quotes created in the selected window.

An eligible quote is owned by a customer, has a valid immutable pricing
snapshot, and was not already expired when converted. An order must carry
`saved_quote_id`; unlinked legacy orders are reported separately and never
included in the numerator.

Grain: one saved quote. Unit: percentage. The numerator cannot exceed the
denominator.

## Diagnostic metrics

- Orders by stage: distinct current orders by the canonical state machine.
- Payment decisions: pending, approved, and rejected proofs by decision time.
- Delivery mix: distinct non-cancelled orders and ordered units by delivery type.
- Top products: summed order-item quantity for non-cancelled orders in the
  selected window.
- Top sourcing countries: distinct non-cancelled orders by origin country in the
  selected window.
- Supplier risk: one supplier using the shared risk thresholds and the latest
  available rating/quality inputs. Risk labels must not differ between admin and
  research views.

## Comparison rules

- A selected window is compared with the immediately preceding window of the
  same duration.
- Percentage delta is omitted when the comparison value is zero; the UI shows
  `New` or `No prior activity` instead.
- Point-in-time cards compare current snapshots only when a historical snapshot
  exists. They must not derive a false comparison from event rows.

## Data-quality invariants

- Product slug and non-null SKU values are unique after case/whitespace
  normalization.
- Every product variant belongs to a product.
- Every seller offer belongs to an existing variant, seller, and country.
- Offer price and stock are non-negative; MOQ is at least one.
- Payment transaction identifiers are normalized and unique per payment
  provider.
- An approved payment has `verified_at` and `verified_by`; a rejected payment
  has a rejection reason.
- Order status history is append-only and records actor, previous status, new
  status, timestamp, and request/correlation identifier.
- Order transitions follow the canonical state machine and cannot move backward
  without an explicit privileged correction event.
- Customer exports are owner-scoped; global analytical exports require an
  authorized admin or operator.

## Freshness and reconciliation

- The overview response includes `generated_at`, selected timezone, applied
  filters, and metric definitions/version.
- Hero cards reconcile to their associated trend and detail endpoints for the
  same filter set.
- Empty periods return zero-valued buckets so charts do not visually skip dates.
- Automated tests cover allowed status values, transition rules, uniqueness,
  ownership, filter windows, and card-to-detail reconciliation.
