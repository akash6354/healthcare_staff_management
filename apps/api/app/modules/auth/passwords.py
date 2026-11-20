"""Password policy: minimum 10 characters + breached-password check (HIBP k-anonymity range API).

Only the first 5 hex chars of the SHA-1 leave the server. If the check is unreachable we fail open
(log a warning) so an outage doesn't lock admins out; set BREACHED_PASSWORD_CHECK=off to disable.
"""

import hashlib
import logging

import httpx

from app.core.config import get_settings
from app.core.errors import AppError

MIN_LENGTH = 10
log = logging.getLogger(__name__)


async def is_breached(password: str) -> bool:
    if get_settings().breached_password_check != "hibp":  # noqa: S105
        return False
    sha1 = hashlib.sha1(password.encode(), usedforsecurity=False).hexdigest().upper()
    prefix, suffix = sha1[:5], sha1[5:]
    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            resp = await client.get(
                f"https://api.pwnedpasswords.com/range/{prefix}",
                headers={"Add-Padding": "true", "User-Agent": "oglos-api"},
            )
            resp.raise_for_status()
    except httpx.HTTPError:
        log.warning("breached-password check unavailable; skipping")
        return False
    return any(line.split(":")[0] == suffix for line in resp.text.splitlines())


async def validate_new_password(password: str) -> None:
    if len(password) < MIN_LENGTH:
        raise AppError("PASSWORD_TOO_SHORT", 422, min_length=MIN_LENGTH)
    if len(password) > 128:
        raise AppError("PASSWORD_TOO_LONG", 422)
    if await is_breached(password):
        raise AppError("PASSWORD_BREACHED", 422)
