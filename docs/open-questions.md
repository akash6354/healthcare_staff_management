# Open questions

Business rules not settled by `decisions.md`. Each has a **working default** used until you answer. Nothing here is invented as final.

| # | Area | Question | Working default |
|---|---|---|---|
| 1 | Compliance | **Named data-protection & security-incident contact** (name, email, phone) for the privacy notice, `SECURITY.md` and CERT-In 6-hour reporting (decision 26). | `TODO` placeholders; **blocks go-live** |
| 2 | Auth | Staff with neither email nor a shared device: should a supervisor be able to complete tasks *on their behalf* (recorded as "by supervisor for Staff #")? | No; every worker needs email or a registered-device PIN |
| 3 | Auth | Which email provider for OTP in production (SES, ZeptoMail, Postmark, Resend)? Delivery speed in India matters for OTP. | Console adapter in dev; decide before pilot |
| 4 | Vendors | Vendors serving several hospitals: one login across hospitals or one per hospital? | One account per hospital in v1 |
| 5 | State machine | "Rejected → reassigned": is `reject` only the verifier failing the work, and is a worker *declining* an assignment a separate action? | Yes: `reject` = verifier; `decline` = worker, back to unassigned |
| 6 | SLA | Does `on_hold` pause the SLA clock, and can a worker put a task on hold or only request it? | Pauses; worker requests, supervisor approves |
| 7 | SLA | Does the resolution clock stop at *submitted* or at *verified*? | Stops at submitted; verification has its own clock for supervisors |
| 8 | SLA | Housekeeping SLA defaults per risk level (decision 17 covers maintenance only). | High risk: 30 min response / 60 min finish; medium 60/120; low 120/240 (please confirm) |
| 9 | SLA | Do SLAs run 24×7 or only in business hours for some categories (e.g. civil works)? | 24×7 for housekeeping & critical/high maintenance; business hours for normal civil |
| 10 | Housekeeping | Inspection scoring: pass mark and scale? | 0–100, pass ≥ 80; any "critical" checklist item failed = fail |
| 11 | Housekeeping | Worker score formula (on-time %, inspection pass %, rework count); weights? | 40% on-time, 40% pass rate, 20% no-rework; shown as a trend, not a rank |
| 12 | Housekeeping | Offline scans: a QR scanned offline and synced later; accept if synced within how long? | Accept within 2 h, flagged "synced late" if more than 10 min |
| 13 | Housekeeping | Photo on every task (decision 14): accept one photo, or after + before for some area types? | One "after" photo; "before + after" configurable per area type |
| 14 | Escalation | Default minutes between escalation levels? | L1 at due, L2 +30 min, L3 +60 min (critical: +15/+30) |
| 15 | Escalation | Should the MD ever receive escalations (e.g. critical overdue > 4 h)? | No; the MD sees them on the overview only |
| 16 | Public QR | Retention for a public reporter's phone number? | 90 days after the report closes |
| 17 | Public QR | Issue options per area type: who maintains the list (Oglos defaults vs hospital-editable)? | Oglos defaults, hospital can edit |
| 18 | Discharge | Who may press "patient discharged → clean bed" (ward nurse, ward clerk, any staff)? Nurses are clinical staff and need a minimal OGLOS login. | A `requester` role scoped to the ward |
| 19 | Labour | Should shift check-in be mandatory before a worker can accept tasks? | Optional per hospital; default off |
| 20 | Web push | `pywebpush` is MPL-2.0 (weak copyleft, not GPL). Is MPL acceptable, or implement VAPID with `cryptography` (Apache/BSD) ourselves? | Implement ourselves to stay MIT/BSD/Apache-only |
| 21 | Fonts | Anek: confirm tabular figures exist (Phase 1 check). | Fallback IBM Plex Sans + Noto Sans Kannada/Devanagari |
| 22 | Brand | SVG logos (decision 6) and a logo version for light backgrounds without the tile. | PNGs; the tile mark works on both themes |
| 23 | Billing | Module enable/disable: should Oglos only (platform admin) switch modules, or the hospital admin too? | Platform admin only (it's tied to pricing) |
| 24 | Exports | Exact NABH document formats wanted (FMS / HIC registers). Any sample registers from a hospital? | Generic daily cleaning register + inspection register + work-order log |
| 25 | Hosting | AWS backup region: ap-south-2 (Hyderabad) acceptable? | Yes |
