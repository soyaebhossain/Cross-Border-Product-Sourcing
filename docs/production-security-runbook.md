# Production security runbook

This runbook covers the FastAPI, Next.js, and PostgreSQL production stack. Keep
production secrets in a managed secret store; never commit them, bake them into
an image, or print them in CI logs.

## Release and runtime baseline

1. Build immutable images and scan them before promotion.
2. Set `CATALOG_ENVIRONMENT=production`, a random 32+ character
   `CATALOG_JWT_SECRET`, a non-default database credential,
   `CATALOG_SECURE_COOKIES=true`, and explicit HTTPS values for
   `CATALOG_FRONTEND_URL` and `CATALOG_CORS_ORIGINS`. Generate a separate
   Fernet key for `CATALOG_MFA_ENCRYPTION_KEY` and keep
   `CATALOG_PRIVILEGED_MFA_REQUIRED=true`. Production startup fails closed when
   any of these identity controls is weak or missing.
3. Run `alembic upgrade head` as a one-off migration job using the same image
   and environment as the API. Follow the existing-schema baseline notes in
   `services/catalog-service/migrations/README.md`; stop the release if
   migration or revision verification fails.
4. Start Uvicorn with its access log disabled (`--no-access-log`); the
   application emits the redacted JSON request log. Production startup does not
   run `create_all()` or seed data.
5. Use `/api/health` only for process liveness. Use `/api/ready` for readiness;
   it returns 503 when the database or required schema is unavailable. Remove
   an instance from service before terminating it during a rolling deploy.

Each application request log contains a validated `request_id`, method, route
template, status, and duration. Query strings, bodies, cookies, authorization
headers, raw resource identifiers, client addresses, and exception messages are
excluded. The response exposes `X-Request-ID`; configure the edge proxy to
generate a safe ID when one is absent and use it to correlate proxy and
application logs. Restrict log access and retention as production data.

## Error monitoring and alert ownership

Production startup requires an HTTPS `CATALOG_ERROR_MONITORING_DSN`. Configure
the remaining release metadata explicitly:

- `CATALOG_ERROR_MONITORING_ENVIRONMENT` — stable environment name such as
  `production`;
- `CATALOG_RELEASE_VERSION` — immutable build/commit identifier;
- `CATALOG_ERROR_MONITORING_TRACES_SAMPLE_RATE` — a reviewed value between
  `0` and `1`.

`app/observability.py` disables default PII collection, removes request
headers, cookies, query strings, bodies, environment data and user context,
strips URL queries, and adds only the validated request ID as a correlation
tag. The source-level scrubber test does not replace a provider-side data
review. Before launch, send a synthetic non-customer exception from staging,
inspect the complete event at the provider, confirm the release/environment
tags and request-ID correlation, and delete the event if required by policy.

Create provider-side alerts with named primary/backup owners for at least:

- new and regressed exceptions;
- sustained 5xx or latency changes;
- readiness failures and deployment health;
- unusual 401/403/429 rates;
- payment/refund/reversal and privileged-role anomalies;
- old `QUEUED`, stale `PROCESSING`, or repeated `FAILED` notification rows;
- backup/restore failures.

Record notification destinations, escalation delay, maintenance windows,
retention, sampling, and a quarterly alert test. Source code can require a DSN,
but it cannot prove that alert routing or on-call ownership is configured.

## TLS and reverse proxy

- Expose only the reverse proxy/load balancer on TCP 443. Keep the API and
  PostgreSQL on private networks; firewall the database to application and
  administration networks only.
- Terminate TLS with a managed certificate, TLS 1.2 or newer, automatic renewal,
  and HTTP-to-HTTPS redirects. Keep HSTS enabled only after every production
  hostname is HTTPS-capable.
- Strip client-supplied `Forwarded` and `X-Forwarded-*` headers at the edge, then
  add authoritative values. If Uvicorn handles proxy headers, use
  `--proxy-headers --forwarded-allow-ips=<exact proxy CIDRs>`—never trust `*`
  unless the API is unreachable except through that proxy.
- Apply request-body limits, header limits, upstream timeouts, connection
  limits, and denial-of-service controls at the edge. Preserve `X-Request-ID`
  and never put OAuth codes, tokens, or full query strings in proxy access logs.

## Secret rotation

Inventory the owner, secret-store path, consumers, creation date, and expiry for
every JWT, database, OAuth, backup, and infrastructure credential.

- **JWT signing secret:** generate a cryptographically random replacement in
  the secret store, deploy it atomically, and verify login/refresh. The current
  single-key implementation invalidates existing sessions at rotation, so
  announce a re-login window. Add key IDs and an overlap key ring before
  attempting zero-logout rotation.
- **Database password:** create a new least-privilege database role or
  credential, grant only required rights, deploy consumers, verify readiness and
  migrations, then revoke the old credential. Do not reuse the PostgreSQL
  administrator role.
- **MFA encryption key:** treat rotation as a data migration. Decrypt each
  enrolled TOTP secret with the old key and immediately re-encrypt it with the
  new key in a restricted one-off job. Do not remove the old key until every
  privileged user has been migrated or explicitly re-enrolled.
- **Google/OAuth secret:** create the replacement with the provider, update the
  secret store and deployment, test the exact redirect URI, then revoke the old
  secret. Review redirect URIs and provider audit logs at the same time.

For any suspected exposure, rotate first, invalidate active sessions, preserve
audit evidence, and then investigate. Removing a value from the latest commit
does not remove it from Git history.

## Purging an exposed secret from Git (instructions only)

No history rewrite is performed by this runbook. A repository owner should:

1. Treat the value as compromised and rotate/revoke it before touching Git.
2. Freeze merges and pushes, notify maintainers, and preserve a restricted
   forensic mirror.
3. Use `git filter-repo` with an exact replacement file (preferred for a value)
   or an exact path removal. Review every ref and tag in a disposable mirror;
   do not use broad patterns.
4. Force-push the reviewed rewritten branches and tags during a coordinated
   window. Ask the Git host to expire cached objects where supported.
5. Invalidate old CI artifacts/caches, close or recreate affected pull
   requests, and require contributors to make fresh clones instead of merging
   old history back.
6. Run secret scanning across all refs and verify the revoked credential no
   longer works.

History rewriting disrupts clones, forks, tags, and open pull requests. Obtain
repository-owner approval and a rollback/coordination plan before executing it.

## Identity provisioning and privileged MFA

There is no built-in admin username or password, and the API no longer reads the
legacy Django user database. After `alembic upgrade head`, provision a new admin
interactively:

```shell
python scripts/provision_admin.py
```

For a non-interactive secret-store job, inject `SOURCEAI_ADMIN_PASSWORD` only
for that process. The command never accepts a password argument, refuses to
overwrite or promote an existing account, applies the production password
policy, and writes an audit event. Delete the injected environment value
immediately after the job.

### Account access recovery

Reset a customer or admin password from the catalog-service directory:

```shell
python scripts/recover_account_access.py --identifier account@example.com --unlock
```

Use a numeric ID when an audit or legacy-data review shows that an identifier is
ambiguous:

```shell
python scripts/recover_account_access.py --user-id 42 --reactivate --clear-mfa
```

The password is read twice with `getpass`; the CLI intentionally has no
`--password` option. An approved one-process secret-store job may instead inject
`SOURCEAI_ACCOUNT_PASSWORD`, which the script removes from its process
environment after reading. Do not place passwords in shell history, logs, CI
arguments, or the repository.

Every successful reset applies the password policy, rejects reuse of the current
password, increments `auth_version`, revokes every active refresh session,
consumes pending authentication challenges, and writes an audit event containing
only state flags and revocation counts. Account activation, lock state, and MFA
enrollment are preserved unless the operator explicitly supplies `--reactivate`,
`--unlock`, or `--clear-mfa`. Verify identity and record approval before those
flags are used. Never reactivate a known/default administrator; provision a new
administrator and enroll MFA.

The first privileged password login returns HTTP 202 with
`mfa_enrollment_required=true` and a five-minute `mfa_token`; it does not issue
authentication cookies. Call `/api/auth/mfa/enroll/start/`, scan the returned
`otpauth_uri`, then call `/api/auth/mfa/enroll/confirm/` with a current TOTP.
Confirmation returns the recovery codes once and only then issues a session.
Later password logins return a one-time challenge for
`/api/auth/mfa/verify/`. Recovery codes are one-time and stored only as keyed
hashes. TOTP secrets are encrypted at rest. Repeated password or MFA failures
persistently lock the account.

Refresh tokens are stored only as hashes, rotate on every use, and form a
server-side session family. Reuse of a rotated token revokes the active family.
Logout revokes the presented refresh session; access tokens expire after the
configured short lifetime.

## Required external security upgrades

These remaining controls require shared infrastructure:

- **Redis rate limiting:** use atomic, expiring counters/sliding windows shared
  by every API replica. Preserve separate IP and normalized-account keys, bound
  key cardinality, monitor 429 rates, and explicitly choose fail-open or
  fail-closed behavior per endpoint during a Redis outage.
- **Passkeys and step-up:** TOTP/recovery MFA is implemented for privileged
  login. Add WebAuthn/passkeys and explicit recent-authentication checks before
  high-risk role, payment reversal, MFA reset, and credential changes.

The process-local analytics cache also needs a shared Redis-backed adapter (or
an accepted equivalent) when more than one API replica is used; otherwise a
write can invalidate only the worker that handled it.

## PII-free catalog migration to PostgreSQL

`scripts/migrate_catalog_to_postgres.py` copies only the owned catalog,
supplier, pricing, shipping, ETA and duty configuration tables from a migrated
file-backed SQLite database into an empty PostgreSQL schema. It deliberately
excludes accounts, social identities, sessions, quotes, orders, payments,
invoices, notifications, support, disputes and audit records.

Before executing:

1. create and verify an isolated backup of the SQLite source;
2. provision an empty least-privilege PostgreSQL database;
3. run `alembic upgrade head` against both source and target and confirm they
   report the same revision;
4. inject `CATALOG_MIGRATION_SOURCE_URL` and `CATALOG_DATABASE_URL` from the
   approved runtime/secret store without writing either URL to logs;
5. run:

   ```shell
   python scripts/migrate_catalog_to_postgres.py --execute --minimum-products 470
   ```

The command refuses a non-SQLite source, non-PostgreSQL target, source without
an Alembic revision, revision mismatch, source below the product threshold, or
any target with pre-existing catalog rows. It copies in foreign-key order,
resets PostgreSQL sequences, and compares every in-scope table count inside
the target transaction.

Afterward, independently reconcile category/product, medical-product, and
precious-product counts, normalized slug/SKU uniqueness, offer foreign keys,
precious-material verification disclaimers, and representative quote
calculations. Keep the old database read-only until rollback expiry. If
historical customer/order/payment data must also move, do not broaden this
script: design and review a separate PII/financial migration with legal,
security and reconciliation owners.

### Temporary public catalog snapshot

Before the production API is ready, regenerate the read-only storefront
snapshot from the migrated SQLite source:

```shell
python scripts/export_public_catalog_snapshot.py --source /approved/catalog.sqlite3
```

The exporter uses a fixed public-field allowlist, excludes free text and
third-party images, and never reads accounts, quotes, orders, payments,
customer, support or audit data. Keep
`NEXT_PUBLIC_CATALOG_SNAPSHOT_FALLBACK=1` only during cutover. After
`/api/ready` returns 200 and the live browse API reports all 470 imported
products, set it to `0` and redeploy Vercel; live catalog data will then be the
only source.

## Backup and restore

- Create a consistent SQLite or PostgreSQL custom-format backup plus checksum
manifest:

  ```shell
  python scripts/backup_database.py --output-directory <restricted-encrypted-directory>
  ```

- Verify SQLite by restoring it into a disposable directory and running
  checksum, `integrity_check`, required-table, and Alembic-revision checks:

  ```shell
  python scripts/verify_restore.py --backup <backup-file>
  ```

- PostgreSQL verification requires a separately created, isolated, empty
  database. The verifier refuses a target that already contains tables:

  ```shell
  python scripts/verify_restore.py --backup <backup-file> \
    --empty-postgres-target-url <isolated-empty-database-url>
  ```

- Define and approve RPO/RTO. Schedule encrypted PostgreSQL backups plus WAL/PITR
  as needed, and back up required media separately. Store copies immutably in a
  separate account/region; keep encryption keys outside the backup location.
- Record database/version metadata, migration revision, checksums, timestamps,
  and retention. Monitor backup completion and storage integrity.
- At least quarterly, restore into an isolated environment using the documented
  application image and secrets. Run migrations, readiness checks, row-count
  reconciliation, representative login/quote/order reads, and integrity checks.
  Measure recovery time against RTO and document data loss against RPO.
- Restrict and audit restore access. Never restore production credentials,
  active sessions, or outbound integrations into a test environment.

## Incident and operational checks

Alert on sustained readiness failures, 5xx/latency changes, unusual 401/403/429
rates, privileged role changes, payment decisions, backup failures, and OAuth
callback errors. During an incident, preserve the request ID and audit records,
rotate exposed credentials, isolate affected services, and record every
operator action. Test this runbook after material auth, proxy, schema, or
infrastructure changes.

The complete implementation-versus-environment acceptance matrix is maintained
in `launch-acceptance-checklist.md`. Do not infer production readiness from a
passing local test suite alone.
