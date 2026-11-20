"""Staff routes: users, roles, credentials set by admins, agencies, vendors, shifts, roster, devices, check-ins."""

import uuid
from datetime import date
from typing import Any

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select

from app.audit.service import record
from app.core.crud import crud_router
from app.core.crypto import token_hash
from app.core.errors import AppError, not_found
from app.modules.auth.service import new_device_key, set_password, set_pin
from app.modules.staff import schemas as sc
from app.modules.staff import service as svc
from app.modules.staff.models import (
    Agency,
    Device,
    RosterEntry,
    Shift,
    ShiftCheckin,
    User,
    UserStatus,
    Vendor,
)
from app.policy.deps import DB, Access, requires
from app.policy.permissions import Perm, Scope

router = APIRouter(tags=["staff"])


# ---------- users ----------


@router.get("/users", response_model=list[sc.UserOut])
async def list_users(
    db: DB,
    access: Access = Depends(requires(Perm.staff_view)),
    status: UserStatus | None = UserStatus.active,
    department_id: uuid.UUID | None = None,
    limit: int = Query(200, ge=1, le=500),
    offset: int = Query(0, ge=0),
) -> Any:
    stmt = svc.scoped_users(access)
    if status:
        stmt = stmt.where(User.status == status)
    if department_id:
        stmt = stmt.where(User.department_id == department_id)
    users = (await db.scalars(stmt.order_by(User.display_name).limit(limit).offset(offset))).all()
    roles = await svc.roles_by_user(db, [u.id for u in users])
    return [svc.to_out(u, roles.get(u.id, []), access) for u in users]


@router.get("/users/{user_id}", response_model=sc.UserOut)
async def get_user(
    user_id: uuid.UUID, db: DB, access: Access = Depends(requires(Perm.staff_view))
) -> Any:
    user = await svc.get_user_in_scope(db, access, user_id)
    roles = await svc.roles_by_user(db, [user.id])
    return svc.to_out(user, roles.get(user.id, []), access)


@router.post("/users", response_model=sc.UserOut, status_code=201)
async def create_user(
    body: sc.UserIn, db: DB, access: Access = Depends(requires(Perm.staff_manage))
) -> Any:
    user = await svc.create_user(db, access, body)
    roles = await svc.roles_by_user(db, [user.id])
    return svc.to_out(user, roles.get(user.id, []), access)


@router.patch("/users/{user_id}", response_model=sc.UserOut)
async def update_user(
    user_id: uuid.UUID,
    body: sc.UserPatch,
    db: DB,
    access: Access = Depends(requires(Perm.staff_manage)),
) -> Any:
    user = await svc.get_user_in_scope(db, access, user_id)
    await svc.update_user(db, access, user, body)
    roles = await svc.roles_by_user(db, [user.id])
    return svc.to_out(user, roles.get(user.id, []), access)


@router.put("/users/{user_id}/roles", response_model=sc.UserOut)
async def put_roles(
    user_id: uuid.UUID,
    body: list[sc.RoleGrantIn],
    db: DB,
    access: Access = Depends(requires(Perm.staff_manage)),
) -> Any:
    if not 1 <= len(body) <= 10:
        raise AppError("ROLES_COUNT_INVALID", 422)
    user = await svc.get_user_in_scope(db, access, user_id)
    await svc.replace_roles(db, access, user, body)
    roles = await svc.roles_by_user(db, [user.id])
    return svc.to_out(user, roles.get(user.id, []), access)


@router.post("/users/{user_id}/deactivate", status_code=204)
async def deactivate(
    user_id: uuid.UUID, db: DB, access: Access = Depends(requires(Perm.staff_manage))
) -> None:
    user = await svc.get_user_in_scope(db, access, user_id)
    await svc.deactivate_user(db, access, user)


@router.put("/users/{user_id}/pin", status_code=204)
async def admin_set_pin(
    user_id: uuid.UUID,
    body: sc.SetPinIn,
    db: DB,
    access: Access = Depends(requires(Perm.staff_manage)),
) -> None:
    user = await svc.get_user_in_scope(db, access, user_id)
    roles = await svc.roles_by_user(db, [user.id])
    if svc.needs_mfa(roles.get(user.id, [])):
        raise AppError("PIN_NOT_ALLOWED_FOR_ROLE", 422)
    await set_pin(db, user, body.pin)
    await record(
        db, hospital_id=user.hospital_id, actor=svc.actor_of(access), entity_type="user",
        entity_id=user.id, action="user.pin_set",
    )  # fmt: skip


@router.put("/users/{user_id}/password", status_code=204)
async def admin_set_password(
    user_id: uuid.UUID,
    body: sc.SetPasswordIn,
    db: DB,
    access: Access = Depends(requires(Perm.staff_manage)),
) -> None:
    """Sets an initial/temporary password (hospital-wide admins only) and signs the user out everywhere."""
    if access.scope < Scope.hospital:
        raise AppError("FORBIDDEN", 403)
    user = await svc.get_user_in_scope(db, access, user_id)
    await set_password(db, user, body.password)
    await record(
        db, hospital_id=user.hospital_id, actor=svc.actor_of(access), entity_type="user",
        entity_id=user.id, action="user.password_set",
    )  # fmt: skip
    from app.modules.auth.service import revoke_sessions

    await revoke_sessions(
        db, user_id=user.id, reason="password_set", actor=svc.actor_of(access),
        hospital_id=user.hospital_id,
    )  # fmt: skip


# ---------- devices (shared phones/tablets for PIN sign-in) ----------


@router.get("/devices", response_model=list[sc.DeviceOut])
async def list_devices(db: DB, access: Access = Depends(requires(Perm.device_manage))) -> Any:
    return (await db.scalars(select(Device).order_by(Device.created_at.desc()))).all()


@router.post("/devices", response_model=sc.DeviceRegistered, status_code=201)
async def register_device(
    body: sc.DeviceIn, db: DB, access: Access = Depends(requires(Perm.device_manage))
) -> Any:
    key = new_device_key()
    device = Device(
        hospital_id=access.principal.hospital_id, label=body.label,
        device_key_hash=token_hash(key), registered_by=access.principal.user_id,
    )  # fmt: skip
    db.add(device)
    await db.flush()
    await record(
        db, hospital_id=device.hospital_id, actor=svc.actor_of(access), entity_type="device",
        entity_id=device.id, action="device.registered",
    )  # fmt: skip
    await db.refresh(device)
    return sc.DeviceRegistered(**sc.DeviceOut.model_validate(device).model_dump(), device_key=key)


@router.post("/devices/{device_id}/revoke", status_code=204)
async def revoke_device(
    device_id: uuid.UUID, db: DB, access: Access = Depends(requires(Perm.device_manage))
) -> None:
    device = await db.get(Device, device_id, with_for_update=True)
    if device is None or device.revoked_at is not None:
        raise not_found("device")
    device.revoked_at = func.now()
    await record(
        db, hospital_id=device.hospital_id, actor=svc.actor_of(access), entity_type="device",
        entity_id=device.id, action="device.revoked",
    )  # fmt: skip


# ---------- roster & check-ins ----------


@router.get("/roster", response_model=list[sc.RosterOut])
async def list_roster(
    db: DB,
    access: Access = Depends(requires(Perm.roster_manage)),
    from_date: date = Query(...),
    to_date: date = Query(...),
) -> Any:
    if (to_date - from_date).days > 62:
        raise AppError("RANGE_TOO_LONG", 422, max_days=62)
    stmt = select(RosterEntry).where(RosterEntry.work_date.between(from_date, to_date))
    if access.scope < Scope.hospital:
        stmt = stmt.where(RosterEntry.department_id.in_(access.department_ids))
    return (await db.scalars(stmt.order_by(RosterEntry.work_date))).all()


@router.post("/roster", response_model=sc.RosterOut, status_code=201)
async def create_roster(
    body: sc.RosterIn, db: DB, access: Access = Depends(requires(Perm.roster_manage))
) -> Any:
    if access.scope < Scope.hospital and body.department_id not in access.department_ids:
        raise AppError("FORBIDDEN", 403)
    entry = RosterEntry(hospital_id=access.principal.hospital_id, **body.model_dump())
    db.add(entry)
    await db.flush()
    await record(
        db, hospital_id=entry.hospital_id, actor=svc.actor_of(access), entity_type="roster_entry",
        entity_id=entry.id, action="roster.created",
    )  # fmt: skip
    return entry


@router.delete("/roster/{entry_id}", status_code=204)
async def delete_roster(
    entry_id: uuid.UUID, db: DB, access: Access = Depends(requires(Perm.roster_manage))
) -> None:
    entry = await db.get(RosterEntry, entry_id)
    if entry is None or (
        access.scope < Scope.hospital and entry.department_id not in access.department_ids
    ):
        raise not_found("roster_entry")
    await db.delete(entry)
    await record(
        db, hospital_id=entry.hospital_id, actor=svc.actor_of(access), entity_type="roster_entry",
        entity_id=entry.id, action="roster.deleted",
    )  # fmt: skip


@router.post("/checkins", response_model=sc.CheckinOut, status_code=201)
async def check_in(
    body: sc.CheckinIn, db: DB, access: Access = Depends(requires(Perm.self_service))
) -> Any:
    row = ShiftCheckin(
        hospital_id=access.principal.hospital_id, user_id=access.principal.user_id,
        roster_entry_id=body.roster_entry_id, kind=body.kind, method=body.method,
    )  # fmt: skip
    db.add(row)
    await db.flush()
    await db.refresh(row)
    return row


# ---------- simple config entities ----------

router.include_router(
    crud_router(
        model=Agency, path="/agencies", entity="agency",
        create_schema=sc.AgencyIn, update_schema=sc.AgencyPatch, read_schema=sc.AgencyOut,
        view_perm=Perm.staff_view, manage_perm=Perm.vendor_manage, order_by=("name",),
    )
)  # fmt: skip
router.include_router(
    crud_router(
        model=Vendor, path="/vendors", entity="vendor",
        create_schema=sc.VendorIn, update_schema=sc.VendorPatch, read_schema=sc.VendorOut,
        view_perm=Perm.staff_view, manage_perm=Perm.vendor_manage, order_by=("name",),
    )
)  # fmt: skip
router.include_router(
    crud_router(
        model=Shift, path="/shifts", entity="shift",
        create_schema=sc.ShiftIn, update_schema=sc.ShiftPatch, read_schema=sc.ShiftOut,
        view_perm=Perm.org_view, manage_perm=Perm.roster_manage, order_by=("starts_at",),
    )
)  # fmt: skip
