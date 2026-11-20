# OGLOS Hospital Operations & Accountability Platform: master build prompt for Claude Code

---

## PART A: Setup checklist (do this yourself before the first prompt)

### A1. Repo and files
```
mkdir oglos-hoap && cd oglos-hoap && git init
mkdir -p docs media
```
- Put this file at `docs/BUILD_PROMPT.md`.
- Put `CLAUDE.md` in the **repo root** (Claude Code loads it automatically every session).
- Put your answers to `QUESTIONS_BEFORE_BUILD.md` in `docs/decisions.md`.
- Put brand assets in `media/`:
  ```
  media/logo/oglos-logo-full.svg       (full colour)
  media/logo/oglos-logo-white.svg      (for dark backgrounds)
  media/logo/oglos-logo-mono.svg
  media/logo/oglos-mark.svg            (icon only)
  media/icons/app-icon-512.png         (PWA icon, square)
  media/fonts/                         (only if you have licensed brand fonts)
  media/design-refs/                   (2–3 screenshots of UIs whose look you like)
  ```
  SVG is best. If you only have PNG, export at 2× or larger.

### A2. Install skills, plugins and MCP servers (run inside Claude Code)
| What | Command | Why |
|---|---|---|
| Frontend Design (official Anthropic) | `/plugin marketplace add anthropics/claude-code` then `/plugin install frontend-design@claude-code-plugins` | Forces a real design direction; avoids the generic AI-made look |
| Anthropic example skills (incl. webapp-testing, skill-creator) | `/plugin marketplace add anthropics/skills` then `/plugin install example-skills@anthropic-agent-skills` | Testing local web apps; creating your own project skills |
| shadcn/ui skill | `npx skills add shadcn/ui` (in a terminal, at the repo root) | Correct component APIs and theming |
| shadcn MCP | `claude mcp add shadcn -- npx shadcn@latest mcp` | Live component docs/registry |
| Playwright MCP | `claude mcp add playwright -- npx @playwright/mcp@latest` | Claude can open the app, click through it and screenshot its own UI |
| Context7 MCP (optional) | `claude mcp add context7 -- npx -y @upstash/context7-mcp` | Up-to-date library docs (FastAPI, SQLAlchemy, TanStack…) |

Restart Claude Code, then run `/mcp` and `/plugin` to confirm everything is loaded.

### A3. How to use Claude Code efficiently on this project
- **One phase per session.** Run `/clear` between phases; CLAUDE.md + `/docs` carry the memory, not the chat.
- **Plan mode first** (Shift+Tab) for anything big. Approve the plan, then let it code.
- **Make it check its own work:** "run make test", "screenshot the screen with Playwright and critique it".
- **Use subagents for parallel or review work:** e.g. "use a subagent to do a security review of the auth module".
- **Use `/compact`** when a session gets long, and **`#`** to add a quick rule to CLAUDE.md.
- **Commit after every green step** so you can roll back cheaply (`git` is your undo button).
- **Review the first 3 screens yourself** and push back hard. Their style carries into every screen after them.

---

## PART B: The prompt (paste everything below this line as your first message)

---

You are the lead engineer, product designer and security engineer for **OGLOS Hospital Operations & Accountability Platform** (OGLOS HOAP), a B2B SaaS built by Oglos (oglos.site).
Read `CLAUDE.md`, `docs/decisions.md` and the contents of `media/` first.
Work in phases. **Do not write application code until I approve Phase 0.** Stop and wait for my approval at the end of every phase.

## 1. Product context

**Customers:** private hospitals in India, starting in Bengaluru, 50–150 beds.

**The problem:** non-clinical work runs on WhatsApp groups, phone calls and paper registers. As a result:
1. Management can't see what is pending, late or done.
2. Registers get signed without the work happening (no proof).
3. Tasks fall between departments, vendors and agencies (no ownership).
4. Problems surface only after a patient complaint or an inspection.
5. AMC vendors and outsourced agencies miss SLAs with no data to hold them accountable.
6. NABH audit documentation is made up by hand before assessments.
7. There is no data on staff performance.

**The solution:** every non-clinical job gets an **owner, a deadline, proof, verification and automatic escalation**, all visible on one screen.

**Never build:** clinical features, EMR, patient identities, billing, pharmacy, inventory/purchasing, payroll, leave management. OGLOS sits alongside the hospital's HMS.

## 2. Core architecture idea: one task engine

All modules are templates on one shared task engine.

**Task sources:** Scheduled (recurring rules) · Requested (staff raise) · Triggered (events, e.g. failed inspection → re-clean, "patient discharged" → bed cleaning) · Reported (public wall QR, no login).

**Lifecycle (server-enforced state machine):**
`created → assigned → accepted → in_progress → submitted → verified → closed`
Branches: `rejected → reassigned`, `on_hold(reason)`, `cancelled(reason)`, and a parallel SLA track `on_time → at_risk → overdue → escalated(level n)`.

Every transition writes an append-only **audit event** `(id, hospital_id, actor_id, actor_role, task_id, from_state, to_state, payload, server_ts, prev_hash, hash)`.

## 3. v1 modules

1. **Org & staff setup:** hospital → buildings → floors → areas (type, risk level: high/medium/low, QR code), departments, staff, roles, shifts/duty roster, shift check-in.
2. **Housekeeping accountability:** cleaning schedules per area, checklists per area type, QR scan start/end, photo evidence, supervisor inspections with scores, random sampling, bed turnaround after discharge, **live area status board** (Clean & verified · Due · In progress · Awaiting inspection · Needs attention · Out of service).
3. **Maintenance management:** complaints → work orders, categories (electrical, plumbing, HVAC, lift, civil, biomedical equipment), basic asset register, preventive maintenance schedules, SLA priorities, vendor assignment, **vendor portal**, vendor SLA reports.
4. **Cross-department requests:** request → accept → handoff → done, with comments, SLA and escalation.
5. **Public QR reporting:** a per-area QR code opens a mobile page with icon choices ("dirty washroom", "no water", "AC not working"…), an optional photo and an optional phone number with consent, which creates a task.
6. **Notifications & escalation:** in-app (web + PWA push), WhatsApp/SMS adapter interface (provider-agnostic; ship a console/mock provider first).
7. **Dashboards & reports:** management overview, department view, scorecards (worker/department/vendor) with trends, SLA compliance, **audit export (PDF/CSV) for NABH documentation**, wall-TV "operations board" mode.

## 4. Roles (RBAC scoped by hospital + department + area)

Platform admin (Oglos) · Hospital admin · Management viewer (MD/COO) · Operations manager · Department head · Supervisor · Worker · Requester (any staff) · Vendor/agency user · Quality/NABH coordinator (read-only audit) · Public reporter (no login).
One user can hold several roles. Permissions live in one policy module with a test matrix (role × action × scope).

## 5. Tech stack (fixed)

- **API:** Python 3.12, FastAPI, SQLAlchemy 2 async, Alembic, Pydantic v2, PostgreSQL 16, Redis 7.
- **Jobs:** Celery worker + beat for recurring task generation, SLA timers, escalations, notifications, retention purges. Timers must be persisted in the DB so they survive restarts.
- **Web:** React + TypeScript + Vite, TanStack Query, React Router, Tailwind, shadcn/ui (fully re-themed), react-hook-form + zod, Recharts or visx for charts.
- **Apps (monorepo, pnpm workspaces):** `apps/web-admin`, `apps/staff-pwa` (Workbox + IndexedDB offline queue, camera capture, QR scanning), `packages/ui` (tokens + components), `packages/i18n` (en, kn, hi).
- **Storage:** S3-compatible, private bucket, signed URLs (MinIO locally).
- **Deploy:** Docker Compose + Caddy (auto HTTPS) on an Indian-region VPS. `make dev` runs everything locally.
- **Quality:** pytest + httpx, Vitest + Testing Library, Playwright e2e, ruff, mypy (strict on services), eslint, prettier, pre-commit, GitHub Actions CI (lint, type-check, test, build, dependency audit, secret scan).

## 6. Brand & UI design (use the `frontend-design` and `shadcn` skills)

**Brand assets:** use the files in `media/`. Copy them into the apps at build time; never modify the originals. Extract the exact brand colours from the logo SVGs and define them as tokens. Default direction: **deep green primary, restrained gold accent, warm-neutral greys.** Gold is for small highlights only, never for large surfaces or body text.

**Name in UI:** "OGLOS" wordmark/logo in the top bar, with the subtitle "Hospital Operations & Accountability Platform" on login, the about page and the PWA splash. Page titles: `<Page> · OGLOS`. PWA name: "OGLOS Ops".

**Feel:** a calm, precise operations control room, closer to airline-ops or logistics software than a marketing site. Information first, dense but readable.

**Avoid (these mark a UI as AI-made):** Inter/Roboto/Arial, purple or blue-purple gradients, glassmorphism, oversized rounded cards everywhere, identical stat-card grids, emoji as icons, big numbers with no context, the default shadcn look.

**Typography:** propose one distinctive, highly legible UI sans (e.g. IBM Plex Sans, Geist or Manrope) plus a monospace for IDs, timestamps and SLA timers. Tabular numerals everywhere. The font must support Kannada and Devanagari (pair with Noto Sans Kannada / Noto Sans Devanagari).

**Colour & status:** one semantic status palette used everywhere, always paired with an icon or shape (colour-blind safe), WCAG AA contrast minimum.

**Signature views:** floor/area grid status board (the hero screen) · live SLA countdowns · task audit-trail timeline · scorecards with sparklines/trends · wall-TV operations board.

**Staff PWA:** icon-first, 48px+ touch targets, one primary action per screen, usable with one thumb, readable in bright light, works on low-end Android, and every label translated.

**Process:** define all design tokens (`packages/ui/tokens.css`) before building screens. Build the first 3 screens (login, area status board, worker task screen), screenshot them at 1440px and 390px with Playwright, critique against this section and `media/design-refs/`, and iterate before continuing. Repeat the screenshot critique for every new screen.

## 7. Security requirements (non-negotiable)

**Tenant isolation**
- `hospital_id` on every tenant table; PostgreSQL **Row-Level Security** with a per-request `SET app.hospital_id`; application-level checks as a second layer.
- Automated cross-tenant tests for every endpoint (read, list, update, delete, file access).

**Authentication**
- Workers: phone + OTP (6 digits, 5-min expiry, max 5 attempts, rate-limited by phone and IP, lockout with backoff). Shared devices: device registration by an admin + a 4–6 digit staff PIN.
- Admins, managers, vendors: password (argon2id, breached-password check, min length 10) + **TOTP 2FA required** for admin/manager roles.
- Short-lived access JWT (≤15 min) + rotating refresh tokens stored hashed, reuse detection, revocation on logout, password change or staff deactivation. Session list with "log out all devices".

**Authorisation**
- Central policy module; deny by default; every endpoint declares required permission + scope. Test matrix in CI.

**Application security (OWASP Top 10 / ASVS L2 as the target)**
- Pydantic validation on all input; parameterised queries only; output encoding; strict CORS; CSRF protection for cookie flows; security headers (CSP, HSTS, X-Content-Type-Options, frame-ancestors, Referrer-Policy).
- Uploads: allow-list MIME + magic-byte check, size limit, image re-encode, EXIF stripped, random object keys, never served from the API domain without signed URLs.
- Rate limiting (Redis) on auth, OTP, public QR and export endpoints; CAPTCHA-less abuse controls for public QR (per-QR and per-IP limits, honeypot field).
- Signed QR tokens (HMAC, per-area, rotatable) so codes can't be forged or enumerated.

**Evidence integrity**
- Server timestamps only; in-app camera capture for evidence (no gallery); watermark (area, time, user); evidence immutable after submit; hash-chained audit log with a verification command (`make verify-audit`).

**Data protection**
- TLS everywhere; encryption at rest (DB volume + bucket); secrets via env/secret manager, never in git; `.env.example` maintained.
- PII minimisation: store only name, phone, role, department, employee ID. No Aadhaar, no home address, no continuous location tracking.
- Field-level encryption for staff phone numbers; phone numbers masked in UI for roles that don't need them.

**Infrastructure**
- Only 80/443 open publicly; DB/Redis/MinIO on a private Docker network; SSH key-only, no root login, fail2ban; unattended security updates; pinned image versions; non-root containers; read-only root filesystems where possible.
- Daily encrypted backups to a separate bucket/region within India, 30-day retention, **monthly restore drill script**.
- Monitoring: health checks, uptime alerts, error tracking (Sentry or GlitchTip), structured JSON logs with request IDs, no PII in logs.

**Secure SDLC**
- CI: `pip-audit`, `pnpm audit`, `gitleaks`, ruff security rules (bandit set), Trivy image scan; Dependabot.
- Create a project skill `.claude/skills/security-review/SKILL.md` that checks a module against this section (authz, tenancy, input validation, upload handling, logging, secrets) and run it before every phase is marked done.
- `SECURITY.md` with a vulnerability-reporting contact.

## 8. Government & regulatory compliance (India)

Build the product so a hospital can comply, and so Oglos complies as their service provider. **Not legal advice: generate templates marked "DRAFT — for legal review".**

**8.1 Digital Personal Data Protection Act 2023 + DPDP Rules 2025**
- Roles: the hospital is the **Data Fiduciary**; Oglos is the **Data Processor**. Reflect this in the DPA template.
- Main obligations apply from May 2027; build them in now:
  - **Notice:** in-app privacy notice for staff (what is collected, why, retention, rights, grievance contact), shown at first login and versioned; acknowledgement recorded. Public QR page shows a short notice before an optional phone number is collected, with an explicit consent checkbox.
  - **Purpose limitation & minimisation:** each personal-data field documented in `docs/compliance/data-inventory.md` (field, purpose, legal basis, retention, who can see it).
  - **Retention & erasure:** configurable per hospital (defaults from decisions.md); scheduled purge jobs; erasure of a deactivated user's personal data while preserving anonymised audit records ("Staff #1234").
  - **Data principal rights:** admin tools to export a user's data (JSON/CSV), correct it and erase it; grievance contact shown in the app.
  - **Security safeguards:** §7, documented in `docs/compliance/security-controls.md`.
  - **Breach handling:** breach register table + workflow: detect → contain → assess → notify the hospital (fiduciary) without delay so they can inform the Data Protection Board and affected people → post-mortem. Template notification text.
  - **Children's data:** not applicable (staff only; no patient data). State this explicitly.
  - **Cross-border:** all data and backups hosted in India by default.

**8.2 CERT-In Directions (April 2022, under IT Act s.70B)**
- Logs of all ICT systems retained for a rolling **180 days** and stored in India; synchronise clocks with NTP (use the NIC/NPL time servers or the cloud provider's NTP).
- **Incident response playbook** `docs/compliance/incident-response.md`: reportable incident types, a **6-hour reporting** checklist to CERT-In, roles, contact list, evidence preservation, hospital notification.

**8.3 IT Act 2000 & SPDI Rules 2011 (s.43A reasonable security practices)**
- Document security practices aligned to ISO/IEC 27001 controls (a mapping table, not certification) in `docs/compliance/iso27001-mapping.md`.

**8.4 Labour Codes (effective 21 Nov 2025)**
- OGLOS is not the employer, but its records may be used in wage/contractor disputes: keep attendance/shift/task records accurate, tamper-evident and exportable. Distinguish employer vs contractor/agency staff in the data model (`employment_type`, `agency_id`).
- No continuous GPS tracking or covert monitoring; location captured only at the moment of a QR scan, and disclosed in the notice.

**8.5 Hospital standards supported (not "certified by OGLOS")**
- **NABH** (Facility Management & Safety, Hospital Infection Control chapters): checklist templates and audit exports that support documentation.
- **Bio-Medical Waste Management Rules 2016**: collection/segregation log template (phase 2).
- **Fire safety**: extinguisher/hydrant inspection templates (phase 2).
- UI copy must say "supports NABH documentation", never "NABH compliant".

**8.6 Accessibility & consumer-facing**
- WCAG 2.1 AA for web; GIGW-friendly practices for public QR pages.

**8.7 Commercial/legal templates (DRAFT, for legal review)** in `docs/legal/`:
Terms of Service · Data Processing Agreement (hospital ↔ Oglos) · Staff Privacy Notice · Public QR Privacy Notice · SLA & Support Policy · Sub-processor list (cloud, SMS/WhatsApp, error tracking).

Create a project skill `.claude/skills/compliance-check/SKILL.md` that checks new features against §8 (new personal-data fields documented? retention set? notice updated? logs free of PII?), and run it before each phase is marked done.

## 9. Phased plan (stop for my approval after each)

**Phase 0: Plan (no code).** Create in `docs/`:
`architecture.md` (components, data flow, tenancy, jobs/timers) · `data-model.md` (Mermaid ERD, indexes, RLS policies) · `api.md` (endpoints by module + permissions) · `state-machine.md` · `ui-direction.md` (tokens, type scale, palette from `media/`, key screen wireframes in words) · `security.md` · `compliance/data-inventory.md` · `open-questions.md`.
Also create the two project skills (`security-review`, `compliance-check`) and a `new-module` skill describing how to add a module (model → migration → service → router → policy → tests → UI → i18n → seed → docs).

**Phase 1: Foundation.** Monorepo, Docker Compose, Makefile, CI, auth (OTP, password + TOTP, refresh tokens), tenancy + RLS + cross-tenant tests, RBAC policy module, org/staff/areas setup, audit log with hash chain, i18n scaffold, design tokens + app shells with the OGLOS brand, seed for the demo hospital "Sunrise Multispeciality, Bengaluru" (synthetic).

**Phase 2: Task engine.** Tasks, state machine, assignment rules (area + department + shift), comments, evidence upload pipeline, recurring schedules, SLA timers, escalation chain, in-app notifications, notification provider interface (mock).

**Phase 3: Housekeeping.** Checklists, QR scan flow, inspections + scoring + sampling, live area status board, discharge → bed-cleaning trigger, staff PWA screens with offline queue.

**Phase 4: Maintenance.** Work orders, assets, preventive maintenance, vendors + vendor portal, SLA reports.

**Phase 5: Requests, public QR, dashboards, exports.** Cross-department requests, public reporting page, management/department dashboards, scorecards, NABH-supporting audit export, wall-TV board.

**Phase 6: Compliance & hardening.** DPDP features (notices, rights tools, retention purges, breach register), CERT-In playbook, legal templates, full security-review + compliance-check pass, load test (~3,000 tasks/day per hospital, 10 hospitals), backup/restore drill, production deployment guide, one-page "OGLOS Security & Privacy" sheet for hospitals.

**Every phase ends with:** green CI, updated docs, seed data showing the feature, Playwright screenshots of new screens, security-review + compliance-check results, and a 5-step demo script.

## 10. Working rules

- Follow `CLAUDE.md` hard rules at all times.
- Plan before multi-file changes; small commits; reversible migrations.
- No new dependency without justification; MIT/BSD/Apache only, no GPL/AGPL.
- When unsure about a business rule, ask me or log it in `open-questions.md`. Don't invent it.
- Never put real people's data in seeds or tests.

Start with Phase 0 now: read `CLAUDE.md`, `docs/decisions.md` and `media/`, then produce the Phase 0 documents and project skills, and list your open questions.
