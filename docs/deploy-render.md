# Prototype demo on Render (synthetic data only)

For showing the prototype. **Not for real hospital data**: Render has no India region (Singapore is used),
and the free database is deleted 30 days after creation. Production stays on AWS Mumbai (`docs/deploy.md`).

## What runs
One free **web service** (Docker, `infra/render/Dockerfile`) serves the API, the admin site at `/` and the
staff app at `/staff/`; photos are stored in Postgres (`STORAGE_BACKEND=db`) behind signed links.
Plus a free **Postgres** and a free **Key Value** (rate limits). No background worker: overdue checks run when
the dashboard loads.

## Steps
1. Push the repo to GitHub (done) and in Render choose **New → Blueprint**, pick the repo; it reads `render.yaml`.
2. Fill the two prompted values:
   `QR_SIGNING_KEYS` = `v1:` + `python -c "import secrets;print(secrets.token_urlsafe(32))"`,
   `FIELD_ENCRYPTION_KEYS` = `v1:` + `python -c "import os,base64;print(base64.b64encode(os.urandom(32)).decode())"`.
3. Deploy. On first start the log shows `bootstrap ok`, migrations, and the demo logins. They are the fixed
   ones in `TESTING.md` (MD/admin codes: `python scripts/demo-code.py md|admin`).

> Those demo logins are public. Anyone who finds your `onrender.com` URL can sign in and change the **demo** data
> (there's no real data in it). Share the link only with people you're demoing to, and redeploy with a fresh
> database to reset.
4. Open `https://<service>.onrender.com/` (admin) and `/staff/` (phone). Demo steps: README.

## Known limits
- Free web service sleeps after 15 min idle; the first request takes ~1 min. Open it before a demo.
- If `bootstrap` fails with a permissions error (database user can't create roles), switch the database to a
  Render **private service** running `postgres:16` with a disk (paid), using `infra/postgres/init`.
- Free Key Value loses data on restart (only rate-limit counters; harmless).
