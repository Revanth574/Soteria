# Soteria

Soteria is a Horizon 1 web application for analyzing Indian health insurance
policy PDFs and surfacing claim-time risk areas in plain language.

This repository is a monorepo. The initial scaffold intentionally keeps
implementation folders thin until each task from the working agreement is
picked up in order.

## Repository Layout

```text
soteria/
  backend/        FastAPI service, migrations, jobs, and tests
  frontend/       Next.js 14 App Router application
  prompts/        Revanth-owned prompt versions
  schemas/        Revanth-owned annotation schemas
  corpus/         Gold annotations; source PDFs are never committed
  infra/          Docker, Caddy, and deployment configuration
  docs/           Product, architecture, evaluation, and working docs
  scripts/        One-off operational and evaluation scripts
```

## Local Services

The root Docker Compose file starts the shared local services needed by the
backend:

```powershell
docker compose up -d postgres redis
```

Optional local reverse proxy:

```powershell
docker compose up -d caddy
```

By default, Caddy expects the backend on `host.docker.internal:8000` and the
frontend on `host.docker.internal:3000`. Override those with
`BACKEND_UPSTREAM` and `FRONTEND_UPSTREAM` if needed.

## Environment

Copy `.env.example` to `.env` for local development and fill in real secrets
only on your machine or deployment target. Do not commit `.env` files.

## Project Guardrails

- Policy PDFs are not committed to git.
- `prompts/` and `schemas/` are product-owned areas and should only change
  with explicit approval in the current task.
- Horizon 1 uses the stack frozen in `docs/SOTERIA_ARCHITECTURE.md`.
- User deletion and soft-delete behavior must be preserved by every
  user-data-touching feature.

