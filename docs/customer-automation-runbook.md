# Customer automation and notification runbook

## Scope

Alembic revision `20260730_04` adds customer-owned profiles, company and
locale preferences, address books, immutable invoice snapshots, persistent
notification preferences, an in-app notification/outbox system, support
tickets/messages, disputes, and append-only manual-payment attempts and
decision events.

The account APIs accept only users whose current database role is `customer`.
Administrator and operator sessions receive `403` rather than being routed
through customer screens. Administrative support/dispute operations require
`admin` or `operator`; provider dispatch and failed-delivery requeue require
the `admin` role. Every privileged ticket/dispute/outbox mutation writes an
`admin_audit_events` row using the current request ID.

Revision 04 also converts the obsolete account role `seller` to an
unprivileged `customer`, clears staff/superuser flags, and increments
`auth_version` so existing sessions are revoked. Supplier companies remain
normal `sourcing_sellers` records and are not changed.

## Customer API

All responses under `/api/account/` include `Cache-Control: no-store`.

- `GET|PATCH /api/account/profile/`
- `GET|POST /api/account/addresses/`
- `GET|PATCH|DELETE /api/account/addresses/{address_id}/`
- `GET /api/account/invoices/`
- `GET /api/account/invoices/{order_id}/`
- `GET /api/account/invoices/{order_id}/pdf/`
- `GET /api/account/invoices/{order_id}/download/`
- `GET|PATCH /api/account/notification-preferences/`
- `GET /api/account/notifications/`
- `POST /api/account/notifications/{notification_id}/read/`
- `POST /api/account/notifications/read-all/`
- `GET|POST /api/account/support-tickets/`
- `GET /api/account/support-tickets/{ticket_id}/`
- `POST /api/account/support-tickets/{ticket_id}/messages/`
- `GET|POST /api/account/disputes/`
- `GET /api/account/disputes/{dispute_id}/`
- `POST /api/account/disputes/{dispute_id}/cancel/`
- `GET /api/account/orders/{order_id}/payment-attempts/`
- `POST /api/account/orders/{order_id}/payment-retry/`

Invoice rows use a persisted snapshot of the customer/company, selected
default addresses, item descriptions, quantities, and monetary totals at
issue time. Later profile/address/order edits do not rewrite that snapshot.
Verified-cash, refund, outstanding, and payment status fields remain live
financial state so the invoice detail reflects later settlements.

The `/pdf/` endpoint returns a valid minimal `%PDF-1.4` document with an
honest `application/pdf` content type. Its built-in Helvetica font is intended
for Latin text. The `/download/` endpoint is the Unicode-safe Bangla/English
printable invoice: it returns UTF-8 HTML with an honest
`text/html; charset=utf-8` content type and can be printed to PDF by a browser
with a Bengali-capable system font. A future server-rendered Bengali PDF
requires an explicitly licensed embedded Bengali font.

## Customer web surfaces

The Next.js account area is wired to the authenticated APIs above:

- `/account/profile` — person/company preferences and shipping/billing address
  book;
- `/account/invoices` — paginated invoice list/detail, Latin PDF, and
  Unicode-safe printable Bangla/English invoice;
- `/account/notifications` — channel preferences, inbox/unread filtering,
  mark-one/all-read, and real delivery states;
- `/account/support` — ticket creation, filtering, conversation replies,
  dispute creation/detail, and customer cancellation with a mandatory reason;
- `/account/orders/{id}` — immutable payment-attempt/decision history and
  eligible payment-proof retry.

The payment retry control appears only while the owned order is `PENDING` and
the current proof is `REJECTED` or `REVERSED`. UI visibility is not the
security boundary; the API repeats ownership, state, transaction, and proof
host validation.

Payment proof URLs must use HTTPS. In production,
`CATALOG_PAYMENT_PROOF_ALLOWED_HOSTS` is mandatory and must be a
comma-separated exact allowlist of object-storage hostnames. New retries are
accepted only while an owned order is `PENDING` and its current proof is
`REJECTED` or `REVERSED`. Each submission is immutable in
`orders_payment_proof_attempts`; approval/rejection/reversal is appended to
`orders_payment_proof_decisions`.

## Operations API

- `GET /api/admin/support-tickets/?q=&status=&limit=&offset=`
- `GET /api/admin/support-tickets/{ticket_id}/`
- `POST /api/admin/support-tickets/{ticket_id}/messages/`
- `PATCH /api/admin/support-tickets/{ticket_id}/status/`
- `GET /api/admin/disputes/?q=&status=&limit=&offset=`
- `GET /api/admin/disputes/{dispute_id}/`
- `PATCH /api/admin/disputes/{dispute_id}/`
- `GET /api/admin/notifications/outbox/?status=&channel=&limit=&offset=`
- `GET /api/admin/notifications/outbox/{outbox_id}/`
- `POST /api/admin/notifications/outbox/{outbox_id}/requeue/` (admin only)
- `POST /api/admin/notifications/outbox/dispatch/?limit=1` (admin only)

The synchronous dispatch endpoint is deliberately capped at one message for
diagnostics. Normal delivery must use the separate worker.

The corresponding control-center routes are `/admin/support`,
`/admin/disputes`, and `/admin/notifications`, each with a dedicated record
detail route. Operators can handle tickets/disputes and monitor the outbox;
only administrators can dispatch or requeue provider deliveries.

## Notification worker

Order creation, payment approval/rejection/reversal, refunds, order
status/tracking changes, support replies/status changes, and dispute changes
create an in-app notification and enqueue enabled external channels.
Unconfigured providers never report fake success: delivery remains `QUEUED`
until a worker claims it, then becomes `FAILED` with
`provider_not_configured`, or `SENT` after the real provider succeeds.

Run one batch:

```shell
python -m scripts.dispatch_notifications --once
```

Run continuously:

```shell
python -m scripts.dispatch_notifications --poll-seconds 10
```

Docker Compose includes a continuously running `notification-worker` service.
For another deployment platform, run one worker deployment or schedule the
`--once` command frequently.

Claims use an atomic conditional update and a unique claim token so concurrent
workers do not normally send the same queued row. A `PROCESSING` claim older
than 30 minutes is recovered. Provider payloads include a stable
`sourceai-outbox-{id}` idempotency key and email uses a stable Message-ID.
External delivery is nevertheless at-least-once: a process can fail after the
provider accepts a message but before the local `SENT` commit. Provider-side
idempotency should remain enabled.

## Provider settings

Email (recommended Resend API provider):

- `CATALOG_RESEND_API_KEY` (sending-only key stored in the deployment secret manager)
- `CATALOG_RESEND_FROM_EMAIL` (sender on a verified domain)

Resend is selected when both values are configured. The API adapter sends text
and escaped HTML, records the provider message ID, and uses a stable
`sourceai-outbox-{id}` idempotency key. Never commit or log an API key. The
`onboarding@resend.dev` sender is for sandbox testing only and must not be used
for production password recovery.

After adding runtime secrets, verify one delivery from the catalog-service
directory without passing the API key on the command line:

```powershell
python scripts/send_test_email.py
```

The command prompts for the recipient and reports only a safe result/provider
message ID. It never prints the API key.

Email (optional SMTP fallback):

- `CATALOG_SMTP_HOST`
- `CATALOG_SMTP_PORT` (default `587`)
- `CATALOG_SMTP_USERNAME`
- `CATALOG_SMTP_PASSWORD`
- `CATALOG_SMTP_FROM_EMAIL`
- `CATALOG_SMTP_STARTTLS=true`

SMS and WhatsApp use provider-neutral HTTPS webhook contracts:

- `CATALOG_SMS_WEBHOOK_URL`, `CATALOG_SMS_API_TOKEN`,
  `CATALOG_SMS_SENDER_ID`
- `CATALOG_WHATSAPP_WEBHOOK_URL`, `CATALOG_WHATSAPP_API_TOKEN`,
  `CATALOG_WHATSAPP_SENDER_ID`

The webhook JSON body contains `channel`, `to`, `sender_id`, `template`,
`data`, and `idempotency_key`. A `2xx` response means accepted; providers may
return `X-Message-ID`. Production validation rejects plaintext provider
webhooks, partial URL/token configuration, and SMTP without STARTTLS.
Credentials, destinations, payloads, transport responses, and raw provider
exceptions are not emitted by the worker. Admin outbox responses mask
destinations.

## Deployment

1. Set provider credentials and the payment-proof host allowlist in the secret
   manager; never commit them.
2. Apply `alembic upgrade head`.
3. Start the API and exactly one or more notification workers.
4. Submit a provider sandbox message and verify `QUEUED -> SENT`. Without
   credentials, verify the expected `QUEUED -> FAILED` state.
5. Alert on old `QUEUED`, stale `PROCESSING`, or repeated `FAILED` rows.
