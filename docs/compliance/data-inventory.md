# Personal data inventory

Per DPDP Act 2023 / DPDP Rules 2025. The **hospital is the Data Fiduciary; Oglos is the Data Processor.**
Every new personal-data field must be added here before merge (`compliance-check` skill enforces it).
Retention values are the defaults from `decisions.md` (decision 23), configurable per hospital.

**Not collected, by design:** patient names, MRNs, diagnoses, clinical notes, Aadhaar, home address, date of birth, photos of people
(capture guidance tells staff to photograph the area, not people), continuous location. **Children's data:** not applicable, since users are adult staff and no patient data is processed.

| Field | Table | Purpose | Legal basis (DPDP) | Retention | Who can see it | Protection |
|---|---|---|---|---|---|---|
| Display name | users | identify task owner, audit trail | Legitimate use: employment (s.7(i)) | active + 1 year after exit, then replaced with "Staff #id" | hospital staff in scope; vendors see the first name only | — |
| Employee code | users | login (PIN), anonymised label | employment | as above; kept as the pseudonym after erasure | admins, supervisors | — |
| Work email | users | OTP login, notifications | employment | active + 1 year | admins; self | unique per hospital |
| Phone (optional) | users | contact by supervisors, future SMS | employment | active + 1 year | `staff.manage` holders (others see a masked value) | AES-GCM field encryption + HMAC lookup hash |
| Role, department, employment type, agency/vendor | users, user_roles | access control, contractor vs employee records (Labour Codes) | employment | active + 1 year | admins | — |
| Shift check-ins (time, method, area) | shift_checkins | attendance accuracy for the hospital | employment | 3 years (audit) | admins, dept head, self | append-only |
| QR scan events (time, area) | qr_scans | proof of presence at the task location, at scan time only | employment | 3 years | supervisors+, self | append-only; **no GPS** |
| Task actions & audit events | audit_events | accountability, NABH documentation support | employment / legal obligation of the hospital | 3 years | in scope; quality coordinator | hash chain; ids only, no names |
| Evidence photos | evidence (S3) | proof of work | employment | 18 months, then purged | in scope | private bucket, signed URLs, EXIF stripped |
| Scorecards (derived) | computed | performance feedback | employment | follows the source data | self, supervisor+, MD | — |
| Password / PIN / TOTP secret | credentials | authentication | necessary for the service | until changed or erased | nobody (hashes / encrypted) | argon2id / AES-GCM |
| Session metadata (UA summary, IP hash) | sessions | security, "log out all devices" | security | 90 days | self, admins | IP stored as a salted hash |
| Push subscription endpoint | push_subscriptions | in-app notifications | consent (browser prompt) | until unsubscribed or erased | nobody | keys encrypted |
| Privacy notice acknowledgement | notice_acknowledgements | proof notice was given | DPDP s.5 | 3 years after exit | admins | append-only |
| **Public reporter phone (optional)** | public_reports | follow up on the reported issue | **Consent** (s.6), explicit checkbox, versioned notice | 90 days (proposed, see open questions) | supervisors+ handling the report (masked by default) | AES-GCM; never shown on the TV board |
| Public reporter IP | public_reports | abuse prevention | legitimate use / security | 30 days as a salted hash | nobody (automated) | hash only |

## Data principal rights (staff)
Export (JSON/CSV): `GET /privacy/users/{id}/export` · correction via the admin staff edit (audited) · erasure via `data_requests(kind=erase)` → anonymise as in `data-model.md` §5 · grievance contact shown in the app footer and notice (**TODO, decision 26**).

## Cross-border
All data, backups and logs are in AWS India regions (ap-south-1 primary, ap-south-2 backups). Sub-processors are listed in `docs/legal/subprocessors.md` (Phase 6).
