# Frontend browser smoke tests

The Playwright suite has two explicit layers:

- `npm run test:e2e:public` starts Next.js and checks public navigation without inventing backend data.
- `npm run test:e2e:roles` validates live customer/admin role routing against a running catalog API.

Role-routing tests are skipped with a visible reason unless all required values are provided:

```text
NEXT_PUBLIC_API_BASE_URL=http://127.0.0.1:8001
E2E_CUSTOMER_IDENTIFIER=...
E2E_CUSTOMER_PASSWORD=...
E2E_ADMIN_IDENTIFIER=...
E2E_ADMIN_PASSWORD=...
```

Accounts must be provisioned specifically for the test environment. The
test-only helper refuses every environment except `CATALOG_ENVIRONMENT=test`
and also requires privileged MFA to be disabled for this narrow routing
fixture:

```text
python -m alembic upgrade head
python -m scripts.provision_e2e_accounts
```

The helper reads the identifiers/passwords above, creates no default
production credential, and must only point at a disposable database. Do not
reuse production accounts or a production database.

Install the browser once on a new machine:

```text
npx playwright install chromium
```

The CI frontend job runs both the public layer and the isolated live role
layer. The latter starts a disposable SQLite API, provisions test-only
customer/admin accounts, runs the routing assertions, and never disables MFA
outside the `test` environment. Transactional checkout/payment/admin browser
coverage remains a separate launch gate.
