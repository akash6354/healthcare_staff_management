"""Create .env for local development from .env.example, with fresh random secrets.

    python scripts/make-env.py

Refuses to overwrite an existing .env (the local database and storage are set up with the secrets
inside it; replacing them makes the database unreachable). Use --force only on a brand-new setup.
"""

import base64
import os
import secrets
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
target = ROOT / ".env"

if target.exists() and "--force" not in sys.argv:
    sys.exit(".env already exists. Not touching it (see the comment at the top of this script).")

text = (ROOT / ".env.example").read_text(encoding="utf-8")
values = {
    "change-me-superuser": secrets.token_urlsafe(18),
    "change-me-owner": secrets.token_urlsafe(18),
    "change-me-app": secrets.token_urlsafe(18),
    "change-me-platform": secrets.token_urlsafe(18),
    "change-me-s3-secret": secrets.token_urlsafe(24),
    "REPLACE_WITH_BASE64_32_BYTES": base64.b64encode(os.urandom(32)).decode(),
}
for placeholder, value in values.items():
    text = text.replace(placeholder, value)
lines = []
for line in text.splitlines():
    key = line.split("=", 1)[0]
    if key in ("JWT_SIGNING_KEY", "HMAC_LOOKUP_KEY", "OTP_HMAC_KEY"):
        line = f"{key}={secrets.token_urlsafe(48)}"
    elif key == "QR_SIGNING_KEYS":
        line = f"{key}=v1:{secrets.token_urlsafe(32)}"
    lines.append(line)
target.write_text("\n".join(lines) + "\n", encoding="utf-8")
print(f"Created {target} with fresh local secrets. Keep it private; it is ignored by git.")
