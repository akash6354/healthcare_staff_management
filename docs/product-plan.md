# OGLOS Staff Management System: product plan (v1.0, 20 Nov 2026)

Source: `OGLOS_Staff_Management_System_Plan_v1.pdf` (Google Drive › Extras). This file is the working summary.
Where it conflicts with `BUILD_PROMPT.md`, the plan wins (see `decisions.md` section H). **Stack exception:** the PDF proposes
Frappe; the owner chose to keep FastAPI + PostgreSQL (decision H1).

**Core principle:** everything runs on our own backend and hosting. No per-use fees (no WhatsApp/SMS API, no paid AI, no NFC
hardware). Low legal risk by design: no biometrics, no live GPS, no patient data in the staff system.

## Business model
Staff system first (tasks, proof of work, attendance, desks, rosters, reports). Patients, billing, pharmacy, lab and doctor
portals come later as the paid hospital upgrade. We sell the accountability features, setup, customisation and secure hosting.
Olympus asked for doctor portals; quote them as paid personalised work in the same deal.

## First pilot: Olympus Hospital, Bangalore (two branches)
- **Handover Monday 23 Nov 2026.** One department (housekeeping) in one branch. 14-day free pilot with a fixed end date;
  then paid plan, or OGLOS returns all data and deletes it. Book the review meeting at handover.
- Review meeting: tasks done, missed, issues caught, plus the 3D building demo (Premium reveal).

### Monday minimum scope
1. Staff profiles, roles and logins (MD, supervisor, staff)
2. Desks for Olympus (name, branch, department) and people assigned to desks
3. Tasks and checklists assigned to desks
4. Before/after photo proof: in-app camera only, server time
5. Simple check-in/check-out (QR at the entrance)
6. Supervisor approve/reject + simple dashboard: overdue, missed, done
7. Staff data notice (what, why, who sees it), hosting in India

The rest of Base lands during pilot weeks 1–2. Pro and Premium are the roadmap shown at the review.

## Tiers (every feature has an on/off switch in Plan Settings)
**Base:** staff profiles (name, phone, role, department, branch, joining date, emergency contact; active / on leave / left) ·
roles and logins by branch · QR attendance (entrance) · desk-wise setup · shifts and duty roster with swap requests ·
"Going out" cover · leave management · tasks and checklists (daily, recurring, one-time, assigned to desks) · before/after
photo proof (reference outline, compressed to ~150–200 KB) · approval and sign-off (supervisor, then the next person, e.g. the nurse, confirms) ·
spot inspections (random picks, short checklist, score) · auto-escalation (supervisor → MD, in-app) · fake-work detector
(rules only, flags go to a human) · shift handover · notices · dashboard and reports (Excel/PDF) · Kannada and Hindi voice and
picture screens · audit log and staff notice.

**Pro (3):** smart door QR (public room card "cleaned at 10:42, checked by a nurse" + report a problem) · rotating QR
attendance (tablet QR changes every 30 s) · star of the week (points, badges, leaderboard, printable poster; reward only).

**Premium (2):** 3D live building + time machine (floor builder, 3D on laptops/tablets, 2D on low-end phones, tap a room for
duty/tasks/photo timeline, replay-the-day slider, before/after swipe; Three.js, MIT) · compliance and reports pack
(NABH-supporting registers as signed PDFs, monthly hygiene report, branch vs branch).

## Desk-wise model
Every work point is a desk (Reception Desk 1, Ward 3 Nurse Station, Housekeeping Floor 2). Tasks belong to desks, not people.
The roster puts people on desks per shift. When the person changes, the tasks stay with the desk. Desks double as rooms in the 3D building.

**Going out:** tap "Going out" + reason (break, errand, emergency, meeting) → pick an on-duty colleague in the same role →
they accept and the desk's open tasks move to them → "I'm back" returns the desk. No acceptance within 10 min → supervisor alerted.
Rules: no off-duty cover, no self-cover, out > 1 h needs supervisor approval, work during cover credits the cover person,
audit log records both names and start/end. Records desk cover, not movements.

## Exit data export (OGLOS super-admin only)
One click → ZIP (Excel of all data, photos folder, PDF summary); audited; data deleted after the client confirms. Contract
promise: export within 7 days of request.

## Deliberately left out
NFC (hardware cost) · AI photo checks (per-call cost) · WhatsApp/SMS API (per-message cost) · fingerprint/face (biometric risk) ·
live GPS · payroll/salary deductions · Aadhaar · patient data in the staff system · automatic penalties.

## Rules
- Never claim "NABH certified"/"guarantees accreditation", and never use the NABH logo. Say "Helps you maintain records for NABH and inspections".
- No medical function (diagnosis, treatment suggestions, reading reports); that would make it a medical device.
- DPDP: short staff notice (also for agency/contract staff); collect only on duty and inside the hospital; never photograph patients; host in India.
- Staff screens extremely simple; never punish automatically; staff see their own score and can appeal.
