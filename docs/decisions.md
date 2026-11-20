# OGLOS: Product decisions

Answers to `docs/QUESTIONS_BEFORE_BUILD.md`, recorded 2026-11-20.
Where these differ from `docs/BUILD_PROMPT.md`, **this file wins** (see "Changes to the spec" below).

## Guiding principle: a configurable platform, not a single-hospital build
There is no fixed pilot hospital. Build a **general platform where every hospital configures its own setup**:
buildings, floors, areas, area types, departments, roles, shifts, checklists, SLA levels, escalation chains,
inspection sampling rates, evidence rules, retention periods, languages and enabled modules.
Business-rule numbers below are **defaults applied to a new hospital**, editable by the hospital admin.
Demo and seed data: synthetic "Sunrise Multispeciality, Bengaluru" (~100 beds).

## A. Product & customer
| # | Decision |
|---|---|
| 1 | No pilot yet. Generic and configurable; demo with the synthetic Sunrise hospital. |
| 2 | Buyer is the **MD/Owner**. The management overview (SLA compliance, scorecards, trends) must look best in the demo. |
| 3 | **Housekeeping** leads the demo. |
| 4 | **Mixed** staffing: in-house + agency staff + AMC vendors. Model `employment_type` and `agency_id`/`vendor_id`. |
| 5 | Pricing: **flat per hospital + per-module add-ons**. Modules need per-hospital on/off switches (no billing in the app). |

## B. Brand & media
| # | Decision |
|---|---|
| 6 | Use the existing PNGs in `/media` for now; the user will provide SVGs later. Keep the asset pipeline swappable. |
| 7 | Extract exact brand colours from the logo PNGs (deep green + gold). |
| 8 | Light theme for the app; dark theme only for the wall-TV operations board. |
| 9 | Domain: `app.oglos.site` (configurable via env). |

## C. People & devices
| # | Decision |
|---|---|
| 10 | **Both**: own phone with own login, and shared supervisor devices. Configurable per hospital. |
| 11 | Languages: **English, Kannada, Hindi**. i18n must allow more languages later. |
| 12 | (Default) Low-end Android + Chrome. |
| 13 | Login: **Email OTP** (6 digits) for staff with email; **PIN on an admin-registered shared device** as the fallback for staff without email. Admins/managers/vendors: email + password + TOTP 2FA (admin/manager roles). |

## D. Workflows
| # | Decision (default, editable per hospital) |
|---|---|
| 14 | Housekeeping: **QR scan at start and end; photo evidence on every task**. Configurable per area type. |
| 15 | Supervisor verifies; **100% of high-risk areas + 20% random sample** of the rest. |
| 16 | Failed inspection → **automatic re-clean task and an effect on the worker's score**. |
| 17 | Maintenance SLA: Critical 30 min response / 4 h fix · High 2 h / 24 h · Normal 8 h / 72 h. |
| 18 | Vendors get their own **limited login (vendor portal)**. |
| 19 | Escalation: **worker → supervisor → department head → operations manager**; times per level configurable. |
| 20 | Notifications: **in-app + web push, and email**. No SMS/WhatsApp in v1; keep the provider adapter interface so they can be added. |
| 21 | Public QR: **optional phone number** with an explicit consent checkbox and a short notice. |

## E. Data, security & compliance
| # | Decision |
|---|---|
| 22 | **Standalone** v1; manual "patient discharged" button triggers bed cleaning. |
| 23 | Retention defaults: photos **18 months**, audit logs **3 years**, deactivated staff **1 year** after exit. |
| 24–25 | **AWS ap-south-1 (Mumbai)**, SaaS only, no on-prem. |
| 26 | Data-protection / security-incident contact: **placeholder (TODO)**. Must be filled in before go-live; tracked in open-questions. |
| 27 | Yes, a lawyer will review ToS / DPA / privacy notices; templates are marked "DRAFT — for legal review". |

## F. Team & timeline
| # | Decision |
|---|---|
| 28 | Solo founder + Claude Code. |
| 29 | No fixed demo date; work through the phases in order. |
| 30 | No accounts yet (domain DNS, AWS, email provider). Build with **mock/console providers** (console email, local MinIO) behind adapters. |

## Changes to the spec (BUILD_PROMPT.md)
- **Auth (§7):** worker phone + SMS OTP is replaced by **email OTP** (same rules: 6 digits, 5-min expiry, max 5 attempts,
  rate-limited by email and IP, lockout with backoff) + **shared-device PIN**. Phone number becomes an optional staff field
  (still field-level encrypted and masked when stored).
- **Notifications (§3.6):** the email channel is added; WhatsApp/SMS are deferred (adapter interface only).
- **Housekeeping evidence:** photo required on every task by default (the spec said high-risk only).
- **Configurability:** all business rules above are per-hospital settings with these defaults, not hard-coded values.
