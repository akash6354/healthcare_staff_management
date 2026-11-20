# Security review + compliance check: Phase 1 and Olympus pilot scope (2026-11-20)

Scope: `apps/api` (all modules), `apps/staff-pwa`, `apps/web-admin`, `infra`. Skills: `security-review`, `compliance-check`.
Result: **all blocking items fixed**; remaining items are deployment tasks (listed at the end).

## Automated checks
| Check | Before | After |
|---|---|---|
| `pip-audit` | 5 packages vulnerable (pyjwt, python-multipart, starlette, pillow, cryptography) | no known vulnerabilities |
| `pnpm audit` | 40 (4 critical, 5 high) via vitest/tinypool, vite, postcss, playwright, react-router, glob | no known vulnerabilities |
| `gitleaks` (full history) | — | no leaks |
| Caddy config | — | `caddy validate`: valid |
| Tests | 52 | 57 API (incl. cross-tenant on every endpoint) + i18n parity |

## Security review findings
| § | Finding | Severity | Fix |
|---|---|---|---|
| 2 | `POST /roster` trusted the client's `department_id`; a department manager could roster an outsider or use another department's desk | **Blocking** | user, desk and department all re-checked against the caller's scope; test added |
| 2 | `POST /tasks` (one-time) didn't check the desk was in the supervisor's department | **Blocking** | `desk_in_scope()`; test added |
| 1 | Cross-tenant tests missing for templates, proofs, flags, roster delete, devices, notice ack, QR rotate, privacy | **Blocking** | `test_cross_tenant_on_remaining_endpoints`, privacy tests |
| 8 | Vulnerable dependency versions | **Blocking** | upgraded (see table); FastAPI 0.165 runs yield-dependency teardown after the response, so DB sessions now use `scope="function"` to commit before replying |
| 1 | `audit.verify` used the BYPASSRLS engine outside `modules/platform` | Minor | `platform.service.list_hospitals()` |
| 4 | i18n text fields (template titles, checklist labels) had no length cap | Minor | 200 / 1000 char caps |
| 5 | Upload size enforced only after Starlette buffered the body; Pillow bomb *warning* not treated as error | Minor | Caddy `request_body max_size 15MB`; `DecompressionBombWarning` → error |
| 9 | CSP `img-src` would block signed S3 photo URLs in production | Minor | `{$S3_PUBLIC_ORIGIN}` in CSP; `.env.example` updated |
| — | `/me/tasks` hid open tasks due after midnight (night shifts) | Bug | shows open tasks due in the next 18 h |

**Accepted risks (documented, not fixed):**
- Password login returns `ACCOUNT_LOCKED` for a locked account, which reveals the account exists. Kept so staff understand why sign-in fails; rate limits apply.
- Anyone who knows a staff email can trigger OTP sends (3 per 15 min) and, with the challenge id, burn attempts and cause a temporary lockout. Mitigated by per-email/IP limits and lockout backoff.
- Photos are processed in the API process (no quarantine prefix + worker yet). Re-encode, size and pixel limits apply; move to the worker before multi-hospital scale.

## Compliance check findings
| § | Finding | Fix |
|---|---|---|
| 1 | Free-text fields lacked "Don't enter patient details" | hint on send-back note and task instructions/checklist |
| 2 | Retention configured but not enforced | nightly `oglos.privacy.retention`: full photos deleted after 90 days (thumbnail + record kept, `proof_purges` append-only), leavers anonymised after 12 months |
| 2 | No rights tools | `GET /privacy/users/{id}/export`, `POST /privacy/users/{id}/erase` (anonymise, audit ids kept, chain verified) |
| 2 | Notice didn't mention emergency contact / joining date | default notice updated (en/kn/hi) |
| 7 | Four screen-reader labels hard-coded in English | moved to i18n |
| 6 | NABH wording | pass (test guards it) |
| 5 | No location tracking; attendance append-only | pass |

## Still open (deployment, before go-live)
- CERT-In: central log store with 180-day retention in India; NTP on the server (AWS Time Sync).
- `docs/compliance/incident-response.md` (6-hour CERT-In checklist) and the named contact (open-questions #1).
- Native-speaker review of Kannada/Hindi strings and the staff notice; legal review of the notice.
