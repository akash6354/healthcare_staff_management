---
name: compliance-check
description: Check new or changed OGLOS features against Indian compliance requirements (DPDP Act 2023 + Rules 2025, CERT-In directions, IT Act/SPDI, Labour Codes, NABH wording) as specified in BUILD_PROMPT §8. Run before marking any phase or feature done.
---

# OGLOS compliance check

Sources: `docs/BUILD_PROMPT.md` §8, `docs/compliance/data-inventory.md`, `docs/decisions.md`. This is an engineering check, not legal advice.
Target: the given module/path or `git diff main...HEAD`. For each item: **PASS / FAIL / N/A** with evidence.

## 1. No patient data (hard rule 1)
- [ ] No fields, seeds, fixtures, i18n strings, log lines or photo captions that hold patient names, MRNs, diagnoses or clinical notes.
- [ ] Free-text fields that staff might misuse (task description, comments, public note) have length caps and the UI hint "Don't enter patient details".

## 2. DPDP: personal data
- [ ] Every **new personal-data field** is listed in `docs/compliance/data-inventory.md` with purpose, legal basis, retention, visibility and protection.
- [ ] Retention is set (a `hospital_settings.retention` key or a documented fixed value) and the purge job covers it.
- [ ] The erasure path handles the new field (anonymise, keep audit ids).
- [ ] The rights export (`/privacy/users/{id}/export`) includes the new field.
- [ ] If the purpose or the data collected changed, the **staff or public privacy notice** is updated and its version bumped (re-acknowledgement triggered).
- [ ] Anything collected from the public needs explicit consent (checkbox + notice version stored); optional fields stay optional.
- [ ] Data stays in India (no new non-India sub-processor; if one is added, update `docs/legal/subprocessors.md`).

## 3. Security safeguards & breach readiness
- [ ] The `security-review` skill has passed for the same scope.
- [ ] New security-relevant events (logins, exports, role changes, erasure) are written to the audit log.
- [ ] Breach register / incident playbook unaffected or updated (`docs/compliance/incident-response.md`).

## 4. CERT-In
- [ ] New services/containers send logs to the central log store with **180-day** retention in India.
- [ ] Timestamps come from server clocks synced via NTP; no client clocks used as record time.

## 5. Labour Codes
- [ ] Attendance / shift / task records stay accurate, append-only and exportable.
- [ ] `employment_type` / `agency_id` / `vendor_id` are respected in new reports.
- [ ] **No continuous or covert location tracking**; location only implied by a QR scan, disclosed in the notice.

## 6. Hospital standards wording
- [ ] UI and docs say "supports NABH documentation", never "NABH compliant" or "certified" (grep `compliant|certified` in `packages/i18n` and `apps/*/src`).

## 7. Accessibility (WCAG 2.1 AA / GIGW for public pages)
- [ ] New screens: contrast AA, status never shown by colour alone, keyboard focus visible, labels on inputs, all strings in i18n (en/kn/hi).

## Output
A table `check | result | evidence | fix` and a list of blocking FAILs (§1 and §2 always block). Add unresolved business/legal questions to `docs/open-questions.md`.
