"""Authentication flows (docs/security.md §2, decisions 13 and G2).

- Staff: email OTP (6 digits, 5-min expiry, 5 attempts) or PIN on a registered shared device.
- Admin/manager/vendor roles: password (argon2id) + TOTP (required for MFA roles).
- Sessions: short access JWT + rotating opaque refresh token "<hospital_id>.<secret>" stored hashed.
  Re-use of a spent refresh token revokes the whole session.
Responses never reveal whether an account exists.
"""

import secrets
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import jwt
import pyotp
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.audit.service import Actor, record
from app.core.config import get_settings
from app.core.crypto import (
    constant_time_equals,
    decrypt_field,
    encrypt_field,
    hash_secret,
    lookup_hash,
    new_token,
    otp_hash,
    token_hash,
    verify_secret,
)
from app.core.db import anonymous_session, resolve_hospital_code, set_tenant, tenant_session
from app.core.errors import AppError, unauthorized
from app.core.ids import uuid7
from app.core.ratelimit import hit
from app.modules.auth.models import AuthSession, Credential, OtpChallenge, RefreshToken
from app.modules.auth.tokens import ALGORITHM, issue_access_token
from app.modules.staff.models import Device, User, UserRole, UserStatus
from app.notify.email import EmailMessage, email_adapter
from app.notify.messages import otp_email
from app.policy.permissions import MFA_REQUIRED_ROLES

OTP_TTL = timedelta(minutes=5)
OTP_MAX_ATTEMPTS = 5
LOCKOUT_STEPS = (timedelta(minutes=15), timedelta(hours=1), timedelta(hours=24))
FAILURES_BEFORE_LOCK = 5
_DUMMY_HASH = hash_secret("dummy-password-for-timing")


@dataclass(frozen=True)
class IssuedSession:
    access_token: str
    access_expires_at: int
    refresh_token: str
    mfa_pending: bool
    user_id: uuid.UUID
    hospital_id: uuid.UUID


def _now() -> datetime:
    return datetime.now(UTC)


def invalid_credentials() -> AppError:
    return AppError("INVALID_CREDENTIALS", 401)


# ---------- helpers ---------------------------------------------------------------------------


async def _roles(session: AsyncSession, user_id: uuid.UUID) -> list[UserRole]:
    return list((await session.scalars(select(UserRole).where(UserRole.user_id == user_id))).all())


async def _credential(session: AsyncSession, user: User) -> Credential:
    cred = await session.get(Credential, user.id, with_for_update=True)
    if cred is None:
        cred = Credential(user_id=user.id, hospital_id=user.hospital_id, recovery_code_hashes=[])
        session.add(cred)
        await session.flush()
    return cred


def _check_lock(cred: Credential) -> None:
    if cred.locked_until and cred.locked_until > _now():
        raise AppError(
            "ACCOUNT_LOCKED",
            423,
            retry_after_seconds=int((cred.locked_until - _now()).total_seconds()),
        )


async def _register_failure(session: AsyncSession, cred: Credential) -> None:
    cred.failed_attempts += 1
    if cred.failed_attempts >= FAILURES_BEFORE_LOCK:
        step = LOCKOUT_STEPS[min(cred.lockout_level, len(LOCKOUT_STEPS) - 1)]
        cred.locked_until = _now() + step
        cred.lockout_level += 1
        cred.failed_attempts = 0
        await record(
            session,
            hospital_id=cred.hospital_id,
            actor=Actor(cred.user_id, "user"),
            entity_type="user",
            entity_id=cred.user_id,
            action="auth.locked",
            payload={"minutes": int(step.total_seconds() // 60)},
        )


def _register_success(cred: Credential) -> None:
    cred.failed_attempts = 0
    cred.lockout_level = 0
    cred.locked_until = None


async def _create_session(
    session: AsyncSession,
    user: User,
    *,
    amr: list[str],
    mfa_pending: bool,
    device_id: uuid.UUID | None = None,
    user_agent: str | None = None,
    ip: str | None = None,
) -> IssuedSession:
    s = get_settings()
    roles = await _roles(session, user.id)
    auth_session = AuthSession(
        id=uuid7(),
        hospital_id=user.hospital_id,
        user_id=user.id,
        device_id=device_id,
        amr=amr,
        mfa_satisfied="totp" in amr,
        user_agent_summary=(user_agent or "")[:120] or None,
        ip_hash=lookup_hash(ip) if ip else None,
        absolute_expires_at=_now() + timedelta(days=s.refresh_token_absolute_days),
        last_seen_at=_now(),
    )
    session.add(auth_session)
    await session.flush()
    refresh = await _new_refresh(session, auth_session, parent_id=None)
    access, exp = issue_access_token(
        user_id=user.id,
        hospital_id=user.hospital_id,
        session_id=auth_session.id,
        roles=[(r.role.value, r.scope_type.value, r.scope_id) for r in roles],
        amr=amr,
        mfa_pending=mfa_pending,
    )
    await record(
        session,
        hospital_id=user.hospital_id,
        actor=Actor(user.id, roles[0].role.value if roles else "user"),
        entity_type="session",
        entity_id=auth_session.id,
        action="auth.login",
        payload={"amr": amr, "mfa_pending": mfa_pending},
    )
    return IssuedSession(access, exp, refresh, mfa_pending, user.id, user.hospital_id)


async def _new_refresh(
    session: AsyncSession, auth_session: AuthSession, parent_id: uuid.UUID | None
) -> str:
    secret = f"{auth_session.hospital_id}.{new_token()}"
    session.add(
        RefreshToken(
            hospital_id=auth_session.hospital_id,
            session_id=auth_session.id,
            token_hash=token_hash(secret),
            parent_id=parent_id,
            expires_at=min(
                _now() + timedelta(days=get_settings().refresh_token_days),
                auth_session.absolute_expires_at,
            ),
        )
    )
    await session.flush()
    return secret


def _needs_mfa(roles: list[UserRole]) -> bool:
    return any(r.role in MFA_REQUIRED_ROLES for r in roles)


# ---------- email OTP ---------------------------------------------------------------------------


async def request_email_otp(hospital_code: str, email: str, ip: str) -> uuid.UUID:
    """Always returns a challenge id, real or decoy, so callers can't tell if the email exists."""
    email_key = lookup_hash(f"{hospital_code}:{email}").hex()
    await hit("otp-send-email", email_key, limit=3, window_seconds=900)
    await hit("otp-send-ip", lookup_hash(ip).hex(), limit=10, window_seconds=900)
    decoy = uuid7()
    async with anonymous_session() as session:
        hid = await resolve_hospital_code(session, hospital_code.strip().upper())
        if hid is None:
            return decoy
        await set_tenant(session, hid)
        user = await session.scalar(
            select(User).where(User.email == email.strip(), User.status == UserStatus.active)
        )
        if user is None:
            return decoy
        roles = await _roles(session, user.id)
        if _needs_mfa(roles):
            return decoy  # MFA roles must use password + TOTP
        cred = await _credential(session, user)
        if cred.locked_until and cred.locked_until > _now():
            return decoy
        code = f"{secrets.randbelow(10**6):06d}"
        challenge = OtpChallenge(
            id=uuid7(), hospital_id=hid, user_id=user.id, channel="email", code_hash=b"",
            expires_at=_now() + OTP_TTL,
        )  # fmt: skip
        challenge.code_hash = otp_hash(str(challenge.id), code)
        session.add(challenge)
        await session.flush()
        subject, body = otp_email(user.preferred_language.value, code, ttl_minutes=5)
        await email_adapter().send(EmailMessage(to=email.strip(), subject=subject, body=body))
        return challenge.id


async def verify_email_otp(
    hospital_code: str, challenge_id: uuid.UUID, code: str, ip: str, user_agent: str | None
) -> IssuedSession:
    await hit("otp-verify-ip", lookup_hash(ip).hex(), limit=30, window_seconds=900)
    async with anonymous_session() as session:
        hid = await resolve_hospital_code(session, hospital_code.strip().upper())
        if hid is None:
            raise AppError("INVALID_CODE", 401)
        await set_tenant(session, hid)
        challenge = await session.get(OtpChallenge, challenge_id, with_for_update=True)
        if (
            challenge is None
            or challenge.consumed_at is not None
            or challenge.expires_at < _now()
            or challenge.attempts >= OTP_MAX_ATTEMPTS
        ):
            raise AppError("INVALID_CODE", 401)
        user = await session.get(User, challenge.user_id)
        if user is None or user.status != UserStatus.active:
            raise AppError("INVALID_CODE", 401)
        cred = await _credential(session, user)
        _check_lock(cred)
        challenge.attempts += 1
        if not constant_time_equals(otp_hash(str(challenge.id), code.strip()), challenge.code_hash):
            if challenge.attempts >= OTP_MAX_ATTEMPTS:
                challenge.consumed_at = _now()
            await _register_failure(session, cred)
            await session.commit()
            raise AppError("INVALID_CODE", 401)
        challenge.consumed_at = _now()
        _register_success(cred)
        return await _create_session(
            session, user, amr=["otp"], mfa_pending=False, user_agent=user_agent, ip=ip
        )


# ---------- password + TOTP --------------------------------------------------------------------

MFA_TOKEN_MINUTES = 5


def _mfa_token(user: User) -> str:
    now = _now()
    payload = {
        "typ": "mfa", "sub": str(user.id), "hid": str(user.hospital_id),
        "iat": int(now.timestamp()), "exp": int((now + timedelta(minutes=MFA_TOKEN_MINUTES)).timestamp()),
    }  # fmt: skip
    return jwt.encode(payload, get_settings().jwt_signing_key, algorithm=ALGORITHM)


async def password_login(
    hospital_code: str, email: str, password: str, ip: str, user_agent: str | None
) -> IssuedSession | str:
    """Returns an IssuedSession, or an MFA token (str) when a TOTP code is still needed."""
    await hit("pw-ip", lookup_hash(ip).hex(), limit=20, window_seconds=900)
    await hit(
        "pw-email", lookup_hash(f"{hospital_code}:{email}").hex(), limit=10, window_seconds=900
    )
    async with anonymous_session() as session:
        hid = await resolve_hospital_code(session, hospital_code.strip().upper())
        user = None
        if hid is not None:
            await set_tenant(session, hid)
            user = await session.scalar(
                select(User).where(User.email == email.strip(), User.status == UserStatus.active)
            )
        cred = await _credential(session, user) if user else None
        if user is None or cred is None or not cred.password_hash:
            verify_secret(_DUMMY_HASH, password)  # equalise timing
            raise invalid_credentials()
        _check_lock(cred)
        if not verify_secret(cred.password_hash, password):
            await _register_failure(session, cred)
            await session.commit()
            raise invalid_credentials()
        _register_success(cred)
        roles = await _roles(session, user.id)
        if _needs_mfa(roles) and cred.totp_enabled_at:
            return _mfa_token(user)
        return await _create_session(
            session, user, amr=["pwd"], mfa_pending=_needs_mfa(roles), user_agent=user_agent, ip=ip
        )


async def totp_login(mfa_token: str, code: str, ip: str, user_agent: str | None) -> IssuedSession:
    await hit("totp-ip", lookup_hash(ip).hex(), limit=20, window_seconds=900)
    try:
        p = jwt.decode(mfa_token, get_settings().jwt_signing_key, algorithms=[ALGORITHM])
        if p.get("typ") != "mfa":
            raise ValueError("wrong token type")
        user_id, hid = uuid.UUID(p["sub"]), uuid.UUID(p["hid"])
    except (jwt.PyJWTError, KeyError, ValueError) as exc:
        raise unauthorized("INVALID_TOKEN") from exc
    async with tenant_session(hid) as session:
        user = await session.get(User, user_id)
        if user is None or user.status != UserStatus.active:
            raise invalid_credentials()
        cred = await _credential(session, user)
        _check_lock(cred)
        if not cred.totp_secret_enc or not _totp_ok(cred, code):
            await _register_failure(session, cred)
            await session.commit()
            raise AppError("INVALID_CODE", 401)
        _register_success(cred)
        return await _create_session(
            session, user, amr=["pwd", "totp"], mfa_pending=False, user_agent=user_agent, ip=ip
        )


def _totp_ok(cred: Credential, code: str) -> bool:
    code = code.strip().replace(" ", "")
    if cred.totp_secret_enc and pyotp.TOTP(decrypt_field(cred.totp_secret_enc)).verify(
        code, valid_window=1
    ):
        return True
    for i, stored in enumerate(cred.recovery_code_hashes):  # single-use recovery codes
        if verify_secret(stored, code):
            cred.recovery_code_hashes = [
                h for j, h in enumerate(cred.recovery_code_hashes) if j != i
            ]
            return True
    return False


async def totp_begin_enrolment(session: AsyncSession, user_id: uuid.UUID) -> str:
    user = await session.get(User, user_id)
    if user is None:
        raise unauthorized()
    cred = await _credential(session, user)
    if cred.totp_enabled_at:
        raise AppError("TOTP_ALREADY_ENABLED", 409)
    secret = pyotp.random_base32()
    cred.totp_secret_enc = encrypt_field(secret)
    label = user.email or user.employee_code
    return pyotp.TOTP(secret).provisioning_uri(name=label, issuer_name="OGLOS")


async def totp_confirm_enrolment(
    session: AsyncSession, user_id: uuid.UUID, session_id: uuid.UUID, code: str
) -> tuple[list[str], str, int]:
    """Enable TOTP. Returns recovery codes (shown once) and a fresh access token without mfa_pending."""
    user = await session.get(User, user_id)
    if user is None:
        raise unauthorized()
    cred = await _credential(session, user)
    if not cred.totp_secret_enc or cred.totp_enabled_at:
        raise AppError("TOTP_NOT_PENDING", 409)
    if not pyotp.TOTP(decrypt_field(cred.totp_secret_enc)).verify(code.strip(), valid_window=1):
        raise AppError("INVALID_CODE", 401)
    codes = [f"{secrets.token_hex(4)}-{secrets.token_hex(4)}" for _ in range(10)]
    cred.recovery_code_hashes = [hash_secret(c) for c in codes]
    cred.totp_enabled_at = _now()
    await session.execute(
        update(AuthSession)
        .where(AuthSession.id == session_id)
        .values(mfa_satisfied=True, amr=["pwd", "totp"])
    )
    roles = await _roles(session, user.id)
    access, exp = issue_access_token(
        user_id=user.id, hospital_id=user.hospital_id, session_id=session_id,
        roles=[(r.role.value, r.scope_type.value, r.scope_id) for r in roles],
        amr=["pwd", "totp"], mfa_pending=False,
    )  # fmt: skip
    await record(
        session, hospital_id=user.hospital_id, actor=Actor(user.id, "user"),
        entity_type="user", entity_id=user.id, action="auth.totp_enabled",
    )  # fmt: skip
    return codes, access, exp


# ---------- shared device + PIN ----------------------------------------------------------------


async def pin_login(
    hospital_code: str, device_key: str, employee_code: str, pin: str, ip: str, ua: str | None
) -> IssuedSession:
    await hit("pin-device", token_hash(device_key).hex(), limit=30, window_seconds=900)
    async with anonymous_session() as session:
        hid = await resolve_hospital_code(session, hospital_code.strip().upper())
        if hid is None:
            raise invalid_credentials()
        await set_tenant(session, hid)
        device = await session.scalar(
            select(Device).where(Device.device_key_hash == token_hash(device_key))
        )
        if device is None or device.revoked_at is not None:
            raise AppError("DEVICE_NOT_REGISTERED", 401)
        user = await session.scalar(
            select(User).where(
                User.employee_code == employee_code.strip(), User.status == UserStatus.active
            )
        )
        cred = await _credential(session, user) if user else None
        if user is None or cred is None or not cred.pin_hash:
            verify_secret(_DUMMY_HASH, pin)
            raise invalid_credentials()
        _check_lock(cred)
        if not verify_secret(cred.pin_hash, pin):
            await _register_failure(session, cred)
            await session.commit()
            raise invalid_credentials()
        roles = await _roles(session, user.id)
        if _needs_mfa(roles):
            raise invalid_credentials()  # PIN is for frontline staff only
        _register_success(cred)
        device.last_seen_at = _now()
        return await _create_session(
            session, user, amr=["pin"], mfa_pending=False, device_id=device.id,
            user_agent=ua, ip=ip,
        )  # fmt: skip


# ---------- refresh / logout / sessions --------------------------------------------------------


async def refresh(refresh_token: str) -> IssuedSession:
    hid_part, _, _ = refresh_token.partition(".")
    try:
        hid = uuid.UUID(hid_part)
    except ValueError as exc:
        raise unauthorized("INVALID_TOKEN") from exc
    async with tenant_session(hid) as session:
        row = await session.scalar(
            select(RefreshToken)
            .where(RefreshToken.token_hash == token_hash(refresh_token))
            .with_for_update()
        )
        if row is None:
            raise unauthorized("INVALID_TOKEN")
        auth_session = await session.get(AuthSession, row.session_id, with_for_update=True)
        if auth_session is None or auth_session.revoked_at is not None:
            raise unauthorized("SESSION_REVOKED")
        if row.used_at is not None:
            # Reuse of a spent token: assume theft, kill the whole session.
            auth_session.revoked_at = _now()
            auth_session.revoke_reason = "refresh_reuse"
            await record(
                session, hospital_id=hid, actor=Actor(auth_session.user_id, "user"),
                entity_type="session", entity_id=auth_session.id, action="auth.refresh_reuse",
            )  # fmt: skip
            await session.commit()
            raise unauthorized("SESSION_REVOKED")
        if row.expires_at < _now() or auth_session.absolute_expires_at < _now():
            raise unauthorized("SESSION_EXPIRED")
        user = await session.get(User, auth_session.user_id)
        if user is None or user.status != UserStatus.active:
            raise unauthorized("SESSION_REVOKED")
        row.used_at = _now()
        auth_session.last_seen_at = _now()
        new_refresh = await _new_refresh(session, auth_session, parent_id=row.id)
        roles = await _roles(session, user.id)
        mfa_pending = _needs_mfa(roles) and not auth_session.mfa_satisfied
        access, exp = issue_access_token(
            user_id=user.id, hospital_id=hid, session_id=auth_session.id,
            roles=[(r.role.value, r.scope_type.value, r.scope_id) for r in roles],
            amr=list(auth_session.amr), mfa_pending=mfa_pending,
        )  # fmt: skip
        return IssuedSession(access, exp, new_refresh, mfa_pending, user.id, hid)


async def revoke_sessions(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    reason: str,
    only: uuid.UUID | None = None,
    actor: Actor | None = None,
    hospital_id: uuid.UUID,
) -> int:
    stmt = (
        update(AuthSession)
        .where(AuthSession.user_id == user_id, AuthSession.revoked_at.is_(None))
        .values(revoked_at=_now(), revoke_reason=reason)
    )
    if only is not None:
        stmt = stmt.where(AuthSession.id == only)
    result = await session.execute(stmt)
    count = int(getattr(result, "rowcount", 0) or 0)
    await record(
        session, hospital_id=hospital_id, actor=actor or Actor(user_id, "user"),
        entity_type="user", entity_id=user_id, action="auth.sessions_revoked",
        payload={"reason": reason, "count": count},
    )  # fmt: skip
    return count


async def set_password(session: AsyncSession, user: User, password: str) -> None:
    from app.modules.auth.passwords import validate_new_password

    await validate_new_password(password)
    cred = await _credential(session, user)
    cred.password_hash = hash_secret(password)
    cred.password_changed_at = _now()


async def set_pin(session: AsyncSession, user: User, pin: str) -> None:
    if not (pin.isdigit() and 4 <= len(pin) <= 6):
        raise AppError("PIN_INVALID", 422)
    if len(set(pin)) == 1 or pin in "0123456789" or pin in "9876543210":
        raise AppError("PIN_TOO_SIMPLE", 422)
    cred = await _credential(session, user)
    cred.pin_hash = hash_secret(pin)


def new_device_key() -> str:
    return new_token(24)
