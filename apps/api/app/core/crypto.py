"""Field-level encryption (AES-256-GCM with key ids), keyed lookup hashes and secret hashing."""

import base64
import hashlib
import hmac
import os
import secrets
from functools import lru_cache

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from app.core.config import get_settings

_ph = PasswordHasher(time_cost=3, memory_cost=64 * 1024, parallelism=1)


@lru_cache
def _keys() -> dict[str, bytes]:
    out: dict[str, bytes] = {}
    for part in get_settings().field_encryption_keys.split(","):
        kid, _, b64 = part.strip().partition(":")
        key = base64.b64decode(b64)
        if len(key) != 32:
            raise ValueError(f"field encryption key {kid} must be 32 bytes")
        out[kid] = key
    return out


def encrypt_field(plaintext: str) -> bytes:
    """Returns b'<kid>:' + nonce + ciphertext. The key id allows key rotation."""
    kid = get_settings().field_encryption_active_key
    nonce = os.urandom(12)
    ct = AESGCM(_keys()[kid]).encrypt(nonce, plaintext.encode(), kid.encode())
    return kid.encode() + b":" + nonce + ct


def decrypt_field(blob: bytes) -> str:
    kid_b, _, rest = bytes(blob).partition(b":")
    nonce, ct = rest[:12], rest[12:]
    return AESGCM(_keys()[kid_b.decode()]).decrypt(nonce, ct, kid_b).decode()


def lookup_hash(value: str) -> bytes:
    """Deterministic keyed hash so encrypted values (e.g. phone) can still be looked up."""
    key = get_settings().hmac_lookup_key.encode()
    return hmac.new(key, value.strip().lower().encode(), hashlib.sha256).digest()


def otp_hash(challenge_id: str, code: str) -> bytes:
    key = get_settings().otp_hmac_key.encode()
    return hmac.new(key, f"{challenge_id}:{code}".encode(), hashlib.sha256).digest()


def token_hash(token: str) -> bytes:
    return hashlib.sha256(token.encode()).digest()


def new_token(nbytes: int = 32) -> str:
    return secrets.token_urlsafe(nbytes)


def constant_time_equals(a: bytes, b: bytes) -> bool:
    return hmac.compare_digest(a, b)


def hash_secret(secret: str) -> str:
    return _ph.hash(secret)


def verify_secret(stored_hash: str, secret: str) -> bool:
    try:
        return _ph.verify(stored_hash, secret)
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False


def mask_phone(phone: str) -> str:
    digits = phone[-10:]
    return f"{digits[:2]}•••••{digits[-3:]}" if len(digits) >= 5 else "•••"
