# OGLOS: questions to answer before building

Answer these, then save the answers as `docs/decisions.md` (the build prompt tells Claude Code to read it).
⭐ = blocks the build. Anything left blank → Claude uses the default in brackets and lists it in `docs/open-questions.md`.

## A. Product & customer
1. ⭐ Who is the first pilot hospital, and roughly how many beds, floors, wards and staff does it have?
2. ⭐ Who signs the cheque: MD, COO/administrator or facility head? Whose dashboard must look best in the demo?
3. Which workflow leads the demo: housekeeping, maintenance or requests? [housekeeping]
4. Is housekeeping in-house, outsourced to an agency, or mixed? Same for security and maintenance (AMC vendors).
5. Pricing model: per bed per month, flat per hospital, or per module? [flat per hospital + per-module add-ons]

## B. Brand & media
6. ⭐ Confirm the files in `/media`: logo (SVG preferred) in full-colour, white and mono versions; favicon/app icon (512×512 PNG); any brand fonts.
7. ⭐ Exact brand hex codes, if you have them. [extract from logo: deep green + gold accent]
8. Light mode only, or light + dark? [light first; dark for the wall TV "operations board"]
9. Domain for the app (e.g. app.oglos.site)? [app.oglos.site]

## C. People & devices
10. ⭐ Does every worker get their own login on their own phone, does a supervisor update from a shared device, or both? [both]
11. ⭐ Which languages for worker screens? [English + Kannada + Hindi]
12. What phones do workers typically have? [low-end Android, Chrome]
13. Worker login method: phone OTP, PIN on a shared device, or QR badge? [OTP on own phone; PIN on shared device]

## D. Workflows
14. ⭐ Housekeeping: QR scan at start, at end, or both? Photo on every task, or only high-risk areas and inspections? [scan start + end; photo for high-risk areas]
15. ⭐ Who verifies cleaning, and what % gets inspected? [supervisor; 100% of high-risk areas + 20% random sample]
16. Should a failed inspection automatically create a re-clean task and affect the worker's score? [yes]
17. Maintenance SLA levels? [Critical 30 min response / 4 h fix · High 2 h / 24 h · Normal 8 h / 72 h]
18. Do vendors get their own limited login? [yes]
19. ⭐ Escalation chain? [worker → supervisor → department head → operations manager]
20. Notification channels: in-app, SMS, WhatsApp Business API? Is the WhatsApp per-message cost acceptable? [in-app for all; WhatsApp for escalations only]
21. Can public QR reporters leave a phone number? [optional, with a consent checkbox]

## E. Data, security & compliance
22. HMS integration in v1, or standalone? [standalone; manual "patient discharged" button]
23. Retention: photos / audit logs / deactivated staff records? [18 months / 3 years / 1 year after exit]
24. Hosting provider and region? [AWS ap-south-1 Mumbai]
25. Any hospital that needs on-premise? [no, SaaS only]
26. Who is Oglos's named contact for data protection and security incidents (needed for the privacy notice and the CERT-In 6-hour reporting)? Name + email + phone.
27. Will you have a lawyer review the Terms of Service, Data Processing Agreement and Privacy Notice templates before the first paid hospital? [yes, strongly recommended]

## F. Team & timeline
28. ⭐ Who builds what: you with Claude Code alone, or teammates (backend / frontend / DevOps owners)?
29. ⭐ Target date for the pilot demo?
30. Do you already have the domain, a cloud account, an SMS/OTP provider (e.g. MSG91) and a WhatsApp Business account?
