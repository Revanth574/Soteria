# Soteria — Working Agreement with Codex (GPT-5 family, highest reasoning tier)

## Role split

**You (Revanth):** Own the prompt, the annotation schema, the policy
corpus, and the user-facing copy. Personally annotate the gold set.
Make all product decisions. Review every PR Codex opens before merge.

**Codex:** Implements the scaffolding — backend endpoints, database
migrations, frontend components, deployment configuration, tests.
Does NOT modify prompts, the annotation schema, or user-facing copy
without explicit approval.

**Claude (architect role):** Reviews Codex's work for correctness,
helps debug, suggests refactors. Does not write code directly into
the repo unless asked.

## Repository structure

Single monorepo:
soteria/
backend/                 -- FastAPI app
frontend/                -- Next.js app
prompts/                 -- versioned prompts (Revanth-owned)
schemas/                 -- annotation schema (Revanth-owned)
corpus/                  -- annotated gold set (Revanth-owned, gitignored documents, committed annotations)
infra/                   -- docker-compose, Caddy config, deploy scripts
docs/                    -- this document and others
scripts/                 -- one-off scripts (Codex may add here)

## Branching and workflow

- `main` is protected. All changes via PR.
- Codex works on `feature/*` branches.
- Codex never force-pushes, never rebases shared branches, never
  modifies `main` history.
- Every PR includes: description of what changed, what was tested,
  what was NOT tested.
- PR description must call out any change touching `prompts/`,
  `schemas/`, or user-facing copy. These changes require Revanth's
  explicit approval before merge regardless of how Codex got there.

## Hard constraints for Codex

1. Do NOT modify files in `prompts/` or `schemas/` without an
   explicit instruction from Revanth in the current task. If a code
   change seems to require schema modification, stop and ask.

2. Do NOT use a different LLM provider, library, or framework than
   listed in `SOTERIA_ARCHITECTURE.md`. If something seems missing,
   stop and ask before adding.

3. Do NOT add cloud services beyond those listed (Hetzner, R2, Vercel,
   Resend, Anthropic, Sentry). No new SaaS dependencies.

4. Do NOT generate, scrape, or include any policy documents. The
   corpus is curated by Revanth.

5. Do NOT write code that bypasses the deletion guarantee. Every
   user-data-touching feature must respect soft-delete and the
   24-hour hard-delete job.

6. Do NOT commit secrets. Use .env.example with placeholders only.

7. Tests are required for: every backend endpoint (happy path +
   one auth failure path), every database migration (round-trip
   test), the analysis pipeline (with a mocked LLM response).
   Coverage targets are not enforced; behavior coverage is.

8. If a task is ambiguous, stop and ask. Do not make product
   decisions silently.

## Initial task list (in order, one PR per item)

1. Repository scaffolding: monorepo layout, .gitignore, README,
   docker-compose for Postgres + Redis, Caddy config.
2. Backend bootstrap: FastAPI app, /health endpoint, structlog,
   Sentry init (optional via env), Postgres connection via SQLAlchemy
   2.x async, Alembic migrations setup.
3. Database schema migration matching SOTERIA_ARCHITECTURE.md.
4. Auth: magic link request + consume, session cookie, /me endpoint.
5. R2 client wrapper, policy upload endpoint with validation.
6. Text extraction job (pdfplumber primary, Document AI fallback
   stub for now — real Document AI integration in a later task).
7. LLM client wrapper for Anthropic, with retry + token accounting.
   Loads prompt from `prompts/v1/` (Revanth provides the actual
   prompt content; Codex builds the loader).
8. Analysis job: chunk policy text if needed, call LLM, parse JSON,
   validate against schema, store analysis row.
9. Frontend bootstrap: Next.js 14, Tailwind, shadcn/ui, magic link
   pages, dashboard skeleton.
10. Upload UI with progress.
11. Analysis view rendering one section at a time
    (SummaryCard first; iterate per-section).
12. Correction button + endpoint.
13. Analysis events logging.
14. Admin dashboard at /admin.
15. Deletion flow (DELETE /me + background jobs + email confirmation).
16. Deployment: deploy script, Caddy + docker-compose on Hetzner,
    Vercel deployment for frontend.

## Communication protocol

- Codex works in roughly hour-long focused sessions.
- At the start of each session, Codex states which task from the
  list it's picking up and any clarifying questions.
- At the end, Codex summarizes what shipped, what didn't, and what
  needs Revanth's input.
- Mid-session, if blocked on a product decision: Codex stops and
  writes the question to a `BLOCKED.md` file in the PR. Does not
  proceed by guessing.

## What Codex should NOT design

- The annotation schema (Revanth + Claude)
- The extraction prompt (Revanth + Claude)
- User-facing copy beyond placeholder text
- Pricing, feature gating, marketing pages (Horizon 1: the only
  marketing page is the landing page; copy provided by Revanth)
- The red flag catalog
- The evaluation methodology

If Codex finds itself drifting toward any of these, stop.

