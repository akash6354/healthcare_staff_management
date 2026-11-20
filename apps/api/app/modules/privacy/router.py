"""Data-principal rights tools for hospital admins (DPDP): export and erase one staff member."""

import uuid
from typing import Any

from fastapi import APIRouter, Depends

from app.audit.service import Actor
from app.modules.privacy import service as svc
from app.policy.deps import DB, Access, requires
from app.policy.permissions import Perm

router = APIRouter(prefix="/privacy", tags=["privacy"])


def _actor(access: Access) -> Actor:
    return Actor(access.principal.user_id, access.principal.primary_role)


@router.get("/users/{user_id}/export")
async def export_user(
    user_id: uuid.UUID, db: DB, access: Access = Depends(requires(Perm.privacy_manage))
) -> Any:
    return await svc.export_user(db, user_id, _actor(access))


@router.post("/users/{user_id}/erase", status_code=204)
async def erase_user(
    user_id: uuid.UUID, db: DB, access: Access = Depends(requires(Perm.privacy_manage))
) -> None:
    await svc.erase_user(db, user_id, _actor(access))
