# SourceAI cross-border sourcing

SourceAI is a Next.js storefront and role-aware control center backed by
FastAPI, SQLAlchemy, Alembic, and PostgreSQL. The retired Vite and Django
applications are not part of the active tree.

## Ownership

SourceAI owns and maintains the application branding and original project
content. Copyright © 2026 SourceAI. All rights reserved. Development tools,
automation services, and hosting providers are infrastructure only; they are
not authors, co-authors, owners, or collaborators of this project. Third-party
packages remain subject to their respective licenses.

## Active applications

- `apps/web-next` — customer storefront, account area, admin control center,
  English/Bangla UI, and browser end-to-end tests.
- `services/catalog-service` — catalog, sourcing, identity, quotes, orders,
  payments, audited administration, analytics, and customer APIs.
- `docker-compose.yml` — Next.js, FastAPI, and PostgreSQL development stack.
- `gateway/nginx.conf` — reverse-proxy baseline; production TLS belongs at the
  managed edge/load balancer.

The current development catalog contains 27 categories and 610 products. It
includes Medical Products & Accessories, Jewelry, Gems & Precious Metals, ten
priority everyday-goods segments, plus travel/luggage and pet-care accessories.
China, India, Malaysia, Singapore, Thailand, Turkey, and Vietnam are available
sourcing origins. Seeded prices and routes are indicative demo values; material,
electrical, food-contact, purity, grade, certification, origin, HS
classification, and import requirements require independent verification.
Runtime database files are ignored and must never be committed.

## Machine-learning starter datasets

The reproducible, PII-free tutorial pack is in `datasets/ml-starter-v1`.
It contains static catalog features, category-classification examples,
formula-labelled offer-price examples, a clearly marked synthetic monthly demand
series, a field dictionary, source/file checksums, and an empty contract for
collecting real quote-to-delivery outcomes. These datasets are for pipeline and
coursework prototypes only; they are not observed marketplace history and must
not be used to claim production model accuracy.

Generate or validate the pack from the repository root:

```powershell
python services/catalog-service/scripts/export_ml_starter_datasets.py
python services/catalog-service/scripts/export_ml_starter_datasets.py --check
```

## Live pricing and price freshness

Cross-border costs move daily, so SourceAI never presents a stored price as a
current market price without saying where it came from and how old it is.

Pipeline: verified or live data → deterministic landed-cost rules → AI
explanation → human verification. The AI layer never calculates or changes a
monetary value.

- **Provenance.** Supplier offers, currency rates, freight rate cards and duty
  rules record `price_source` (`seeded`, `csv_import`, `admin`,
  `supplier_quote`, `api`), `source_reference`, `verified_at` and an optional
  `valid_until`. Seeded and migrated rows have no `verified_at`, so they are
  reported as unverified. An administrator saving a price stamps it as
  admin-verified at that moment.
- **Freshness policy.** Every quote returns a `pricing` block listing each
  input with its source, verification time and maximum age (defaults: FX 48 h,
  supplier offer 7 days, freight 30 days, duty 365 days or its `effective_to`).
  If any input is stale or unverified the quote is `indicative`; otherwise it
  is `verified`. The quote page shows this to the customer, and the AI
  explanation must say indicative prices need re-verification and requires
  human review.
- **Live FX.** With `CATALOG_FX_AUTO_REFRESH_ENABLED=true` the API refreshes
  every active currency's BDT rate from
  [ExchangeRate-API](https://www.exchangerate-api.com) (open access, daily
  updates, attribution shown on the quote page) every
  `CATALOG_FX_REFRESH_INTERVAL_HOURS`. A move larger than
  `CATALOG_FX_MAX_CHANGE_PERCENT` against a recent live rate is held for an
  administrator instead of repricing every quote. Admins can also refresh from
  **Admin → Rules → Refresh live FX**, or a scheduler can run
  `python -m scripts.refresh_fx_rates`.
- **Re-pricing before ordering.** Ordering from a saved quote recalculates the
  landed cost with current data. A change within
  `CATALOG_QUOTE_REPRICE_TOLERANCE_PERCENT` (default 2%) keeps the saved price;
  a larger change blocks the order and asks the customer for a new quote. The
  check is stored in the order's `quote_snapshot.reprice_check`.
- **Admin visibility.** `GET /api/admin/pricing/freshness/` and the Rules page
  show how many active inputs of each kind are stale or unverified.

Supplier offers, freight and duty still come from the catalog dataset or
administrator entry. Marketplace, carrier and customs-tariff feeds can be added
as further `price_source = "api"` adapters without changing the quote logic.

## Exchange-rate outlook and country risk

Both features use published external data, stored with its source and date.
Neither is produced by the AI layer.

- **FX outlook.** The API stores one observed BDT rate per currency per day
  (`pricing_fx_rate_history`, from the open fawazahmed0 currency-api dataset,
  150 days by default). The outlook is a random walk with drift on daily log
  returns over a 30-day horizon, reported as an expected rate with a 90%
  interval. Every response includes a walk-forward backtest (mean absolute
  percent error and interval coverage on past forecasts), so the stated
  accuracy is measured, not assumed. Quotes turn the interval into a landed
  cost range; only the product cost and the percentage charges on it move with
  the rate. It needs at least 30 stored days and says so when it has fewer.
  It forecasts exchange rates only, not supplier prices or freight.
- **Country risk.** `sourcing_country_risk_indicators` holds three World Bank
  indicators per origin country: political stability (WGI), regulatory quality
  (WGI) and the Logistics Performance Index, each with its data year. The
  composite is their mean on a 0-100 scale (Low from 70, Medium from 55,
  otherwise High; these thresholds are a project choice). Medium and High
  country risk add to a route's risk score and appear as a weakness.
- **Refresh.** With FX auto-refresh enabled the API fills missing history days
  and refreshes the indicators monthly. Admins can run
  `POST /api/admin/market-data/refresh/`. Public reads:
  `GET /api/market/fx-outlook/?currency=USD` and
  `GET /api/market/country-risk/`.

## Keeping AI explanations grounded

The explanation model never calculates anything, and it is not trusted to
quote figures either.

- **Number check.** Every number in a model explanation, in Latin or Bangla
  digits, must appear in the server-calculated data it was given. An amount of
  100 or more may be rounded to a whole number and any figure to one or two
  decimals; nothing else is accepted. A summary that quotes an unsupported
  number is replaced by the deterministic summary, a list item that does so is
  removed, and the explanation is marked for human review. The API reports the
  count as `ai_metadata.unsupported_numbers_removed`.
- **Applied everywhere.** The check runs when the model answers, again when a
  quote is saved (the explanation returns from the browser) and again when a
  saved quote is shown.
- **Other guards.** Wrong-language text is dropped, Medium and High risk always
  require human review, indicative prices must be described as such, and any
  model failure falls back to the deterministic explanation.
- **Measuring it.** `python -m scripts.evaluate_explanations --sample 50
  --language both` asks the model to explain real catalog quotes and scores the
  raw answers before validation: answers with unsupported numbers,
  wrong-language statements, missing price caveats and missing review flags.
  It writes JSON and CSV. Each model answer is a billed request. This check
  covers numbers; it does not detect a false statement that contains no number.

## Admin ERP modules

The admin sidebar is grouped by business function: Dashboard, Sales,
Procurement, Finance, Customers, Master data and System.

- **Procurement.** A confirmed customer order gets a purchase order (PO) for
  its supplier, prefilled from the supplier offer the order was priced with.
  Status flow: `DRAFT -> SENT -> CONFIRMED -> RECEIVED -> CLOSED`, or
  `CANCELLED` before goods arrive. Confirming a PO moves the customer order to
  `PURCHASED`. Goods receipts record accepted and rejected units; a rejection
  needs a quality-check note and flags a quality defect on the order. A PO
  becomes `RECEIVED` when every ordered unit has been received.
- **Finance.** Supplier payments are recorded against a PO in the supplier's
  currency, each with the exchange rate of the day it was paid. Payments are
  reversed by an administrator, never deleted, and a PO cannot close while a
  balance is payable. *Supplier payables* lists open balances by age (0-30,
  31-60, over 60 days). *Order profit and loss* shows revenue, cash collected,
  supplier cost and margin per order, and says whether supplier cost comes from
  a PO or from the quote. Freight and duty stay quoted figures until the
  settled cost is entered on the order, so only then is a realized margin shown.
- **Controls.** Every change is written to the admin audit log. Operators run
  procurement and read finance; reversing a supplier payment needs an
  administrator.
- **Not included.** Warehouse stock movements, a double-entry general ledger,
  supplier invoices and tax filing are outside this system.

API: `/api/admin/purchase-orders/`, `/api/admin/orders/{id}/purchase-orders/`,
`/api/admin/finance/payables/`, `/api/admin/finance/order-pnl/` and
`/api/admin/erp/summary/`.

## Run locally on Windows

Install the backend and frontend dependencies once:

```powershell
cd services/catalog-service
py -3.13 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
cd ..\..\apps\web-next
npm ci
cd ..\..
```

Start or safely restart only this worktree's processes:

```powershell
.\start-dev.ps1 -Restart
```

- Web: `http://localhost:3000`
- API: `http://localhost:8001`
- API docs in development: `http://localhost:8001/docs`
- Readiness: `http://localhost:8001/api/ready`

The launcher refuses to stop an unrelated process that owns either port. The
read-only smoke check is:

```powershell
.\services\catalog-service\.venv\Scripts\python.exe scripts\smoke_rebuild.py
```

## Secure first admin

There are no hard-coded or auto-seeded production admin credentials. Apply the
schema and provision an administrator with a password entered through
`getpass`:

```powershell
cd services/catalog-service
.\.venv\Scripts\python.exe -m alembic upgrade head
.\.venv\Scripts\python.exe scripts\provision_admin.py --username owner --email owner@example.com
```

The first privileged login must enroll TOTP MFA and returns one-time recovery
codes. Store those codes outside the repository. Admin and customer routing is
role-separated; `/research`, research analytics, and CSV research export are
admin-only.

If an existing customer or admin loses access, use the interactive recovery
command from `services/catalog-service`:

```powershell
.\.venv\Scripts\python.exe scripts\recover_account_access.py --identifier owner --unlock
```

The command prompts for the new password, increments the account authentication
version, revokes active refresh sessions, consumes pending authentication
challenges, and records a credential-free audit event. It preserves disabled,
locked, and MFA state by default. Use `--reactivate` or `--clear-mfa` only after
verifying the account owner; prefer `--user-id` when a legacy identifier is
ambiguous. Never reactivate a known/default admin account—provision a replacement
and complete MFA enrollment instead.

## Hosted deployment

- Configure the Vercel project root as `apps/web-next`; that directory contains
  the Next.js deployment config. Browser traffic uses same-origin `/api` and
  `/media` routes, while server rendering and the fixed reverse proxy use the
  HTTPS API origin. Production Vercel deployments target the maintained Render
  service; non-production deployments require an explicit `API_BASE_URL` and
  must never proxy mutations into the production database. Every frontend build
  runs `verify:deployment` first and fails if the repository build configuration
  selects Vite or contains a Vite dependency/configuration file.
- `render.yaml` builds the maintained non-root FastAPI image, applies Alembic
  migrations before startup, and checks `/api/ready`. Before syncing the
  Blueprint, provide the `sync: false` MFA, monitoring, and payment-proof
  settings from a secrets manager.
- Migrations intentionally create an empty catalog. Transfer only the
  PII-free catalog scope into the new PostgreSQL database with
  `scripts/migrate_catalog_to_postgres.py`; never upload a legacy SQLite user
  database to a hosting provider.
- Run `python -m scripts.dispatch_notifications --poll-seconds 10` as exactly
  one separately managed worker when automated email/SMS/WhatsApp delivery is
  enabled.
- Use sibling custom domains for the web and API services in production, then
  update the exact frontend URL and CORS allowlist. Provider preview domains
  are not the final authenticated-cookie topology.

## Run with Docker and PostgreSQL

Copy `.env.example` to `.env`, replace every development placeholder, then:

```bash
docker compose up --build
```

The API container runs `alembic upgrade head` before startup. Production mode
fails closed when JWT, database, cookie, origin, MFA, payment-proof,
notification-transport, or monitoring settings are unsafe. Do not expose
PostgreSQL or the API directly to the public internet.

## Verification

Backend:

```powershell
cd services/catalog-service
.\.venv\Scripts\python.exe -m ruff check app scripts tests migrations
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m alembic heads
```

Frontend:

```powershell
cd apps/web-next
npm run lint
npx tsc --noEmit
npm run build
npx playwright install chromium
npm run test:e2e:public
```

Role-protected Playwright tests intentionally require explicitly provisioned
test accounts; see `docs/frontend-e2e.md`. CI provisions only a disposable
`CATALOG_ENVIRONMENT=test` fixture and runs both public and role-isolation
browser checks. CI also runs static, migration, API, security, payment, RBAC,
build, dependency-audit, Compose, and container checks.

## Operations

- Launch status, evidence, known gaps, and external go-live gates:
  `docs/launch-acceptance-checklist.md`
- Security, secret rotation, identity provisioning, backup, and restore:
  `docs/production-security-runbook.md`
- Admin API and metric contracts:
  `docs/admin-operations-backend.md`
- Dashboard metric definitions:
  `docs/dashboard-metric-contract.md`
- Customer accounts, invoices, notifications, support, disputes, and provider
  worker operations: `docs/customer-automation-runbook.md`
- Optional self-hosted n8n/Ollama quote explanations and safe fallback:
  `docs/n8n-ollama-automation.md`
- Browser acceptance layers and protected role-test prerequisites:
  `docs/frontend-e2e.md`

Create checksummed SQLite or PostgreSQL backups with
`services/catalog-service/scripts/backup_database.py`, and verify them in an
isolated restore with `verify_restore.py`. A successful backup is not accepted
until restore verification passes.

Production still requires environment-owned work: rotate real credentials in a
secret manager, coordinate any Git-history purge, provision managed
PostgreSQL/Redis, configure HTTPS and monitoring alerts, provide
email/SMS/WhatsApp vendor credentials, and schedule automated backup/restore
drills.
