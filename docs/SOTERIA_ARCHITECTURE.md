# Soteria — Architecture (Horizon 1)

## Stack decisions (frozen for Horizon 1; do not relitigate during build)

- Backend: FastAPI (Python 3.11+)
- Database: PostgreSQL 15
- Object storage: Cloudflare R2 (S3-compatible)
- LLM: Anthropic Claude API (Sonnet for production, Opus for evaluation only)
- PDF text extraction: pdfplumber (primary), Google Document AI (fallback)
- Auth: Magic-link email, via Resend
- Frontend: Next.js 14 (App Router) + Tailwind + shadcn/ui
- Hosting: single Hetzner CPX21 VPS for backend (€8/mo);
  Vercel free tier for frontend; R2 for storage.
- Deployment: Docker Compose on the VPS, Caddy as reverse proxy
  with automatic Let's Encrypt.

## Why these choices

Single VPS over Kubernetes: at this user volume, complexity has no
payoff. Migrate later if needed.

Postgres over a managed DB service: Postgres on the same VPS, with
nightly backups to R2, is fine for the data sizes involved. Saves
~₹2K/month and one external dependency.

Claude over self-hosted: at this stage, the per-analysis cost is
trivial and the quality difference matters. See PRODUCT_SPEC for
when we revisit this (Horizon 3, conditional on traction).

Next.js + Vercel over a custom React SPA: faster to ship, server-
side rendering for shareable analysis links, free tier covers
Horizon 1 traffic.

## Database schema (PostgreSQL)

```sql
CREATE TABLE users (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  email TEXT NOT NULL UNIQUE,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  deleted_at TIMESTAMPTZ NULL,
  consent_to_training BOOLEAN NOT NULL DEFAULT FALSE,
  consent_given_at TIMESTAMPTZ NULL
);

CREATE TABLE magic_links (
  token TEXT PRIMARY KEY,
  email TEXT NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  expires_at TIMESTAMPTZ NOT NULL,
  consumed_at TIMESTAMPTZ NULL
);

CREATE TABLE policies (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  uploaded_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  filename TEXT NOT NULL,
  file_size_bytes BIGINT NOT NULL,
  page_count INT NULL,
  r2_key TEXT NOT NULL,
  ocr_method TEXT NULL,                -- 'pdfplumber' | 'document_ai'
  extracted_text_r2_key TEXT NULL,
  extraction_status TEXT NOT NULL DEFAULT 'pending',
  deleted_at TIMESTAMPTZ NULL
);

CREATE TABLE analyses (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  policy_id UUID NOT NULL REFERENCES policies(id) ON DELETE CASCADE,
  schema_version TEXT NOT NULL,
  prompt_version TEXT NOT NULL,
  model_name TEXT NOT NULL,             -- e.g. 'claude-sonnet-...'
  analysis_json JSONB NOT NULL,
  raw_llm_response TEXT NOT NULL,        -- store the raw response too
  generation_started_at TIMESTAMPTZ NOT NULL,
  generation_completed_at TIMESTAMPTZ NOT NULL,
  llm_input_tokens INT NULL,
  llm_output_tokens INT NULL,
  llm_cost_usd NUMERIC(10, 6) NULL,
  status TEXT NOT NULL                   -- 'success' | 'failed' | 'partial'
);

CREATE TABLE corrections (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  analysis_id UUID NOT NULL REFERENCES analyses(id) ON DELETE CASCADE,
  user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  field_path TEXT NOT NULL,              -- JSONPath into analysis_json
  original_value JSONB NOT NULL,
  corrected_value JSONB NULL,
  correction_type TEXT NOT NULL,         -- 'incorrect' | 'missing' | 'not_a_concern' | 'severity_wrong'
  user_note TEXT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE analysis_events (
  id BIGSERIAL PRIMARY KEY,
  analysis_id UUID NOT NULL REFERENCES analyses(id) ON DELETE CASCADE,
  user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  event_type TEXT NOT NULL,              -- 'viewed' | 'expanded_field' | 'shared' | 'red_flag_dismissed'
  event_data JSONB NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_policies_user ON policies(user_id) WHERE deleted_at IS NULL;
CREATE INDEX idx_analyses_policy ON analyses(policy_id);
CREATE INDEX idx_corrections_analysis ON corrections(analysis_id);
```

The `corrections` and `analysis_events` tables exist from day one.
They are the data flywheel. Without them, the eventual model
training in Horizon 3 has no labeled data to work with.

## Backend endpoints
POST   /auth/request-magic-link      { email }
GET    /auth/consume?token=...
POST   /auth/logout
GET    /me
DELETE /me                            -- triggers full data deletion
PATCH  /me/consent                    { consent_to_training: bool }
POST   /policies                      multipart upload, returns policy_id
GET    /policies                      list user's policies
GET    /policies/{id}
DELETE /policies/{id}
POST   /policies/{id}/analyze         triggers analysis if not present
GET    /analyses/{id}                 returns analysis JSON
POST   /analyses/{id}/corrections     submit a correction
POST   /analyses/{id}/events          log a UI event (rate-limited)

## Async job processing

Analysis is async because it takes 30–90s. Use a simple approach:
ARQ (Python Redis-based job queue) or even a Postgres-backed queue
like Procrastinate. Don't reach for Celery; the operational overhead
isn't worth it at this scale.

Job pipeline for an uploaded policy:
1. extract_text_job (pdfplumber → fallback Document AI)
2. analyze_policy_job (chunk if needed, send to Claude, parse, store)
3. notify_user_job (frontend polls; no email needed in Horizon 1)

Each job records its own row with status. Failures are retryable
manually via admin endpoint.

## Frontend structure (Next.js App Router)
app/
layout.tsx
page.tsx                          -- landing page
login/page.tsx                    -- magic link request
auth/callback/page.tsx            -- magic link consumption
app/
layout.tsx                      -- authed layout
page.tsx                        -- dashboard / list of analyses
upload/page.tsx                 -- upload flow
analyses/[id]/page.tsx          -- the main analysis view
privacy/page.tsx
terms/page.tsx
components/
AnalysisView/
SummaryCard.tsx
CoverageSection.tsx
WaitingPeriodsSection.tsx
SubLimitsSection.tsx
ExclusionsSection.tsx
RedFlagsSection.tsx             -- the most important component
SourceClauseExpander.tsx
CorrectionButton.tsx
Upload/
UploadDropzone.tsx
UploadProgress.tsx
lib/
api.ts                            -- typed fetch wrappers
schema.ts                         -- TS types matching annotation schema

The annotation schema must be the single source of truth: generate
TypeScript types from it (use `quicktype` or hand-maintain in lockstep).
Both Python backend and TS frontend reference the same schema.

## Prompt versioning

`prompts/` directory in the backend repo:
prompts/
v1/
extract_policy.md         -- the main extraction prompt
system.md                 -- system instructions
schema.json               -- output schema for the LLM
v2/
...

Every prompt change increments the version. The version is stored
on every analysis row. When a regression is detected, you can roll
back by routing new analyses to the previous prompt version while
investigating.

## Local development

`docker-compose.yml` brings up: Postgres, Redis, the backend, and
Caddy. Frontend runs separately with `pnpm dev`. The R2 bucket and
LLM API are real (no mocking) but pointed at dev credentials.

A `seed/` script loads 10 sample annotated policies for development.

## Observability

For Horizon 1, keep this minimal:
- Backend: structured logging via `structlog`, written to file and to stdout
- Sentry for backend exceptions (free tier)
- A single admin dashboard at `/admin` (basic auth) showing:
  total users, total analyses, failed analyses, recent corrections,
  daily LLM cost
- No APM, no tracing, no Prometheus/Grafana. Save it for Horizon 2.

## Security baseline

- All endpoints require auth except landing page, magic link request,
  privacy/terms.
- File uploads validated: PDF magic bytes, max 25MB, max 100 pages.
- Rate limiting per user (5 analyses per day, 60 events per minute).
- R2 bucket private; all access via signed URLs.
- Postgres connection over SSL only.
- Backend secrets via .env, never committed.
- Anthropic API key has spend limit set on Anthropic dashboard.

## Deletion guarantee

When a user requests deletion (or hits DELETE /me):
1. Mark user as deleted_at in DB
2. Background job: delete all R2 objects for that user
3. Background job (24h delay): hard-delete all DB rows
4. Confirmation email when complete

Implement this from week 1. Retrofitting deletion is much harder.

