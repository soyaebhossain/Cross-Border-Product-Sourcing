# Frontend browser smoke tests

The Playwright suite has two explicit layers:

- `npm run test:e2e:public` starts Next.js and checks public navigation without inventing backend data.
- `npm run test:e2e:roles` validates live customer/admin role routing against a running catalog API.

The `@roles` run also includes two admin specs that need no backend because
they answer the admin API themselves: `admin-media.spec.ts` and
`admin-erp.spec.ts` (module menu, a purchase order from the customer order to
closed, supplier payables and order profit and loss). They check what the pages
show and which requests they send; the API rules behind them are covered by
`services/catalog-service/tests/test_procurement.py`.

CI runs the public layer with the API unreachable, so the catalog comes from
the committed snapshot. To reproduce that locally:

```text
API_BASE_URL=http://127.0.0.1:65534 NEXT_PUBLIC_CATALOG_SNAPSHOT_FALLBACK=1 npm run build
CI=1 PLAYWRIGHT_USE_BUILD=1 API_BASE_URL=http://127.0.0.1:65534 E2E_EXPECT_CATALOG_SNAPSHOT=1 NEXT_PUBLIC_CATALOG_SNAPSHOT_FALLBACK=1 npm run test:e2e:public
```

`PLAYWRIGHT_USE_BUILD=1` starts the production build (`next start`) instead of
the development server. CI always does this: on a slow runner the development
server can serve a page while its manifest is half written and answer with
"Unexpected end of JSON input", which made the public layer fail at random. The
API address and the snapshot fallback are fixed at build time, so CI builds
once for the public layer and once for the role layer. Without the variable,
Playwright starts the development server, which is quicker while writing tests.

Role-routing tests are skipped with a visible reason unless all required values are provided:

```text
API_BASE_URL=http://127.0.0.1:8001
E2E_API_BASE_URL=http://127.0.0.1:8001
E2E_CUSTOMER_IDENTIFIER=...
E2E_CUSTOMER_PASSWORD=...
E2E_ADMIN_IDENTIFIER=...
E2E_ADMIN_PASSWORD=...
```

Browser requests remain on the Playwright storefront origin and reach the
test API through Next.js rewrites. `E2E_API_BASE_URL` is used only by the test
runner's direct backend readiness check.

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
