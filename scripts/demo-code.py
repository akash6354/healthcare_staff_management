"""Print the current 6-digit sign-in code for the DEMO MD or admin account (instead of an authenticator app).

    python scripts/demo-code.py md
    python scripts/demo-code.py admin

Works only for the fixed demo secrets in apps/api/app/seed/sunrise.py (synthetic demo data).
Codes change every 30 seconds.
"""

import base64
import hashlib
import hmac
import struct
import sys
import time

DEMO_TOTP = {"admin": "OGLOSADMINSUNRISEDEMOKEYAAAAAAAA", "md": "OGLOSMDSUNRISEDEMOKEYAAAAAAAAAAA"}


def totp(secret: str, at: float) -> str:
    key = base64.b32decode(secret)
    counter = struct.pack(">Q", int(at // 30))
    digest = hmac.new(key, counter, hashlib.sha1).digest()
    offset = digest[-1] & 0x0F
    value = struct.unpack(">I", digest[offset : offset + 4])[0] & 0x7FFFFFFF
    return f"{value % 1_000_000:06d}"


who = (sys.argv[1] if len(sys.argv) > 1 else "md").lower()
if who not in DEMO_TOTP:
    sys.exit("Usage: python scripts/demo-code.py md|admin")
now = time.time()
print(f"{who.upper()} code: {totp(DEMO_TOTP[who], now)}   (valid for {30 - int(now) % 30} more seconds)")
