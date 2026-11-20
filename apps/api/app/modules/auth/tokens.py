"""Short-lived access JWTs (≤15 min). Refresh tokens are opaque, stored hashed (see service.py)."""

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import jwt

from app.core.config import get_settings
from app.core.errors import unauthorized

ALGORITHM = "HS256"
AUDIENCE = "oglos-api"
ISSUER = "oglos"


@dataclass(frozen=True)
class AccessClaims:
    sub: uuid.UUID
    hid: uuid.UUID
    sid: uuid.UUID
    roles: tuple[tuple[str, str, uuid.UUID | None], ...]
    amr: tuple[str, ...]
    mfa_pending: bool
    exp: int


def issue_access_token(
    *,
    user_id: uuid.UUID,
    hospital_id: uuid.UUID,
    session_id: uuid.UUID,
    roles: list[tuple[str, str, uuid.UUID | None]],
    amr: list[str],
    mfa_pending: bool,
) -> tuple[str, int]:
    s = get_settings()
    now = datetime.now(UTC)
    exp = now + timedelta(minutes=s.access_token_minutes)
    payload = {
        "iss": ISSUER,
        "aud": AUDIENCE,
        "sub": str(user_id),
        "hid": str(hospital_id),
        "sid": str(session_id),
        "roles": [[r, st, str(sid) if sid else None] for r, st, sid in roles],
        "amr": amr,
        "mfa_pending": mfa_pending,
        "iat": int(now.timestamp()),
        "exp": int(exp.timestamp()),
    }
    return jwt.encode(payload, s.jwt_signing_key, algorithm=ALGORITHM), int(exp.timestamp())


def decode_access_token(token: str) -> AccessClaims:
    try:
        p = jwt.decode(
            token,
            get_settings().jwt_signing_key,
            algorithms=[ALGORITHM],
            audience=AUDIENCE,
            issuer=ISSUER,
            options={"require": ["exp", "sub", "hid", "sid"]},
        )
        return AccessClaims(
            sub=uuid.UUID(p["sub"]),
            hid=uuid.UUID(p["hid"]),
            sid=uuid.UUID(p["sid"]),
            roles=tuple(
                (r[0], r[1], uuid.UUID(r[2]) if r[2] else None) for r in p.get("roles", [])
            ),
            amr=tuple(p.get("amr", [])),
            mfa_pending=bool(p.get("mfa_pending", False)),
            exp=int(p["exp"]),
        )
    except (jwt.PyJWTError, KeyError, ValueError, TypeError) as exc:
        raise unauthorized("INVALID_TOKEN") from exc
