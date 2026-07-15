
# Cross-Border Product Sourcing Rebuild

## Vercel deployment

The production web application is the Next.js project in `apps/web-next`.
The root `vercel.json` installs and builds that application, so importing the
repository into Vercel does not deploy the legacy root Vite application.

For the cleanest monorepo setup, the Vercel project's **Root Directory** may
also be set to `apps/web-next`; when doing that, clear any custom build and
output settings so Vercel uses the Next.js defaults from that directory.

**Welcome**: A short project introduction and quick-start checklist are in [WELCOME.md](WELCOME.md). You can also open the simple local welcome page at [public/welcome.html](public/welcome.html).

The rebuild now starts from the stack you asked for:

- `services/catalog-service`: FastAPI backend for catalog and sourcing flows
- `apps/web-next`: Next.js storefront for the new frontend
- `postgres`: primary database for the rebuild
- `docker-compose.yml`: Docker entrypoint for `FastAPI + Next.js + PostgreSQL`

The legacy Django app under `backend/` is still present. The FastAPI service can import catalog data from that legacy SQLite database and serve the legacy uploaded media files so the rebuild starts with your real products instead of placeholder data.

## Current Rebuild Scope

Implemented in the new stack:

- `GET /api/categories/`
- `GET /api/countries/`
- `GET /api/products/`
- `GET /api/products/{slug}/`
- `POST /api/quote/`
- `POST /api/quote/recommend/`
- `POST /api/recommendations/cheapest-country/`
- `POST /api/quote/save/`
- `GET /api/quote/saved/`
- `POST /api/orders/create-manual/`
- `GET /api/orders/me/`
- `GET /api/orders/{id}/`
- `POST /api/orders/{id}/status/`
- `GET /media/...` for legacy uploaded product images
- Next.js home page with category and product listing
- Next.js product detail page with cheapest-country recommendation panel
- Heuristic hybrid sourcing recommendation response with cost, ETA, quality, and reliability ranking
- Itemized total landed cost (product, shipping, customs, VAT, handling, and other import cost)
- Buyer-weighted 0-100 sourcing score with supplier reliability, Low/Medium/High risk, advantages, and weaknesses
- Side-by-side saved quotation comparison
- Research analytics dashboard at `/research` and CSV dataset export at `/api/research/export.csv`
- Evaluation-readiness placeholders for NDCG/Precision@K, MAE/RMSE, accuracy/F1, and UX measures

### Decision methodology

Recommendation weights accept `price`, `quality`, `delivery`, `reliability`, and `risk` as either fractions or percentages. The heuristic normalizes the weights and combines normalized landed cost, ETA, seller rating/stock reliability, and risk into a higher-is-better score out of 100. Reliability currently uses seller rating and stock coverage because confirmed order, dispute, response-time, and delivery-accuracy history are not yet available. Risk explicitly reports those data limitations and should be recalibrated after labelled outcomes are collected.

### Security and integrity checks

- Credential login uses HTTP-only access/refresh cookies; public registration always creates a customer account.
- Legacy catalog sync is idempotent by product/variant business keys and migrates the complete seller-offer set.
- Run `uv run --python 3.13 python scripts/smoke_rebuild_security.py` from the repository root while the API is running to verify catalog counts, duplicate prevention, real offer filters, forced-customer registration, and cookie login.

On first boot, FastAPI tries to import categories, products, and variants from `backend/db.sqlite3`. If that file is unavailable, it falls back to demo catalog data.

## Run With Docker

1. Copy `.env.example` to `.env` if you want to override defaults.
2. Start the new stack:

```bash
docker compose up --build
```

3. Use these URLs:

- Next.js app: `http://localhost:3000`
- FastAPI API: `http://localhost:8000`
- FastAPI docs: `http://localhost:8000/docs`
- PostgreSQL: `localhost:5432`

The Docker setup mounts `./backend` read-only into the API container so the FastAPI service can import the old Django catalog and serve `backend/media`.

## Local Dev Notes

- One-shot local launcher: `run-rebuild-local.cmd`
- Smoke test: `python scripts/smoke_rebuild.py`
- Next.js local helper: `apps/web-next/run-local.cmd`
- FastAPI local helper: `services/catalog-service/run-local.cmd`

The default local pairing is:

- Next.js on `3001`
- FastAPI on `8001`

## Supply Chain AI Dataset

`Data/supply_chain_data.csv` is imported automatically by the FastAPI startup seed layer. Rows are exposed as catalog products such as `Haircare SKU0`, with dataset-backed suppliers, stock levels, MOQ, origin prices, inspection-derived supplier quality, and recommendation offers.

Local dev uses `CATALOG_SUPPLY_CHAIN_CSV_PATH=..\..\Data\supply_chain_data.csv` from `services/catalog-service/run-local.cmd`. Docker mounts `./Data` read-only and uses `/data/supply_chain_data.csv`.

## Suggested Next Phases

1. Move auth into FastAPI and add Next.js session flow.
2. Replace `create_all()` with Alembic migrations.
3. Migrate quote/order/admin UI from the old frontend into Next.js route by route.
4. Replace generated offer heuristics with real sourcing and pricing rules from the legacy system.
