"""Request-level auth: decode the access token, bind the DB transaction to the tenant, check permission.

Every /api/v1 route must depend on either `requires(<perm>)` or `public()`. `assert_all_routes_declared`
runs at startup and in CI, so an undeclared route fails loudly instead of being silently open.
"""

import uuid
from collections.abc import AsyncIterator, Callable, Coroutine
from dataclasses import dataclass, field
from typing import Annotated, Any

from fastapi import Depends, FastAPI, Request
from fastapi.dependencies.models import Dependant
from fastapi.routing import APIRoute
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import tenant_session
from app.core.errors import AppError, forbidden, unauthorized
from app.modules.auth.tokens import AccessClaims, decode_access_token
from app.modules.staff.models import Role, ScopeType
from app.policy.permissions import ROLE_PERMISSIONS, Perm, Scope

_bearer = HTTPBearer(auto_error=False)


@dataclass(frozen=True)
class RoleGrant:
    role: Role
    scope_type: ScopeType
    scope_id: uuid.UUID | None


@dataclass(frozen=True)
class Principal:
    user_id: uuid.UUID
    hospital_id: uuid.UUID
    session_id: uuid.UUID
    roles: tuple[RoleGrant, ...]
    mfa_pending: bool = False

    @property
    def primary_role(self) -> str:
        return self.roles[0].role.value if self.roles else "none"


@dataclass(frozen=True)
class Access:
    """What the caller may do for one permission: the widest scope plus the ids it covers."""

    principal: Principal
    perm: Perm
    scope: Scope
    department_ids: frozenset[uuid.UUID] = field(default_factory=frozenset)
    area_ids: frozenset[uuid.UUID] = field(default_factory=frozenset)
    vendor_ids: frozenset[uuid.UUID] = field(default_factory=frozenset)

    @property
    def hospital_wide(self) -> bool:
        return self.scope == Scope.hospital


def resolve_access(principal: Principal, perm: Perm) -> Access | None:
    best: Scope | None = None
    depts: set[uuid.UUID] = set()
    areas: set[uuid.UUID] = set()
    vendors: set[uuid.UUID] = set()
    for grant in principal.roles:
        level = ROLE_PERMISSIONS.get(grant.role, {}).get(perm)
        if level is None:
            continue
        # A role scoped narrower than its permission level narrows the grant.
        if grant.scope_type == ScopeType.department and level > Scope.department:
            level = Scope.department
        if grant.scope_type == ScopeType.area and level > Scope.area:
            level = Scope.area
        if grant.scope_type == ScopeType.vendor:
            level = Scope.vendor
        if grant.scope_id:
            {
                ScopeType.department: depts,
                ScopeType.area: areas,
                ScopeType.vendor: vendors,
            }.get(grant.scope_type, set()).add(grant.scope_id)
        best = level if best is None else max(best, level)
    if best is None:
        return None
    return Access(principal, perm, best, frozenset(depts), frozenset(areas), frozenset(vendors))


async def current_claims(
    creds: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
) -> AccessClaims:
    if creds is None or creds.scheme.lower() != "bearer":
        raise unauthorized()
    return decode_access_token(creds.credentials)


async def db_session(
    request: Request, claims: Annotated[AccessClaims, Depends(current_claims)]
) -> AsyncIterator[AsyncSession]:
    """Tenant-bound transaction for this request; also re-checks that the session is still live."""
    from app.modules.auth.models import AuthSession
    from app.modules.staff.models import User, UserStatus

    async with tenant_session(claims.hid, claims.sub) as session:
        row = (
            await session.execute(
                select(AuthSession.revoked_at, User.status)
                .join(User, User.id == AuthSession.user_id)
                .where(AuthSession.id == claims.sid, AuthSession.user_id == claims.sub)
            )
        ).first()
        if row is None or row.revoked_at is not None or row.status != UserStatus.active:
            raise unauthorized("SESSION_REVOKED")
        request.state.claims = claims
        yield session


async def current_principal(
    claims: Annotated[AccessClaims, Depends(current_claims)],
    _db: Annotated[AsyncSession, Depends(db_session)],
) -> Principal:
    return Principal(
        user_id=claims.sub,
        hospital_id=claims.hid,
        session_id=claims.sid,
        roles=tuple(RoleGrant(Role(r[0]), ScopeType(r[1]), r[2]) for r in claims.roles),
        mfa_pending=claims.mfa_pending,
    )


def requires(
    perm: Perm, *, allow_mfa_pending: bool = False
) -> Callable[..., Coroutine[Any, Any, Access]]:
    async def dependency(
        principal: Annotated[Principal, Depends(current_principal)],
    ) -> Access:
        if principal.mfa_pending and not allow_mfa_pending:
            raise AppError("MFA_ENROLLMENT_REQUIRED", 403)
        access = resolve_access(principal, perm)
        if access is None:
            raise forbidden()
        return access

    dependency.__oglos_permission__ = perm  # type: ignore[attr-defined]
    return dependency


def public() -> Callable[[], Coroutine[Any, Any, None]]:
    """Explicit marker for unauthenticated routes (login, public QR, health)."""

    async def dependency() -> None:
        return None

    dependency.__oglos_public__ = True  # type: ignore[attr-defined]
    return dependency


DB = Annotated[AsyncSession, Depends(db_session)]


def _declared(dep: Dependant) -> bool:
    call = dep.call
    if call is not None and (
        getattr(call, "__oglos_permission__", None) or getattr(call, "__oglos_public__", False)
    ):
        return True
    return any(_declared(d) for d in dep.dependencies)


def undeclared_routes(app: FastAPI) -> list[str]:
    return [
        f"{sorted(r.methods)} {r.path}"
        for r in app.routes
        if isinstance(r, APIRoute) and r.path.startswith("/api/") and not _declared(r.dependant)
    ]


def assert_all_routes_declared(app: FastAPI) -> None:
    missing = undeclared_routes(app)
    if missing:
        raise RuntimeError(f"Routes without requires()/public(): {missing}")
