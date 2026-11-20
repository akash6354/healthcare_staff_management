# CLAUDE.md — OGLOS Hospital Operations & Accountability Platform

> Claude Code reads this file automatically at the start of every session. Keep it short and current.
> Full product spec: `/docs/BUILD_PROMPT.md`. Decisions: `/docs/decisions.md`.

## What this is
OGLOS Hospital Operations & Accountability Platform: a multi-tenant B2B SaaS for private hospitals in India (50–150 beds).
It turns every **non-clinical** job (cleaning, repairs, equipment upkeep, cross-department requests) into a tracked task with an
owner, a deadline, proof, verification and automatic escalation. Built by Oglos (oglos.site).

## Hard rules (never break)
1. **No patient data, ever.** No patient names, MRNs, diagnoses or clinical notes in any table, log, photo caption or seed file.
2. **Tenant isolation.** Every tenant table has `hospital_id` + PostgreSQL RLS. Every new endpoint gets a cross-tenant test.
3. **Evidence is immutable.** Use server timestamps only. Submitted evidence and audit events are never updated or deleted; corrections are new events.
4. **Task state changes go through the state machine service.** Never set `task.status` directly.
5. **No secrets in code or git.** Use env vars; update `.env.example`.
6. **Every staff-facing string goes through i18n** (en, kn, hi).
7. **Migrations are reversible**, and applied migrations are never edited.
8. **Ask, don't invent** business rules. Add unknowns to `/docs/open-questions.md`.
9. **Don't add a dependency without a one-line justification** in the PR/commit message, and prefer MIT/BSD/Apache licences. **Never add GPL/AGPL code.**

## Key decisions (full list: `/docs/decisions.md`, which overrides BUILD_PROMPT)
- Generic, configurable platform: every business rule is a per-hospital setting with a default, never hard-coded.
- Login: email OTP for staff; PIN on admin-registered shared devices; password + TOTP for admins/managers/vendors.
- Notifications: in-app + web push + email (SMS/WhatsApp adapters stubbed only). Hosting: AWS ap-south-1.

## Stack
- API: Python 3.12, FastAPI, SQLAlchemy 2 (async), Alembic, Pydantic v2, PostgreSQL 16, Redis 7
- Jobs: Celery worker + beat (recurring tasks, SLA timers, escalations, notifications)
- Web: React + TypeScript + Vite, TanStack Query, React Router, Tailwind, shadcn/ui (fully themed), react-hook-form + zod
- Apps: `apps/web-admin` (desktop), `apps/staff-pwa` (mobile PWA, offline queue, camera, QR)
- Storage: S3-compatible (MinIO locally), private bucket, signed URLs
- Deploy: Docker Compose + Caddy on an Indian-region VPS

## Repo layout
```
apps/api/            FastAPI app (app/modules/<module>/{models,schemas,service,router}.py)
apps/worker/         Celery tasks
apps/web-admin/      React admin dashboard
apps/staff-pwa/      React mobile PWA
packages/ui/         shared design tokens + themed components
packages/i18n/       translations (en, kn, hi)
infra/               docker-compose, Caddyfile, backup scripts
media/               OGLOS brand assets (logos, icons, fonts): read-only source of truth
docs/                spec, architecture, data model, API, decisions, security, compliance
```

## Commands
```
make dev          # docker compose up (api, worker, beat, postgres, redis, minio, caddy)
make test         # backend + frontend tests
make lint         # ruff, mypy, eslint, prettier --check
make migrate      # alembic upgrade head
make seed         # demo hospital "Sunrise Multispeciality, Bengaluru" (synthetic data)
make e2e          # Playwright
```

## Brand & UI
- Product name in UI: **OGLOS** with the subtitle "Hospital Operations & Accountability Platform".
- Logos/colours/fonts come from `/media`. Extract exact colours from the logo files; don't invent a palette.
  Default direction: deep green primary with a restrained gold accent, warm-neutral greys.
- Use the **`frontend-design`** skill for every screen and the **`dataviz`** skill for every chart, status display or scorecard
  (validate palettes with its script). `/docs/ui-direction.md` holds the agreed tokens and layouts. No Inter/Roboto/Arial, no purple gradients,
  no glassmorphism, no default-shadcn look. Use semantic status colours plus icons everywhere.
- After building or changing a screen: take a Playwright screenshot (desktop 1440px + mobile 390px), critique it against ui-direction.md, fix, then move on.

## How to work in this repo
- Use plan mode for anything touching more than 3 files. Show the plan before coding.
- One phase or feature per session; run `/clear` between unrelated tasks.
- Before finishing any task: `make lint && make test` must pass, docs updated, seed data shows the feature.
- Use the `security-review` and `compliance-check` project skills before marking a phase done.
- Commit small, with clear messages: `feat(housekeeping): ...`, `fix(api): ...`.
