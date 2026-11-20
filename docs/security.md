# Security

Target: OWASP ASVS L2. Implements BUILD_PROMPT §7 with the changes in `decisions.md` (email OTP instead of SMS OTP).
Checked before each phase by `.claude/skills/security-review`.

## 1. Threat model (summary)

| Asset | Main threats | Key controls |
|---|---|---|
| Tenant data | cross-hospital read/write through a bug or IDOR | RLS + `FORCE`, composite FKs, policy layer, cross-tenant test per endpoint, 404 on foreign ids |
| Evidence & audit trail | backdating, editing proof, deleting a bad record | server timestamps, in-app camera only, immutable rows + triggers, per-hospital hash chain, nightly verify |
| Staff accounts | OTP brute force, credential stuffing, stolen shared device | rate limits, lockout with backoff, argon2id, TOTP for admins, device registration + PIN, session revocation |
| Public QR | spam, forged QR codes, enumerating areas | HMAC-signed rotatable tokens, per-QR/IP limits, honeypot, no staff data on the page |
| Staff personal data | over-collection, leaks in logs or exports | minimisation, field encryption for phone, masking, PII-free logs, export audit |
| Infrastructure | exposed DB/Redis, stale images, lost backups | private network, 80/443 only, pinned non-root images, Trivy, encrypted off-region backups + drills |

## 2. Authentication

| Who | Method | Rules |
|---|---|---|
| Workers with email (decision 13) | **Email OTP** | 6 digits, CSPRNG, stored as an HMAC hash, 5-min expiry, max 5 attempts per challenge, rate limits: 3 sends / 15 min per email, 10 / 15 min per IP; lockout 15 min → 1 h → 24 h backoff. The response is identical whether or not the email exists. |
| Workers without email | **Shared device + PIN** | Device registered by an admin (device key stored as a hash, revocable). PIN 4–6 digits, argon2id, 5 wrong → user locked on that device + supervisor alert. A PIN works only on a registered device. |
| Admins, managers, vendors | Password + TOTP | argon2id (m=64 MiB, t=3, p=1), min 10 chars, breached-password check (k-anonymity HIBP range API, or an offline list if the network is blocked), **TOTP required** for hospital_admin, ops_manager, management_viewer, dept_head, quality coordinator, platform admin. Recovery codes (10, single use, hashed). |
| Tokens | JWT access ≤15 min (EdDSA, `kid` rotation) + rotating refresh (opaque, 30 days idle / 90 days absolute, stored hashed) | Reuse of a used refresh token → revoke the whole session family + alert. Revoke on logout, password change, role change, deactivation. "Log out all devices". |

## 3. Authorisation

- One policy module: `app/policy/`. A route is `@requires("task.verify", scope=Scope.AREA)`. **Deny by default**: routes without a declaration fail a startup check and CI.
- Scope resolution: hospital ⊃ department ⊃ area; vendor scope = own vendor's tasks; self = assignee/requester.
- Extra rules: a verifier can't verify their own task; vendors never see staff phone numbers; the management viewer is read-only.
- The **test matrix** (`tests/policy/test_matrix.py`) is generated from the table below: every role × permission × scope, allowed and denied.

| Permission | Platform admin | Hospital admin | Mgmt viewer (MD/COO) | Ops manager | Dept head | Supervisor | Worker | Requester | Vendor user | Quality/NABH |
|---|---|---|---|---|---|---|---|---|---|---|
| settings.manage / config.manage | P (support, audited) | H | – | H (config only) | – | – | – | – | – | – |
| org.manage | P | H | – | H | – | – | – | – | – | – |
| staff.manage | P | H | – | H | D | – | – | – | – | – |
| roster.manage | – | H | – | H | D | D/A | – | – | – | – |
| task.view | – | H | H | H | D | A | S | S | V | H |
| task.create | – | H | – | H | D | A | S (requests, complaints) | S | – | – |
| task.assign | – | H | – | H | D | A | – | – | – | – |
| task.verify / inspection.perform | – | – | – | H | D | A | – | – | – | H (spot audits) |
| task.hold / task.cancel | – | H | – | H | D | A | request only | own before accept | – | – |
| board.view | – | H | H | H | D | A | – | – | – | H |
| report.view | – | H | H | H | D | A (team) | own scorecard | – | V (own SLA) | H |
| audit.export | – | H | H | H | – | – | – | – | – | H |
| vendor.manage / asset.manage | – | H | – | H | – | – | – | – | – | – |
| privacy.manage | – | H | – | – | – | – | – | – | – | – |
| breach.manage | P | H | – | – | – | – | – | – | – | – |
| discharge.trigger | – | H | – | H | D | A | – | A (ward staff) | – | – |

(P platform · H hospital · D department · A areas/zone · S self · V own vendor · – denied). A user can hold several roles, and their effective permissions are the union.

## 4. Application security

- Input: Pydantic v2 models with `extra="forbid"`, length caps on all free text, enums for states. SQLAlchemy Core/ORM only (no string SQL).
- Output: React escaping; no `dangerouslySetInnerHTML`; Markdown notices rendered with a sanitiser allow-list.
- Headers (Caddy): `Content-Security-Policy: default-src 'self'; img-src 'self' blob: <bucket host>; connect-src 'self'; frame-ancestors 'none'; object-src 'none'; base-uri 'none'`, HSTS (1 y, preload later), `X-Content-Type-Options: nosniff`, `Referrer-Policy: strict-origin-when-cross-origin`, `Permissions-Policy: camera=(self), geolocation=()`.
- CORS: only the app origins. CSRF: double-submit token on the refresh-cookie route; API calls use bearer tokens (not cookies).
- Rate limits (Redis sliding window): auth, OTP, PIN, public QR (per token + per IP), uploads, exports.
- Uploads: allow-list JPEG/PNG/WebP/HEIC by magic bytes, ≤10 MB, decode + re-encode to JPEG (q≈82, max 2048px), strip all metadata, random object keys, served only through 5-min signed URLs from the bucket domain.
- **QR tokens:** `base64url(hospital_id | area_id | purpose | version) + HMAC-SHA256(key_v, …)[:16]`. Rotation bumps `qr_token_version` (reprint). Keys are versioned in env. Unknown or old tokens get a generic "This code is no longer active".
- Idempotency keys stored 24 h per user (offline replays never double-apply).

## 5. Evidence integrity
Server timestamps only · in-app camera capture (`<input capture>` / getUserMedia; gallery picks are blocked in the UI and EXIF capture times are ignored) · watermark burned in (area code, IST time, staff #) · sha256 stored · immutable after submit · hash-chained `audit_events` · `make verify-audit` and a nightly job.

## 6. Data protection
- TLS 1.2+ everywhere. EBS/RDS volume encryption + SSE on the bucket. Backups encrypted with `age` before upload.
- **Field-level encryption** (AES-256-GCM via `cryptography`, Apache/BSD): `users.phone_enc`, `public_reports.reporter_phone_enc`, `credentials.totp_secret_enc`, `push_subscriptions.keys_enc`. Keys from env (KMS later), with a key id stored per value so keys can rotate.
- Masking: phone shown as `98•••••210` unless the viewer has `staff.manage`.
- Logs: structured JSON, request id, user id, hospital id, **no** names, emails, phones, OTPs, tokens or free text. A log-scrubbing filter plus a test that greps captured logs for seeded PII.

## 7. Infrastructure
Only 80/443 public · Postgres/Redis/MinIO on an internal Docker network · SSH keys only, no root, fail2ban, unattended-upgrades · images pinned by digest, non-root users, read-only root FS where possible · NTP (AWS Time Sync / NPL) · daily encrypted backups to ap-south-2, 30-day retention, `make restore-drill` monthly · health checks + uptime alerts + GlitchTip (self-hosted, MIT) for errors.

## 8. Secure SDLC
CI: ruff (incl. `S` bandit rules), mypy (strict on services), pytest, eslint, prettier, vitest, Playwright, `pip-audit`, `pnpm audit`, `gitleaks`, Trivy, licence check (fail on GPL/AGPL). Dependabot weekly. Pre-commit runs ruff, prettier and gitleaks. `SECURITY.md` has the reporting contact (TODO, decision 26).
