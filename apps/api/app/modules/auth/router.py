"""Auth routes. Refresh token lives in an HttpOnly cookie scoped to /api/v1/auth, with a
double-submit CSRF token (non-HttpOnly cookie echoed in the X-CSRF-Token header)."""

import uuid
from typing import Any

from fastapi import APIRouter, Depends, Request, Response
from pydantic import EmailStr, Field
from sqlalchemy import select

from app.audit.service import Actor, record
from app.core.config import get_settings
from app.core.crypto import constant_time_equals, new_token, verify_secret
from app.core.errors import AppError, unauthorized
from app.core.schemas import In, Out
from app.modules.auth import service as auth
from app.modules.auth.models import AuthSession, Credential
from app.modules.org.models import Hospital
from app.modules.staff.models import User
from app.policy.deps import DB, Access, public, requires, resolve_access
from app.policy.permissions import Perm

router = APIRouter(prefix="/auth", tags=["auth"])
me_router = APIRouter(tags=["me"])

REFRESH_COOKIE = "oglos_rt"
CSRF_COOKIE = "oglos_csrf"
COOKIE_PATH = "/api/v1/auth"

HospitalCode = Field(min_length=2, max_length=24, pattern=r"^[A-Za-z0-9-]+$")


class OtpRequestIn(In):
    hospital_code: str = HospitalCode
    email: EmailStr


class OtpRequestOut(Out):
    challenge_id: uuid.UUID
    expires_in_seconds: int = 300


class OtpVerifyIn(In):
    hospital_code: str = HospitalCode
    challenge_id: uuid.UUID
    code: str = Field(min_length=6, max_length=6, pattern=r"^\d{6}$")


class PasswordLoginIn(In):
    hospital_code: str = HospitalCode
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


class TotpLoginIn(In):
    mfa_token: str = Field(min_length=10, max_length=2000)
    code: str = Field(min_length=6, max_length=17)


class PinLoginIn(In):
    hospital_code: str = HospitalCode
    device_key: str = Field(min_length=16, max_length=100)
    employee_code: str = Field(min_length=1, max_length=32)
    pin: str = Field(min_length=4, max_length=6, pattern=r"^\d+$")


class TokenOut(Out):
    access_token: str
    expires_at: int
    mfa_pending: bool = False
    mfa_token: str | None = None
    totp_required: bool = False


class TotpEnrolOut(Out):
    otpauth_uri: str


class TotpConfirmIn(In):
    code: str = Field(min_length=6, max_length=6, pattern=r"^\d{6}$")


class TotpConfirmOut(Out):
    recovery_codes: list[str]
    access_token: str
    expires_at: int


class SessionOut(Out):
    id: uuid.UUID
    user_agent_summary: str | None
    created_at: Any
    last_seen_at: Any
    current: bool = False


class ChangePasswordIn(In):
    current_password: str = Field(min_length=1, max_length=128)
    new_password: str = Field(min_length=10, max_length=128)


def _ip(request: Request) -> str:
    return request.client.host if request.client else "unknown"


def _issue(response: Response, issued: auth.IssuedSession) -> TokenOut:
    secure = True  # browsers treat http://localhost as a secure context, so this works in dev too
    response.set_cookie(
        REFRESH_COOKIE, issued.refresh_token, httponly=True, secure=secure, samesite="strict",
        path=COOKIE_PATH, max_age=get_settings().refresh_token_days * 86400,
    )  # fmt: skip
    response.set_cookie(
        CSRF_COOKIE, new_token(16), httponly=False, secure=secure, samesite="strict",
        path="/", max_age=get_settings().refresh_token_days * 86400,
    )  # fmt: skip
    return TokenOut(
        access_token=issued.access_token, expires_at=issued.access_expires_at,
        mfa_pending=issued.mfa_pending,
    )  # fmt: skip


def _clear(response: Response) -> None:
    response.delete_cookie(REFRESH_COOKIE, path=COOKIE_PATH)
    response.delete_cookie(CSRF_COOKIE, path="/")


@router.post(
    "/otp/request", response_model=OtpRequestOut, status_code=202, dependencies=[Depends(public())]
)
async def otp_request(body: OtpRequestIn, request: Request) -> Any:
    challenge_id = await auth.request_email_otp(body.hospital_code, str(body.email), _ip(request))
    return OtpRequestOut(challenge_id=challenge_id)


@router.post("/otp/verify", response_model=TokenOut, dependencies=[Depends(public())])
async def otp_verify(body: OtpVerifyIn, request: Request, response: Response) -> Any:
    issued = await auth.verify_email_otp(
        body.hospital_code,
        body.challenge_id,
        body.code,
        _ip(request),
        request.headers.get("user-agent"),
    )
    return _issue(response, issued)


@router.post("/password/login", response_model=TokenOut, dependencies=[Depends(public())])
async def password_login(body: PasswordLoginIn, request: Request, response: Response) -> Any:
    result = await auth.password_login(
        body.hospital_code,
        str(body.email),
        body.password,
        _ip(request),
        request.headers.get("user-agent"),
    )
    if isinstance(result, str):
        return TokenOut(access_token="", expires_at=0, totp_required=True, mfa_token=result)
    return _issue(response, result)


@router.post("/totp/verify", response_model=TokenOut, dependencies=[Depends(public())])
async def totp_verify(body: TotpLoginIn, request: Request, response: Response) -> Any:
    issued = await auth.totp_login(
        body.mfa_token, body.code, _ip(request), request.headers.get("user-agent")
    )
    return _issue(response, issued)


@router.post("/pin/login", response_model=TokenOut, dependencies=[Depends(public())])
async def pin_login(body: PinLoginIn, request: Request, response: Response) -> Any:
    issued = await auth.pin_login(
        body.hospital_code, body.device_key, body.employee_code, body.pin, _ip(request),
        request.headers.get("user-agent"),
    )  # fmt: skip
    return _issue(response, issued)


@router.post("/refresh", response_model=TokenOut, dependencies=[Depends(public())])
async def refresh(request: Request, response: Response) -> Any:
    token = request.cookies.get(REFRESH_COOKIE)
    csrf_cookie = request.cookies.get(CSRF_COOKIE, "")
    csrf_header = request.headers.get("x-csrf-token", "")
    if not token:
        raise unauthorized("NO_REFRESH_TOKEN")
    if not csrf_cookie or not constant_time_equals(csrf_cookie.encode(), csrf_header.encode()):
        raise AppError("CSRF_FAILED", 403)
    try:
        issued = await auth.refresh(token)
    except AppError:
        _clear(response)
        raise
    return _issue(response, issued)


@router.post("/totp/enroll", response_model=TotpEnrolOut)
async def totp_enroll(
    db: DB, access: Access = Depends(requires(Perm.self_service, allow_mfa_pending=True))
) -> Any:
    return TotpEnrolOut(otpauth_uri=await auth.totp_begin_enrolment(db, access.principal.user_id))


@router.post("/totp/confirm", response_model=TotpConfirmOut)
async def totp_confirm(
    body: TotpConfirmIn,
    db: DB,
    access: Access = Depends(requires(Perm.self_service, allow_mfa_pending=True)),
) -> Any:
    codes, token, exp = await auth.totp_confirm_enrolment(
        db, access.principal.user_id, access.principal.session_id, body.code
    )
    return TotpConfirmOut(recovery_codes=codes, access_token=token, expires_at=exp)


@router.post("/logout", status_code=204)
async def logout(
    response: Response,
    db: DB,
    access: Access = Depends(requires(Perm.self_service, allow_mfa_pending=True)),
) -> None:
    p = access.principal
    await auth.revoke_sessions(
        db, user_id=p.user_id, reason="logout", only=p.session_id, hospital_id=p.hospital_id
    )
    _clear(response)


@router.get("/sessions", response_model=list[SessionOut])
async def list_sessions(db: DB, access: Access = Depends(requires(Perm.self_service))) -> Any:
    rows = (
        await db.scalars(
            select(AuthSession)
            .where(
                AuthSession.user_id == access.principal.user_id, AuthSession.revoked_at.is_(None)
            )
            .order_by(AuthSession.created_at.desc())
        )
    ).all()
    return [
        SessionOut(
            id=r.id,
            user_agent_summary=r.user_agent_summary,
            created_at=r.created_at,
            last_seen_at=r.last_seen_at,
            current=r.id == access.principal.session_id,
        )  # fmt: skip
        for r in rows
    ]


@router.delete("/sessions/{session_id}", status_code=204)
async def revoke_session(
    session_id: uuid.UUID, db: DB, access: Access = Depends(requires(Perm.self_service))
) -> None:
    p = access.principal
    count = await auth.revoke_sessions(
        db, user_id=p.user_id, reason="user_revoked", only=session_id, hospital_id=p.hospital_id
    )
    if not count:
        raise AppError("NOT_FOUND", 404)


@router.post("/sessions/revoke-all", status_code=204)
async def revoke_all(
    response: Response, db: DB, access: Access = Depends(requires(Perm.self_service))
) -> None:
    p = access.principal
    await auth.revoke_sessions(
        db, user_id=p.user_id, reason="log_out_everywhere", hospital_id=p.hospital_id
    )
    _clear(response)


@router.post("/password/change", status_code=204)
async def change_password(
    body: ChangePasswordIn,
    response: Response,
    db: DB,
    access: Access = Depends(requires(Perm.self_service)),
) -> None:
    p = access.principal
    cred = await db.get(Credential, p.user_id, with_for_update=True)
    if (
        cred is None
        or not cred.password_hash
        or not verify_secret(cred.password_hash, body.current_password)
    ):
        raise auth.invalid_credentials()
    user = await db.get(User, p.user_id)
    assert user is not None  # noqa: S101 - session check guarantees the user exists
    await auth.set_password(db, user, body.new_password)
    await record(
        db, hospital_id=p.hospital_id, actor=Actor(p.user_id, p.primary_role), entity_type="user",
        entity_id=p.user_id, action="user.password_changed",
    )  # fmt: skip
    await auth.revoke_sessions(
        db, user_id=p.user_id, reason="password_change", hospital_id=p.hospital_id
    )
    _clear(response)


# ---------- /me ----------


class MeOut(Out):
    id: uuid.UUID
    display_name: str
    employee_code: str
    preferred_language: str
    hospital: dict[str, str]
    roles: list[dict[str, Any]]
    permissions: dict[str, str]  # perm -> widest scope name, for the UI to show/hide things
    mfa_pending: bool


@me_router.get("/me", response_model=MeOut)
async def me(
    db: DB, access: Access = Depends(requires(Perm.self_service, allow_mfa_pending=True))
) -> Any:
    p = access.principal
    user = await db.get(User, p.user_id)
    hospital = await db.get(Hospital, p.hospital_id)
    if user is None or hospital is None:
        raise unauthorized()
    perms = {}
    for perm in Perm:
        a = resolve_access(p, perm)
        if a is not None:
            perms[perm.value] = a.scope.name
    return MeOut(
        id=user.id, display_name=user.display_name, employee_code=user.employee_code,
        preferred_language=user.preferred_language.value,
        hospital={"id": str(hospital.id), "code": hospital.code, "name": hospital.name},
        roles=[{"role": r.role.value, "scope_type": r.scope_type.value,
                "scope_id": str(r.scope_id) if r.scope_id else None} for r in p.roles],
        permissions=perms, mfa_pending=p.mfa_pending,
    )  # fmt: skip
