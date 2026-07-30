# SourceAI launch acceptance checklist

Audit date: 2026-07-30

Scope: the current uncommitted `.publish-worktree` source tree

Target: the P0, P1, analytics, global UX, and production-foundation requirements
agreed for launch

## Status definitions

- **VERIFIED** — the implementation is present and has a focused automated
  assertion or a repository-level validation job covering the stated
  behaviour.
- **IMPLEMENTED** — the implementation is present, but the final deployed
  environment or a complete end-to-end acceptance run has not yet been
  demonstrated.
- **PARTIAL** — a usable portion exists, but a stated acceptance condition is
  missing or only covered at one layer.
- **EXTERNAL-ONLY** — completion requires repository-owner, secret-manager,
  provider, DNS/TLS, managed-infrastructure, or deployment access that is not
  represented by a source-code change.

`VERIFIED` here describes repository evidence, not production certification.
The release remains blocked until every item in **External go-live gates** has
an owner, evidence, and sign-off.

## Executive decision

**Not production-ready yet.** The high-risk application controls for identity,
research access, payment decisions, order transitions, quote-to-order
integrity, audit attribution, and secure admin provisioning are implemented
and test-covered. The current blockers are:

1. purge the historical PII/database objects from all Git refs and rotate every
   potentially exposed credential;
2. provision and migrate the real production PostgreSQL service, shared rate
   limiter/cache, encrypted backups, HTTPS edge, monitoring alerts, and message
   providers;
3. complete and run the protected customer/admin browser acceptance suite
   against release-like services;
4. obtain a WCAG 2.2 audit rather than treating responsive CSS and keyboard
   smoke tests as conformance;
5. close the remaining product-surface gaps listed below before calling the
   control center complete.

## Current workspace validation snapshot

This is a transient working-tree record, not release evidence:

- Backend Ruff and `compileall` passed; the final local run reported **70
  passing tests** and `pip-audit` reported **0 known vulnerabilities** for
  `requirements.txt`.
- A live SQLite backup/isolated restore passed. The live development database
  was upgraded to Alembic `20260730_04`; integrity checks reported 27
  categories, 610 products, 85 medical products, 60 jewelry/gem/precious-metal
  products, 140 priority everyday/travel/pet accessories, seven sourcing
  origins, zero foreign-key violations, zero duplicate normalized slugs, and
  zero active administrators.
- The PII-free public catalog snapshot exported twice with the same SHA-256
  (`bfb39d06c7f3ba4046ee2fa7d4a4bc0652715b7a8f6fba0e172d6100bd5af97e`);
  desktop and mobile snapshot browse checks passed.
- A fresh SQLite upgrade to Alembic head passed. The PII-free
  catalog/configuration-to-empty-PostgreSQL migration tool has scope/order
  tests, but an actual PostgreSQL transfer has not yet been run.
- Frontend `npm run lint -- --quiet`, `npx tsc --noEmit`, and the Next.js
  15.5.22 production build passed; the build generated all 35 pages. The
  prebuild deployment guard also confirmed the maintained frontend uses
  Next.js and contains no Vite dependency or configuration file.
- Playwright passed 4 public desktop/mobile checks and 2 live customer/admin
  role-routing checks against an isolated test database. The production
  frontend dependency audit reported 0 findings. Compose configuration passed
  both default and gateway profiles; image/runtime validation remains blocked
  locally because the Docker Linux engine/WSL is unavailable.
- Transactional browser acceptance, an actual PostgreSQL transfer, container
  builds, and external security checks remain pending. Rerun every check on
  the exact final commit rather than copying this working-tree result into
  release evidence.

## P0 — required before launch

| Requirement | Status | Evidence and acceptance note |
| --- | --- | --- |
| Remove old user database/PII from the active tree | IMPLEMENTED | The legacy `backend/` tree and `backend/db.sqlite3` are staged for deletion, runtime `*.sqlite3`/`*.db` files are ignored, and the active service does not read the Django database. This does not remove prior Git objects. |
| Purge PII/secrets from Git history | EXTERNAL-ONLY | `git log --all -- backend/db.sqlite3 .env` still finds historical commits. Follow `production-security-runbook.md`; rotate first, then coordinate `git filter-repo`, force-push, cache/artifact expiry, and fresh clones. |
| Rotate exposed credentials | EXTERNAL-ONLY | Source code cannot prove revocation. Record secret-store rotation evidence for JWT, database, OAuth, provider, backup, and infrastructure credentials. |
| Strong production JWT/cookie/origin/MFA configuration | VERIFIED | `app/config.py` fails production startup for a short/default JWT, default PostgreSQL password, insecure cookies, wildcard/non-HTTPS origins, missing/distinct-invalid MFA key, disabled privileged MFA, missing payment-proof allowlist, or missing HTTPS monitoring DSN. Covered by `tests/test_security_hardening.py`. |
| Secure admin MFA | VERIFIED | Privileged password login issues no session before TOTP enrollment/verification; secrets are encrypted, recovery codes are one-time keyed hashes, challenges are bounded, and recovery/MFA events are audited. Evidence: `app/auth.py`, `app/api/routes/auth.py`, `tests/test_identity_security.py`. |
| Login rate limit and account lockout | VERIFIED | Bounded in-process IP/account rate limits and persistent database-backed account/MFA lockout are present and test-covered. The edge also limits login/register traffic. A shared multi-replica limiter is still an external production gate. |
| Refresh-session security | VERIFIED | Refresh tokens are stored as hashes, rotate on use, and replay revokes the session family; logout revokes the presented session. Covered by `tests/test_identity_security.py`. |
| Research analytics and CSV are admin-only | VERIFIED | Both `/api/research/analytics/` and `/api/research/export.csv` require role `admin`; customer and operator denial is tested in `tests/test_security_hardening.py`. The customer UI does not expose research navigation. |
| Full pending-payment queue | IMPLEMENTED | `/api/admin/payments/` uses server pagination and can enumerate all matching proofs. The dashboard intentionally shows a 12-row preview plus `payment_queue_total`; it is no longer the review queue. |
| Proof preview and Approve/Reject confirmations | IMPLEMENTED | Admin payment list/detail show proof links/previews and modal decisions with a mandatory reason. Evidence: `app/admin/payments/`, `components/payment-proof-preview.tsx`. Final live-browser verification with an allowed object-storage host is pending. |
| Unique transaction ID and verifier identity/time | VERIFIED | Provider + normalized transaction ID is unique; decisions persist `decided_by_user_id`, `decided_at`, reason, request ID, immutable attempt/decision records, and audit before/after state. Covered by operations/customer payment tests. |
| Payment reversal and refund ledger | VERIFIED | Verification reversal is restricted before purchase; purchased/fulfilled orders use refunds. Refund and reversal references are unique, over-refunds are rejected, and original rows are retained. Evidence: `services/financial_operations.py`, `tests/test_admin_operations_analytics.py`. |
| Controlled order state machine | VERIFIED | Forward transitions are enumerated, payment approval is required before confirmation, tracking is required before transit, an operational note is mandatory, and status/audit rows carry actor and request ID. Covered by `tests/test_operations_integrity.py` and `tests/test_admin_operations_analytics.py`. |
| Quote-to-order integrity | VERIFIED | Saved quote ID, server-owned locked pricing snapshot, expiry, offer availability, owner/matching fields, one-order-per-quote constraint, and per-user idempotency are enforced. Covered by both operations test modules. |
| No default/known production admin credential | VERIFIED | No admin is auto-seeded. `scripts/provision_admin.py` prompts or reads a process-only environment secret, refuses promotion/overwrite, validates password strength, audits provisioning, and requires first-login MFA. Covered by `tests/test_operational_security.py`. |

## P1 — professional admin control center

### Required destinations

| Screen | Status | Evidence and limitations |
| --- | --- | --- |
| Overview | IMPLEMENTED | Dedicated `/admin` operational and analytics overview, comparison cards, queues, charts, freshness and drill-down links. |
| Orders | IMPLEMENTED | Paginated list and dedicated `/admin/orders/[id]` detail; status, tracking, settlement, refund and reversal workflows are not routed through customer pages. |
| Payments | IMPLEMENTED | Paginated review queue and dedicated `/admin/payments/[id]` detail with proof and decision history. |
| Saved quotes | IMPLEMENTED | Paginated list and dedicated `/admin/quotes/[id]` detail. |
| Products and categories | IMPLEMENTED | Product, category, and variant CRUD/detail routes with audited soft archive/restore. |
| Suppliers and offers | IMPLEMENTED | Supplier and offer CRUD/detail routes with audited soft archive/restore. |
| Customers/users | IMPLEMENTED | Admin-only list/detail, role/active updates, last-admin safeguards, and session invalidation are present. Current-role/active-state authorization is test-covered, but the complete user-management mutation workflow still needs protected API/browser acceptance. |
| Shipping, currency, fees, ETA and duty | IMPLEMENTED | `/admin/rules` provides real configuration CRUD/archive, filters and audit notes. |
| Roles and permissions | IMPLEMENTED | `/admin/roles` shows the backend-enforced fixed role contract. It is intentionally not a custom role-builder. |
| Audit logs | IMPLEMENTED | Admin-only searchable/paginated audit list with actor, action, entity, note, request ID, and CSV/print output. There is no separate audit-record detail route. |
| Settings | PARTIAL | `/admin/settings` stores personal language/density/motion/alert preferences in browser storage. It is not a server-side organization/security settings console. |
| Support tickets, disputes, notification outbox | IMPLEMENTED | Sidebar routes, searchable/filterable paginated queues, current-page CSV/print, dedicated detail pages, support reply/status, valid dispute transitions, and outbox monitoring are wired to the audited APIs. Dispatch/requeue remains administrator-only while operators have the intended operational read/respond access. |

### Management-screen interaction contract

**PARTIAL.** The shared `AdminDataPage` provides search, resource filters,
current-page sorting, server pagination, selected rows, CSV export, browser
print/PDF, retry/error states, and confirmation modals. Product, category,
variant, supplier, offer, and rules screens provide real bulk archive/restore.
However:

- date range is not enabled on every list;
- orders, payments, quotes, users, and audit have no bulk operation;
- CSV/print exports operate on the currently loaded page (or selected rows),
  not a server-generated export of the entire filtered result;
- sorting is client-side within the current page, not a server sort contract;
- audit, roles, rules, and settings do not all have dedicated record-detail
  pages.

Those limitations must either be implemented or explicitly accepted as a
revised P1 scope. The current UI must not be described as satisfying the
literal “every management screen has every control” requirement.

### Role boundary

**VERIFIED for customer isolation.** `/account` redirects privileged users to
`/admin`; `/admin` rejects customers; current database role, active state, and
auth version are reloaded for sensitive authorization. `/research` is
administrator-only. The operational dashboard and the newer admin analytics
APIs intentionally allow both `admin` and `operator`; if “admin-only dashboard”
was meant literally rather than “not visible to customers,” tighten this
policy before launch.

## Analytics

| Requirement | Status | Evidence and acceptance note |
| --- | --- | --- |
| Today, 7-day, 30-day and custom range | IMPLEMENTED | Overview and drill-down APIs accept presets/custom dates and timezone conversion; admin UI exposes the ranges. Custom-range aggregation is test-covered, while preset selection still needs browser acceptance. |
| Previous-period value and percentage trend | IMPLEMENTED | The immediately preceding equal-duration period is returned for financial metrics; zero baselines return a null percentage rather than a misleading infinite change. Add a focused current/prior-period reconciliation test. |
| Revenue/order value, verified cash, outstanding, refunds | VERIFIED | SQL aggregates and financial-ledger reconciliation are covered by `tests/test_admin_operations_analytics.py`; metric wording is defined in `dashboard-metric-contract.md`. |
| Quote → order → delivered funnel | IMPLEMENTED | Saved-quote linkage and delivered conversion are returned and rendered. Quote/order integrity is test-covered, but the funnel values do not yet have a focused reconciliation assertion. |
| Average delivery and delayed shipments | VERIFIED | Delivered-duration, delivered-late, and active-overdue metrics plus paginated delayed-order drill-down are present. |
| Supplier defect, reliability and fulfilment SLA | VERIFIED | Outcome-aware SQL metrics return `N/A` when evidence is missing; paginated supplier drill-down is present. |
| Country/category/product profitability | VERIFIED | Realized margin requires actual-cost settlement; order values are allocated across items to avoid duplicated multi-item revenue. Country preview and paginated three-dimension drill-down are present. |
| Drill-down chart and metric tooltip | PARTIAL | Metric definitions/tooltips and links to source-backed paginated tables exist. The financial chart itself is not an interactive click-to-filter drill-down. |
| Selected timezone and last-updated time | PARTIAL | API supports an IANA timezone and responses/rendering show timezone, generated time, data freshness, and cache state. Admin UI currently fixes analytics to `Asia/Dhaka` instead of offering a timezone selector. |
| SQL aggregation, cache and paginated API | PARTIAL | New `/api/admin/analytics/*` uses SQL aggregation, paginated drill-downs, and a bounded 30-second cache. The cache is process-local, so Redis/shared invalidation is still required for multiple replicas. Legacy `/api/research/analytics/` still materializes all saved quotes and orders in memory and should be refactored or retired before it is used on large data. |

## Global UX

| Requirement | Status | Evidence and acceptance note |
| --- | --- | --- |
| Bangla/English switch | IMPLEMENTED | Global locale context, header switch, customer/admin copy, and `lang` updates exist. Translation is mixed-source and still needs a native-speaker QA pass. |
| Currency, locale and timezone formatting | PARTIAL | Monetary helpers consistently show two decimals and use `Intl`; account preferences persist language/currency/timezone. Most screens still render BDT and `Asia/Dhaka`, and saved account preferences are not the global formatting source. |
| WCAG 2.2 accessibility | PARTIAL | Semantic labels, focus states, reduced-motion preference, responsive navigation/tables, screen-reader chart table, and a keyboard smoke test exist. There is no axe/Accessibility Insights suite, screen-reader test, contrast report, or independent WCAG 2.2 audit; conformance must not be claimed. |
| Mobile admin navigation and responsive tables | IMPLEMENTED | Collapsible admin sidebar and responsive/scrollable table styles exist. Final device/browser acceptance remains pending. |
| Confirmation, toast, retry and clear error states | IMPLEMENTED | Reusable modal/toast/error/retry patterns are used across destructive and operational admin flows. Browser E2E coverage of these flows is still limited. |
| Customer profile/company/address book | VERIFIED | Owner-scoped APIs, default address behaviour, UI wiring, and immutable invoice snapshot tests exist. |
| Customer invoices | IMPLEMENTED | `/account/invoices` now uses the owner-scoped paginated list/detail APIs and offers the tested immutable Latin PDF plus Unicode-safe printable Bangla/English HTML. Protected browser acceptance of authenticated downloads remains pending. |
| Customer notifications and preferences | IMPLEMENTED | `/account/notifications` wires persisted channel preferences, paginated inbox/unread filtering, mark-one/all-read, and real queued/sent/failed delivery states to the durable outbox APIs. Actual external delivery is tracked separately below. |
| Customer support and disputes | IMPLEMENTED | `/account/support` provides ticket creation/filter/pagination/detail/replies and dispute create/detail/cancel with mandatory reason, backed by owner-scoped APIs and privileged audit tests. |
| Payment retry | IMPLEMENTED | Customer order detail renders append-only attempt/decision history and permits a new proof only for a `PENDING` order whose proof is `REJECTED`/`REVERSED`; channel, transaction, and optional HTTPS proof URL validation match the tested backend contract. |
| Email/SMS/WhatsApp order notifications | PARTIAL | Real provider adapters, durable outbox, idempotency key, worker claims/recovery and fail-closed unconfigured state exist. Vendor credentials, templates/provider approval, sandbox acceptance, alerting, and customer UI are external/pending. |

## Production foundation

| Requirement | Status | Evidence and acceptance note |
| --- | --- | --- |
| PostgreSQL instead of SQLite | PARTIAL | SQLAlchemy/Psycopg, PostgreSQL Compose service, migration job, PostgreSQL CI migration check, and a test-covered PII-free catalog/configuration transfer into an empty Alembic-migrated PostgreSQL database exist. The audited local dataset is still SQLite; production PostgreSQL provisioning, actual transfer/reconciliation and cutover have not been demonstrated. |
| Alembic migrations | VERIFIED | Revisions `20260729_01` through `20260730_04` have one head; fresh/legacy test migrations and the live development upgrade to revision 04 passed. CI is configured to upgrade a fresh PostgreSQL 16 service. Resolve any historical duplicate saved-quote links before enforcing the skipped unique index noted in `admin-operations-backend.md`. |
| Automated backup and restore testing | PARTIAL | SQLite/PostgreSQL backup and isolated-restore scripts create checksum manifests; both the automated SQLite test and a live development SQLite backup/restore verification passed. Scheduled encrypted backups, PostgreSQL restore drills, media backup, RPO/RTO and restore evidence are external. |
| Error monitoring | IMPLEMENTED | Sentry initialization is PII-scrubbed and tagged with request ID; production requires an HTTPS DSN. A real project, release identifier, alert routing, retention and test event are external. |
| Structured logs and request/audit IDs | VERIFIED | Redacted JSON request logs, safe incoming ID validation, `X-Request-ID`, readiness checks and actor/request audit attribution are test-covered. |
| Alerts | EXTERNAL-ONLY | Code and runbooks name conditions, but no alert policy/routing/ownership can be proven from this repository. |
| Unit/API/RBAC/payment/end-to-end tests | PARTIAL | The final local backend run reported 49 passing security, identity, payment, migration, analytics, customer and operations tests. Playwright passed 4 public desktop/mobile checks and 2 live customer/admin role-isolation checks using disposable test-only accounts; CI now provisions the same isolated fixture and runs both layers. A full quote-to-checkout/payment retry/admin decision-reversal/notification/support browser suite and coverage threshold are still missing. |
| Security headers | IMPLEMENTED | Next and API emit CSP, frame, content-type, referrer, permissions and related headers; HSTS is production/HTTPS conditional. Edge header/TLS verification is pending. |
| HTTPS | EXTERNAL-ONLY | The repository supplies an HTTP Nginx baseline and HTTPS requirements. DNS, certificate issuance/renewal, 443-only exposure, redirects and external scanning require the deployment platform. |
| Dependency updates/audit | IMPLEMENTED | Pinned backend/frontend versions, weekly Dependabot, `pip-audit`, and production `npm audit` CI steps exist; final local backend and production frontend audits both reported zero findings. Full dev-only tooling still follows upstream advisories, and image/SBOM scanning remains release evidence. |
| CI/CD | PARTIAL | GitHub Actions validates backend, frontend lint/type/build, public and isolated live-role Playwright, PostgreSQL migrations, Compose/Nginx config, and image builds. There is no deployment/promotion/rollback workflow, so this is CI rather than complete CI/CD. |
| Containers and least privilege | IMPLEMENTED | API and web production images run as non-root users; Compose health checks and service dependencies exist. Both Compose profiles validated locally. Docker client 29.6.2 is installed, but image/runtime validation is blocked until WSL and the Docker Linux engine are operational. |

## External go-live gates

Do not change any status below without attaching evidence from the owning
system:

- [ ] Repository owner completed and reviewed the Git history purge across all
  branches/tags and expired host caches/artifacts.
- [ ] Every exposed or possibly exposed credential was rotated/revoked and the
  old value was proven unusable.
- [ ] Production admin was provisioned out of band, enrolled MFA, stored
  recovery codes securely, and no shared/default admin remains.
- [ ] Managed PostgreSQL was provisioned with least privilege; migration,
  record-count/financial reconciliation, rollback and cutover evidence passed.
- [ ] Shared Redis (or an accepted equivalent) backs multi-replica rate limits
  and analytics cache invalidation.
- [ ] HTTPS-only edge, managed certificate renewal, exact proxy trust, firewall,
  request limits and security-header scan passed.
- [ ] Error-monitoring project, release tag, PII scrubbing test, alert routes,
  escalation owners and synthetic test event passed.
- [ ] SMTP/SMS/WhatsApp credentials and approved templates passed sandbox
  delivery; outbox age/failure alerts are active.
- [ ] Encrypted database and media backup schedule is active; an isolated
  PostgreSQL restore drill met approved RPO/RTO.
- [ ] Protected role, customer checkout/payment retry, admin decision/reversal,
  notification, support/dispute and mobile browser E2E passed against the
  release candidate.
- [ ] WCAG 2.2 audit, keyboard/screen-reader checks, contrast and zoom/reflow
  findings were resolved or formally accepted.
- [ ] Deployment, rollback, database rollback/roll-forward, incident response
  and on-call ownership were rehearsed.

## Repository verification commands

Run these on the exact release commit and attach logs to the release record:

```powershell
cd services/catalog-service
.\.venv\Scripts\python.exe -m pip_audit -r requirements.txt
.\.venv\Scripts\python.exe -m ruff check app scripts tests migrations
.\.venv\Scripts\python.exe -m compileall -q app scripts
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m alembic heads

cd ..\..\apps\web-next
npm audit --omit=dev --audit-level=high
npm run lint
npx tsc --noEmit
npm run build
npm run test:e2e:public
npm run test:e2e:roles
```

The protected role suite requires a live test API and disposable credentials.
CI creates them with the test-only, fail-closed
`scripts/provision_e2e_accounts.py`; see `frontend-e2e.md`.
