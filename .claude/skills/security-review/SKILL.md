---
name: security-review
description: Review an OGLOS module or the pending changes against the project's security requirements (tenancy/RLS, authz policy, auth, input validation, uploads, evidence integrity, logging, secrets, dependencies). Run before marking any phase or feature done.
---

# OGLOS security review

Source of truth: `docs/security.md` and `docs/BUILD_PROMPT.md` §7. Review the target (a module path, or `git diff main...HEAD` if none given).
Read the code; don't assume. For each check, record **PASS / FAIL / N/A** with file:line evidence.

## Checklist

### 1. Tenant isolation
- [ ] Every new table with tenant data has `hospital_id NOT NULL`, a composite FK where it references tenant rows, and `enable_tenant_rls()` in its migration (ENABLE + FORCE).
- [ ] No query uses the `oglos_platform` role/engine outside `modules/platform`.
- [ ] No code path runs tenant queries without `SET LOCAL app.hospital_id` (jobs included).
- [ ] **Every new endpoint has a cross-tenant test** (read, list, update, delete, file URL) expecting 404.

### 2. Authorisation
- [ ] Every route declares `@requires(permission, scope)`. No ad-hoc role string checks in routers.
- [ ] Services re-check scope for ids taken from the request body (not just the path).
- [ ] New permissions were added to `app/policy` **and** the matrix table in `docs/security.md`, and the matrix test covers them.
- [ ] Self-verification is impossible (verifier ≠ assignee) where relevant.

### 3. Authentication & sessions
- [ ] OTP/PIN/password routes are rate-limited and don't reveal whether an account exists.
- [ ] Secrets are compared in constant time; OTPs, PINs and refresh tokens are stored only as hashes.
- [ ] Role change, deactivation and password change revoke sessions.

### 4. Input & output
- [ ] Pydantic models use `extra="forbid"`, length caps and enums; no raw SQL string building.
- [ ] No `dangerouslySetInnerHTML`; user Markdown is sanitised.
- [ ] Error responses use codes plus `message_key`; no stack traces or internal ids of other tenants.

### 5. Uploads & evidence
- [ ] Magic-byte allow-list, size limit, re-encode, EXIF strip, random keys, quarantine prefix.
- [ ] Evidence/audit rows are never UPDATEd/DELETEd (except through the retention SECURITY DEFINER fn); server timestamps only.
- [ ] Task status changes go only through the state machine service (grep for `.status =` on tasks).
- [ ] Audit events are written in the same transaction as the change; payloads contain ids, not names.

### 6. Logging & privacy
- [ ] No names, emails, phones, OTPs, tokens or free text in logs (check `logger.` calls and exception messages).
- [ ] Personal fields that are new use encryption/masking per `docs/compliance/data-inventory.md`.

### 7. Secrets & config
- [ ] No secrets, keys or real credentials in code, tests, seeds or fixtures; new settings are in `.env.example`.
- [ ] Run `gitleaks detect --no-banner` if available.

### 8. Dependencies
- [ ] Each new dependency has a one-line justification in the commit and a permissive licence (MIT/BSD/Apache/ISC/OFL for fonts). **No GPL/AGPL.**
- [ ] `pip-audit` / `pnpm audit` show no high/critical issues (or they are documented).

### 9. Public surfaces
- [ ] Public QR routes: HMAC token validated, per-token + per-IP limits, honeypot, no staff personal data in responses.
- [ ] Security headers/CSP unchanged or tightened.

## Output
A table `check | result | evidence | fix`, then a short list of **blocking** findings (any FAIL in §1, §2, §5 or §7 blocks the phase).
Offer to fix the blocking items; don't silently change unrelated code.
