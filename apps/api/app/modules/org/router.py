"""Org routes: hospital profile, settings, modules, and the building/floor/area structure."""

from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy import select

from app.audit.service import Actor, record
from app.core.crud import crud_router
from app.core.errors import not_found
from app.modules.org import schemas as sc
from app.modules.org.models import (
    Area,
    AreaType,
    Branch,
    Building,
    Department,
    Desk,
    Floor,
    Hospital,
    HospitalModule,
    HospitalSettings,
)
from app.policy.deps import DB, Access, requires
from app.policy.permissions import Perm

router = APIRouter(tags=["org"])


@router.get("/hospital", response_model=sc.HospitalOut)
async def get_hospital(db: DB, access: Access = Depends(requires(Perm.org_view))) -> Any:
    hospital = await db.get(Hospital, access.principal.hospital_id)
    if hospital is None:
        raise not_found("hospital")
    return hospital


@router.patch("/hospital", response_model=sc.HospitalOut)
async def update_hospital(
    body: sc.HospitalUpdate, db: DB, access: Access = Depends(requires(Perm.settings_manage))
) -> Any:
    # oglos_app may only UPDATE (name, city) on its own hospital row (column grant + RLS).
    hospital = await db.get(Hospital, access.principal.hospital_id, with_for_update=True)
    if hospital is None:
        raise not_found("hospital")
    changes = body.model_dump(exclude_unset=True, exclude_none=True)
    for key, value in changes.items():
        setattr(hospital, key, value)
    await db.flush()
    await record(
        db, hospital_id=hospital.id,
        actor=Actor(access.principal.user_id, access.principal.primary_role),
        entity_type="hospital", entity_id=hospital.id, action="hospital.updated",
        payload={"fields": sorted(changes)},
    )  # fmt: skip
    await db.refresh(hospital)
    return hospital


@router.get("/hospital/settings", response_model=sc.SettingsOut)
async def get_settings_doc(db: DB, access: Access = Depends(requires(Perm.settings_view))) -> Any:
    row = await db.get(HospitalSettings, access.principal.hospital_id)
    if row is None:
        raise not_found("settings")
    return sc.SettingsOut(
        schema_version=row.schema_version,
        settings=sc.HospitalSettingsV1.model_validate(row.settings),
        updated_at=row.updated_at,
    )


@router.put("/hospital/settings", response_model=sc.SettingsOut)
async def put_settings_doc(
    body: sc.HospitalSettingsV1, db: DB, access: Access = Depends(requires(Perm.settings_manage))
) -> Any:
    row = await db.get(HospitalSettings, access.principal.hospital_id, with_for_update=True)
    if row is None:
        raise not_found("settings")
    before = sc.HospitalSettingsV1.model_validate(row.settings).model_dump(mode="json")
    after = body.model_dump(mode="json")
    row.settings = after
    row.updated_by = access.principal.user_id
    await db.flush()
    changed = sorted(k for k in after if after[k] != before.get(k))
    await record(
        db, hospital_id=access.principal.hospital_id,
        actor=Actor(access.principal.user_id, access.principal.primary_role),
        entity_type="hospital_settings", entity_id=access.principal.hospital_id,
        action="settings.updated", payload={"sections": changed},
    )  # fmt: skip
    await db.refresh(row)
    return sc.SettingsOut(
        schema_version=row.schema_version, settings=body, updated_at=row.updated_at
    )


@router.get("/hospital/modules", response_model=list[sc.ModuleOut])
async def list_modules(db: DB, access: Access = Depends(requires(Perm.settings_view))) -> Any:
    return (await db.scalars(select(HospitalModule).order_by(HospitalModule.module))).all()


router.include_router(
    crud_router(
        model=Building, path="/buildings", entity="building",
        create_schema=sc.BuildingIn, update_schema=sc.BuildingPatch, read_schema=sc.BuildingOut,
        view_perm=Perm.org_view, manage_perm=Perm.org_manage, order_by=("sort", "name"),
    )
)  # fmt: skip
router.include_router(
    crud_router(
        model=Floor, path="/floors", entity="floor",
        create_schema=sc.FloorIn, update_schema=sc.FloorPatch, read_schema=sc.FloorOut,
        view_perm=Perm.org_view, manage_perm=Perm.org_manage, order_by=("level",),
        filters=("building_id",),
    )
)  # fmt: skip
router.include_router(
    crud_router(
        model=AreaType, path="/area-types", entity="area_type",
        create_schema=sc.AreaTypeIn, update_schema=sc.AreaTypePatch, read_schema=sc.AreaTypeOut,
        view_perm=Perm.org_view, manage_perm=Perm.config_manage, order_by=("key",),
    )
)  # fmt: skip
router.include_router(
    crud_router(
        model=Department, path="/departments", entity="department",
        create_schema=sc.DepartmentIn, update_schema=sc.DepartmentPatch,
        read_schema=sc.DepartmentOut, view_perm=Perm.org_view, manage_perm=Perm.org_manage,
        order_by=("name",),
    )
)  # fmt: skip
router.include_router(
    crud_router(
        model=Area, path="/areas", entity="area",
        create_schema=sc.AreaIn, update_schema=sc.AreaPatch, read_schema=sc.AreaOut,
        view_perm=Perm.org_view, manage_perm=Perm.org_manage, order_by=("code",),
        filters=("floor_id", "department_id", "area_type_id"),
    )
)  # fmt: skip
router.include_router(
    crud_router(
        model=Branch, path="/branches", entity="branch",
        create_schema=sc.BranchIn, update_schema=sc.BranchPatch, read_schema=sc.BranchOut,
        view_perm=Perm.org_view, manage_perm=Perm.org_manage, order_by=("name",),
    )
)  # fmt: skip
router.include_router(
    crud_router(
        model=Desk, path="/desks", entity="desk",
        create_schema=sc.DeskIn, update_schema=sc.DeskPatch, read_schema=sc.DeskOut,
        view_perm=Perm.org_view, manage_perm=Perm.org_manage, order_by=("code",),
        filters=("branch_id", "department_id", "floor_id"),
    )
)  # fmt: skip
