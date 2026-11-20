# Security policy

OGLOS (Hospital Operations & Accountability Platform) is built by Oglos (oglos.site).

## Reporting a vulnerability
Email **security contact: TODO (see docs/open-questions.md #1)** with a description, steps to reproduce and impact.
Please do not open public GitHub issues for security problems. We aim to acknowledge reports within 2 business days.

## Scope
The API, web admin, staff PWA, public QR pages and infrastructure configuration in this repository.

## Our practices
See `docs/security.md` for controls (tenant isolation with PostgreSQL RLS, MFA for admins, immutable audit trail,
encryption, dependency and secret scanning in CI).
