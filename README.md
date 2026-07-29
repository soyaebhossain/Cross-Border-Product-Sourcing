# SourceAI cross-border sourcing

SourceAI is a Next.js storefront and role-aware control center backed by
FastAPI, SQLAlchemy, Alembic, and PostgreSQL. The retired Vite and Django
applications are not part of the active tree.

## Active applications

- `apps/web-next` — customer storefront, account area, admin control center,
  English/Bangla UI, and browser end-to-end tests.
- `services/catalog-service` — catalog, sourcing, identity, quotes, orders,
  payments, audited administration, analytics, and customer APIs.
- `docker-compose.yml` — Next.js, FastAPI, and PostgreSQL development stack.
- `gateway/nginx.conf` — reverse-proxy baseline; production TLS belongs at the
  managed edge/load balancer.

The current development catalog contains 14 categories and 410 products,
including Medical Products & Accessories. China, India, Singapore, and
Thailand are available sourcing origins. Runtime database files are ignored
and must never be committed.

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

## Hosted deployment

- Configure the Vercel project root as `apps/web-next`; that directory contains
  the Next.js deployment config. Set both `NEXT_PUBLIC_API_BASE_URL` and
  `API_BASE_URL` to the public API origin.
- `render.yaml` builds the maintained non-root FastAPI image, applies Alembic
  migrations before startup, and checks `/api/ready`. Before syncing the
  Blueprint, provide the `sync: false` MFA, monitoring, and payment-proof
  settings from a secrets manager.
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
