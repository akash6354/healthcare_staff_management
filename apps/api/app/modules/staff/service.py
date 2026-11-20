"""Staff management rules: scope checks, role assignment limits, encryption of phone numbers."""

import uuid
from collections.abc import Sequence
from datetime import UTC, datetime

from sqlalchemy import Select, delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.audit.service import Actor, record
from app.core.crypto import decrypt_field, encrypt_field, lookup_hash, mask_phone
from app.core.errors import AppError, forbidden, not_found
from app.modules.auth.service import revoke_sessions
from app.modules.staff.models import Role, ScopeType, User, UserRole, UserStatus
from app.modules.staff.schemas import RoleGrantIn, RoleGrantOut, UserIn, UserOut, UserPatch
from app.policy.deps import Access, resolve_access
from app.policy.permissions import MFA_REQUIRED_ROLES, Perm, Scope

# Roles a department head may grant inside their own department.
DEPT_GRANTABLE: frozenset[Role] = frozenset({Role.worker, Role.supervisor, Role.requester})


def actor_of(access: Access) -> Actor:
    return Actor(access.principal.user_id, access.principal.primary_role)


def scoped_users(access: Access) -> Select[tuple[User]]:
    stmt = select(User)
    if access.scope >= Scope.hospital:
        return stmt
    if access.scope >= Scope.department and access.department_ids:
        return stmt.where(User.department_id.in_(access.department_ids))
    return stmt.where(User.id == access.principal.user_id)


async def get_user_in_scope(db: AsyncSession, access: Access, user_id: uuid.UUID) -> User:
    user = await db.scalar(scoped_users(access).where(User.id == user_id))
    if user is None:
        raise not_found("user")
    return user


def _check_department_in_scope(access: Access, department_id: uuid.UUID | None) -> None:
    if access.scope >= Scope.hospital:
        return
    if department_id is None or department_id not in access.department_ids:
        raise forbidden()


def _check_grants(access: Access, grants: Sequence[RoleGrantIn]) -> None:
    if access.scope >= Scope.hospital:
        return
    for g in grants:
        if g.role not in DEPT_GRANTABLE:
            raise AppError("ROLE_NOT_GRANTABLE", 403, role=g.role.value)
        if g.scope_type == ScopeType.hospital:
            raise AppError("ROLE_SCOPE_TOO_WIDE", 403)
        if g.scope_type == ScopeType.department and g.scope_id not in access.department_ids:
            raise forbidden()


def to_out(user: User, roles: Sequence[UserRole], viewer: Access) -> UserOut:
    out = UserOut.model_validate(user)
    out.roles = [RoleGrantOut.model_validate(r) for r in roles]
    if user.phone_enc:
        phone = decrypt_field(user.phone_enc)
        can_see = resolve_access(viewer.principal, Perm.staff_manage) is not None
        out.phone = phone if can_see else mask_phone(phone)
    return out


async def roles_by_user(
    db: AsyncSession, user_ids: Sequence[uuid.UUID]
) -> dict[uuid.UUID, list[UserRole]]:
    rows = (await db.scalars(select(UserRole).where(UserRole.user_id.in_(user_ids)))).all()
    out: dict[uuid.UUID, list[UserRole]] = {}
    for r in rows:
        out.setdefault(r.user_id, []).append(r)
    return out


async def create_user(db: AsyncSession, access: Access, body: UserIn) -> User:
    _check_department_in_scope(access, body.department_id)
    _check_grants(access, body.roles)
    data = body.model_dump(exclude={"roles", "phone"})
    user = User(hospital_id=access.principal.hospital_id, **data)
    if body.phone:
        user.phone_enc = encrypt_field(body.phone)
        user.phone_hash = lookup_hash(body.phone)
    db.add(user)
    await db.flush()
    for g in body.roles:
        db.add(UserRole(hospital_id=user.hospital_id, user_id=user.id, **g.model_dump()))
    await db.flush()
    await record(
        db, hospital_id=user.hospital_id, actor=actor_of(access), entity_type="user",
        entity_id=user.id, action="user.created",
        payload={"roles": sorted({g.role.value for g in body.roles})},
    )  # fmt: skip
    return user


async def update_user(db: AsyncSession, access: Access, user: User, body: UserPatch) -> User:
    changes = body.model_dump(exclude_unset=True)
    if "department_id" in changes:
        _check_department_in_scope(access, changes["department_id"])
    if "phone" in changes:
        phone = changes.pop("phone")
        user.phone_enc = encrypt_field(phone) if phone else None
        user.phone_hash = lookup_hash(phone) if phone else None
        changes["phone"] = "***"
    for key, value in changes.items():
        if key != "phone":
            setattr(user, key, value)
    await db.flush()
    await record(
        db, hospital_id=user.hospital_id, actor=actor_of(access), entity_type="user",
        entity_id=user.id, action="user.updated", payload={"fields": sorted(changes)},
    )  # fmt: skip
    return user


async def replace_roles(
    db: AsyncSession, access: Access, user: User, grants: Sequence[RoleGrantIn]
) -> None:
    if user.id == access.principal.user_id:
        raise AppError("CANNOT_CHANGE_OWN_ROLES", 403)
    _check_grants(access, grants)
    existing = (await db.scalars(select(UserRole).where(UserRole.user_id == user.id))).all()
    if access.scope < Scope.hospital and any(r.role not in DEPT_GRANTABLE for r in existing):
        raise forbidden()  # a dept head can't strip an admin/manager role
    await db.execute(delete(UserRole).where(UserRole.user_id == user.id))
    for g in grants:
        db.add(UserRole(hospital_id=user.hospital_id, user_id=user.id, **g.model_dump()))
    await db.flush()
    await record(
        db, hospital_id=user.hospital_id, actor=actor_of(access), entity_type="user",
        entity_id=user.id, action="user.roles_changed",
        payload={"roles": sorted({g.role.value for g in grants})},
    )  # fmt: skip
    # Role change: revoke sessions so new tokens carry the new roles (security.md §2).
    await revoke_sessions(
        db, user_id=user.id, reason="role_change", actor=actor_of(access),
        hospital_id=user.hospital_id,
    )  # fmt: skip


async def deactivate_user(db: AsyncSession, access: Access, user: User) -> None:
    if user.id == access.principal.user_id:
        raise AppError("CANNOT_DEACTIVATE_SELF", 403)
    if user.status != UserStatus.active:
        raise AppError("USER_NOT_ACTIVE", 409)
    user.status = UserStatus.deactivated
    user.deactivated_at = datetime.now(UTC)
    await db.flush()
    await record(
        db, hospital_id=user.hospital_id, actor=actor_of(access), entity_type="user",
        entity_id=user.id, action="user.deactivated", from_state="active", to_state="deactivated",
    )  # fmt: skip
    await revoke_sessions(
        db, user_id=user.id, reason="deactivated", actor=actor_of(access),
        hospital_id=user.hospital_id,
    )  # fmt: skip


def needs_mfa(roles: Sequence[UserRole]) -> bool:
    return any(r.role in MFA_REQUIRED_ROLES for r in roles)
