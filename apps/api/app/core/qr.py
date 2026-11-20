"""Signed QR tokens (HMAC-SHA256, versioned keys, rotatable per object) so codes can't be forged
or enumerated. Payload: purpose | hospital id | object id | object version."""

import base64
import hashlib
import hmac
import io
import uuid
from dataclasses import dataclass
from functools import lru_cache

import qrcode
import qrcode.image.svg

from app.core.config import get_settings


@lru_cache
def _keys() -> dict[str, bytes]:
    out = {}
    for part in get_settings().qr_signing_keys.split(","):
        kid, _, secret = part.strip().partition(":")
        out[kid] = secret.encode()
    return out


def _b64(b: bytes) -> str:
    return base64.urlsafe_b64encode(b).rstrip(b"=").decode()


def _unb64(s: str) -> bytes:
    return base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))


@dataclass(frozen=True)
class QrClaim:
    purpose: str
    hospital_id: uuid.UUID
    object_id: uuid.UUID
    version: int


def sign(purpose: str, hospital_id: uuid.UUID, object_id: uuid.UUID, version: int) -> str:
    kid = next(iter(_keys()))  # first key signs; all keys verify (rotation)
    body = f"{purpose}|{hospital_id}|{object_id}|{version}".encode()
    mac = hmac.new(_keys()[kid], body, hashlib.sha256).digest()[:16]
    return f"{kid}.{_b64(body)}.{_b64(mac)}"


def verify(token: str, purpose: str) -> QrClaim | None:
    try:
        kid, body_b64, mac_b64 = token.strip().split(".")
        key = _keys()[kid]
        body = _unb64(body_b64)
        expected = hmac.new(key, body, hashlib.sha256).digest()[:16]
        if not hmac.compare_digest(expected, _unb64(mac_b64)):
            return None
        p, hid, oid, ver = body.decode().split("|")
        if p != purpose:
            return None
        return QrClaim(p, uuid.UUID(hid), uuid.UUID(oid), int(ver))
    except (ValueError, KeyError, UnicodeDecodeError):
        return None


def svg(data: str) -> str:
    img = qrcode.make(data, image_factory=qrcode.image.svg.SvgPathImage, box_size=12, border=2)
    buf = io.BytesIO()
    img.save(buf)
    return buf.getvalue().decode()
