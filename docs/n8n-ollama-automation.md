# n8n and Ollama automation

## Scope

This integration adds an optional AI explanation layer to the deterministic
sourcing recommendation endpoint. FastAPI remains authoritative for prices,
currency conversion, freight, duty, VAT, fees, ETA, risk and ranking. n8n and
Ollama may explain those results but cannot overwrite them.

## Included workflows

- `automation/n8n/workflows/quote-ai-explanation.json` authenticates the API
  webhook, calls the local Ollama generate API with JSON output, bounds the
  returned fields and responds synchronously.
- `automation/n8n/workflows/global-error-handler.json` produces a credential-
  free error summary. Connect a private admin notification destination after
  importing it.

Both workflows are inactive on import. Review them, select the global error
workflow in the quote workflow settings, then activate them deliberately.

## Local start

1. Copy `.env.example` to `.env` and replace `N8N_ENCRYPTION_KEY` and
   `N8N_AUTOMATION_TOKEN`. The webhook token must match
   `CATALOG_AUTOMATION_WEBHOOK_TOKEN`.
2. Start the normal application plus the automation profile:

   ```powershell
   docker compose --profile automation up --build
   ```

3. Pull the configured model once:

   ```powershell
   docker compose --profile automation exec ollama ollama pull qwen3:8b
   ```

4. Open `http://127.0.0.1:5678`, create the local n8n owner, and import both
   JSON workflows from `/workflows`.
5. Configure the quote workflow's error workflow, test it, and activate it.
6. Call either AI explanation endpoint:
   - `POST /api/recommendations/cheapest-country/ai-explanation/` compares
     countries.
   - `POST /api/quote/ai-explanation/` explains one quote and is used by the
     customer quote page.

When n8n, Ollama, authentication, JSON parsing or the network fails, the API
returns `ai_metadata.source=deterministic-fallback`; sourcing remains usable.

## Production requirements

- Run n8n and Ollama on private infrastructure; do not expose Ollama publicly.
- Terminate HTTPS in front of n8n and configure an exact HTTPS webhook URL.
- Generate independent high-entropy webhook and n8n encryption secrets.
- Pin reviewed n8n and Ollama image digests rather than using the development
  `latest` defaults.
- Restrict n8n ingress to the API service where possible.
- Configure execution retention, backups, monitoring and a real error alert.
- Run `n8n audit` after configuration changes and review unprotected webhooks,
  community nodes, Code nodes and unused credentials.
- Never include customer contact, payment proof, credentials or unnecessary PII
  in an LLM prompt.

## Response contract

The API adds:

```json
{
  "ai_explanation": {
    "summary_bn": "...",
    "advantages": [],
    "risks": [],
    "missing_information": [],
    "recommended_checks": [],
    "confidence": 0.78,
    "human_review_required": false
  },
  "ai_metadata": {
    "source": "ollama-via-n8n",
    "automation_available": true,
    "monetary_calculations_are_deterministic": true
  }
}
```

Medium and High deterministic risk can never be downgraded to no-review by the
AI response. Confidence is an AI self-report, not a calibrated probability,
until an evaluated calibration process is added.

## Persistence and human review

When an authenticated customer saves an AI-assisted quote, the API recomputes
the authoritative quote and stores the bounded explanation separately in
`ai_decision_explanations`. The stored record includes the deterministic input
snapshot, provider/model metadata, confidence, prompt version, and review
state. Client-supplied prices or risk levels are never treated as authoritative.

Apply the schema before deploying the updated API:

```powershell
cd services/catalog-service
.\.venv\Scripts\python.exe -m alembic upgrade head
```

Operators and admins can review flagged explanations at `/admin/ai-reviews`.
The supporting endpoints are:

- `GET /api/admin/ai-reviews/?status=PENDING`
- `PATCH /api/admin/ai-reviews/{review_id}/` with an `APPROVED` or `REJECTED`
  decision and a required note.

Each decision stores the reviewer and timestamp and writes an admin audit
event. Approval changes only the explanation's review state; it never changes
the deterministic quote or creates an order.

## Current automation boundary

- Automated: deterministic quote/risk calculation, n8n orchestration, Ollama
  explanation, schema validation, safe fallback, persistence, review routing,
  and audited human approval/rejection.
- Human-owned: activating imported workflows, acting on missing supplier data,
  approving flagged explanations, and final sourcing/payment decisions.
- Not yet automated: supplier outreach, purchase placement, payment execution,
  shipment-provider actions, or autonomous price changes.
