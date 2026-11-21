# OGLOS Staff Management System

OGLOS makes non-clinical hospital work (cleaning, for a start) **provable**. Every job belongs to a **desk**
(for example "Housekeeping Floor 2"), has a deadline, needs a **before and after photo** taken in the app, and
is **approved by a supervisor**. Late work goes to the supervisor and then the MD. The MD sees the whole building
on one screen.

There are two apps:

| App | Who uses it | Where it runs |
|---|---|---|
| **Admin site** | MD, admin, supervisor | laptop / desktop browser |
| **Staff app** | housekeeping staff | phone browser (can be "installed" like an app) |

This version is a **prototype** with made-up demo data (the "Sunrise Multispeciality" hospital).
No real staff or patient data belongs in it.

> **Just want to try it?** Start it (section 3A), then follow **[TESTING.md](TESTING.md)**: every login and a
> step-by-step walkthrough for each role.

---

## 1. What you need on this computer (one time)

| Install | Why | Check it works (in PowerShell) |
|---|---|---|
| **Docker Desktop** | runs the database, Redis and storage | `docker --version` |
| **Python 3.12** + **uv** | runs the server | `uv --version` |
| **Node.js 22+** + **pnpm** | builds the two apps | `pnpm --version` |

**Start Docker Desktop before anything else.** Most "it doesn't start" problems are Docker not running.

## 2. First-time setup (one time)

Open PowerShell in the project folder (`E:\healthcare_staff_management_system`) and run:

```powershell
python scripts\make-env.py          # creates .env with private random keys (never share or commit it)
powershell -ExecutionPolicy Bypass -File scripts\dev.ps1 dev       # starts database, Redis, storage
powershell -ExecutionPolicy Bypass -File scripts\dev.ps1 migrate   # creates the database tables
powershell -ExecutionPolicy Bypass -File scripts\dev.ps1 seed      # adds the demo hospital, prints the logins
pnpm install                                                        # downloads the app libraries
```

> `make-env.py` will **not** overwrite an existing `.env`. That file holds the keys the database was set up with;
> replacing it locks you out of the local database.

---

## 3. Run it

There are two ways. For showing the prototype, use **A**.

### A. The "Render version" (one command, what you'll put online)

```powershell
powershell -ExecutionPolicy Bypass -File scripts\run-render-local.ps1
```

It builds everything into one package, starts it, and prints the logins. Then open:

- Admin site: **http://localhost:10000**
- Staff app: **http://localhost:10000/staff/**

Add `-Fresh` to wipe this copy's demo data and start again. Stop it with `docker stop oglos-render-test`.

### B. The development version (for changing the code)

Open **three** PowerShell windows in the project folder:

```powershell
# window 1: the server
cd apps\api; uv run uvicorn app.main:app --port 8000
# window 2: the admin site  → http://localhost:5173
pnpm dev:admin
# window 3: the staff app   → http://localhost:5174
pnpm dev:pwa
```

Stop each with `Ctrl + C`.

---

## 4. Test users

Full list and walkthroughs: **[TESTING.md](TESTING.md)**. The logins are fixed (the same after every reset):

| Role | Where | Login |
|---|---|---|
| **MD** | admin site | `md@sunrise.example.org` / `sunrise-demo-2026` + code from `python scripts/demo-code.py md` |
| **Admin** | admin site | `admin@sunrise.example.org` / `sunrise-demo-2026` + code from `python scripts/demo-code.py admin` |
| **Supervisor** | admin site | `supervisor@sunrise.example.org` / `sunrise-demo-2026` |
| **Staff** | staff app | *Use the shared phone and PIN* → device key `SUNRISE-DEMO-SHARED-PHONE-01` → `HK-101` … `HK-106`, PIN `4826` |

Hospital code everywhere: `SUNRISE`.

## 5. Where do the email sign-in codes go?

**Nowhere yet.** No email service is connected, so codes are **printed in the server log** instead of emailed:

- version A: `docker logs oglos-render-test --tail 15`
- version B: in window 1 (the server)

You'll see `Your OGLOS sign-in code is 482613`. In the real deployment codes go to the person's inbox
(AWS SES), and the server refuses to start in "print" mode.
MD and admin codes are **never sent**: the authenticator app makes them.

## 6. A 5-minute demo

1. **Staff (phone-sized window):** sign in with `HK-101` / `4826`, accept the data notice, check in with the
   entrance QR, open a task.
2. *Start task* → **before photo** → tick the checklist → **after photo** → *Send for approval*.
   (On a laptop the photo button opens a file picker; on a phone it opens the camera.)
3. **Supervisor:** *Approvals*: compare before/after, then **Approve** or **Send back** with a note.
4. Back on the staff app: the sent-back task shows the note and needs **new** photos.
5. **MD:** *Today*: tasks done, overdue, awaiting approval, and the building floor by floor.

Sign out between roles (top right), or use a private window for the second person.

## 7. Everyday tasks

| I want to… | Do this |
|---|---|
| Reset the demo data (B) | `$env:SEED_RESET=1; powershell -ExecutionPolicy Bypass -File scripts\dev.ps1 seed; Remove-Item Env:SEED_RESET` |
| Reset the demo data (A) | `powershell -ExecutionPolicy Bypass -File scripts\run-render-local.ps1 -Fresh` |
| Stop everything | `Ctrl + C` in the windows, `docker stop oglos-render-test`, then `powershell -ExecutionPolicy Bypass -File scripts\dev.ps1 down` |
| See the screens without running anything | `docs/screens/phase1/` (screenshots) |
| Check the audit trail hasn't been tampered with | `cd apps\api; uv run python -m app.audit.verify` |

## 8. When something doesn't work

| Problem | Fix |
|---|---|
| "Cannot connect to Docker" | Start Docker Desktop and wait for it to say *running*. |
| Port already in use (5173, 5174, 8000, 10000) | Something is already running there; close the old window or `docker stop oglos-render-test`. |
| The board says *Loading…* the first time | The first page load builds a cache. Refresh after a few seconds. |
| MD/admin code rejected | Codes last 30 seconds; generate a fresh one. The computer clock must be correct. |
| "Too many tries" | Sign-in is rate-limited. Wait 15 minutes, or reset the demo data. |
| "Password authentication failed" for the database | `.env` was replaced or edited. Restore it, or ask a developer to reset the local database passwords. |
| Computer is slow / processes stop | Close other apps. Run only version A for demos. |

## 9. Putting the prototype online

- **Prototype on Render** (free, demo data only): follow **`docs/deploy-render.md`**. In short: Render → *New →
  Blueprint* → pick this GitHub repo → paste two keys → deploy → copy the logins from Render's *Logs* tab.
  Render has no India region, so **never put real hospital data there**.
- **Real deployment** (Olympus and later): AWS Mumbai, following **`docs/deploy.md`**.

## 10. What's built and what's next

**Built:** logins and roles · desks, floors, branches, roster · daily and one-time tasks with checklists ·
before/after photo proof (camera only, server time, watermark) · supervisor approval and send-back ·
fake-work flags · late-task escalation to supervisor then MD · MD dashboard · entrance QR check-in ·
staff data notice · export and erase a person's data · 90-day photo clean-up · tamper-proof audit trail ·
English, Kannada, Hindi.

**Next (from the product plan):** "Going out" desk cover · leave and shift swaps · notices · reports
(Excel/PDF) · spot inspections · voice instructions · offline mode · Pro and Premium features (smart door QR,
rotating QR, star of the week, 3D building, NABH registers).

**Before real use:** native-speaker check of Kannada/Hindi, lawyer review of the staff notice, a named
data-protection contact, hosting in India.

## 11. Where things are

| Path | What's inside |
|---|---|
| `docs/product-plan.md` | what we're building (from your plan PDF) |
| `docs/decisions.md` | every decision made, and why |
| `docs/open-questions.md` | what's still needed from you |
| `docs/reviews/` | security and privacy review results |
| `docs/deploy-render.md`, `docs/deploy.md` | putting it online |
| `apps/api` | the server (Python) |
| `apps/web-admin`, `apps/staff-pwa` | the two apps (React) |
| `packages/i18n` | all screen text in English, Kannada and Hindi |
| `CLAUDE.md` | rules for anyone (or any AI) working on the code |

<details>
<summary>For developers: checks before committing</summary>

```bash
make lint && make test        # or: powershell -File scripts\dev.ps1 lint / test
# ruff, mypy, pytest (59 API tests incl. cross-hospital isolation), eslint, tsc, vitest
node e2e/screens-staff.mjs    # screenshot walk-through (needs STAFF_DEVICE_KEY)
node e2e/screens-admin.mjs    # needs MD_TOTP and ADMIN_TOTP from the seed output
```
Security issues: see `SECURITY.md`.
</details>
