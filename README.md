# OGLOS Staff Management System

Hospital Operations & Accountability Platform by Oglos (oglos.site). Every non-clinical job gets an owner,
a deadline, photo proof, supervisor approval and automatic escalation. First pilot: Olympus Hospital, Bangalore.

Start here: `CLAUDE.md` (rules), `docs/product-plan.md` (what we're building), `docs/decisions.md`.

## Run the demo locally

Needs Docker, Python 3.12 + [uv](https://docs.astral.sh/uv/), Node 22+ and pnpm. On Windows without `make`,
use `pwsh scripts/dev.ps1 <target>` for the same targets.

```bash
cp .env.example .env          # then replace every change-me / REPLACE value
make dev                      # Postgres 16 (port 5434), Redis 7, SeaweedFS S3 (port 9000)
make migrate                  # alembic upgrade head
make seed                     # demo hospital SUNRISE (synthetic); prints logins + TOTP secrets
pnpm install

cd apps/api && uv run uvicorn app.main:app --port 8000   # API
pnpm dev:admin                                           # web admin  http://localhost:5173
pnpm dev:pwa                                             # staff app  http://localhost:5174
```

**Demo walk-through (5 steps)**
1. Staff app (phone width): *Use the shared phone and PIN* → set up the device with the key printed by `make seed`
   → sign in as `HK-101`, PIN `4826` → read and accept the staff data notice.
2. Check in by scanning the entrance QR (web admin → Entrance QR, shown on a second screen or printed).
3. Open an overdue task → *Start task* → before photo → tick the checklist → after photo → *Send for approval*.
4. Web admin as the supervisor (`supervisor@sunrise.example.org`) → *Approvals*: compare before/after, approve or send back with a note.
5. Web admin as the MD (`md@sunrise.example.org` + TOTP) → *Today*: the building by floor, done / overdue / awaiting approval, open flags.

## Checks

```bash
make lint && make test        # ruff, mypy, pytest (52 API tests incl. cross-tenant), eslint, tsc, vitest
node e2e/screens-staff.mjs    # screenshot walk-through (needs STAFF_DEVICE_KEY)
node e2e/screens-admin.mjs    # needs MD_TOTP and ADMIN_TOTP from the seed output
```

## Layout

```
apps/api         FastAPI + SQLAlchemy + Alembic (+ Celery app); RLS per hospital, audit hash chain
apps/staff-pwa   staff mobile PWA (React, Vite)
apps/web-admin   desktop admin, supervisor and MD screens
packages/ui      design tokens + components    packages/i18n  en / kn / hi    packages/client  API client
infra/           docker compose, Caddy, Postgres roles
docs/            plan, decisions, architecture, data model, API, security, compliance, screenshots
```

Security issues: see `SECURITY.md`.
