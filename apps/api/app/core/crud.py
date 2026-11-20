"""Generic tenant CRUD router for configuration entities (buildings, floors, area types, ...).

Every write is audited. Deletes archive the row (soft delete) so history and references survive.
Tenant isolation comes from RLS: a row from another hospital is simply not found (404).
"""

import uuid
from typing import Any

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel
from sqlalchemy import func, select

from app.audit.service import Actor, record
from app.core.errors import AppError, not_found
from app.db.base import Base
from app.policy.deps import DB, Access, requires
from app.policy.permissions import Perm


def _actor(access: Access) -> Actor:
    return Actor(access.principal.user_id, access.principal.primary_role)


def crud_router(
    *,
    model: type[Base],
    path: str,
    entity: str,
    create_schema: type[BaseModel],
    update_schema: type[BaseModel],
    read_schema: type[BaseModel],
    view_perm: Perm,
    manage_perm: Perm,
    order_by: tuple[str, ...] = ("created_at",),
    filters: tuple[str, ...] = (),
) -> APIRouter:
    router = APIRouter(prefix=path, tags=[entity])
    archivable = hasattr(model, "archived_at")
    m: Any = model

    @router.get("", response_model=list[read_schema])  # type: ignore[valid-type]
    async def list_items(
        request: Request,
        db: DB,
        access: Access = Depends(requires(view_perm)),
        include_archived: bool = False,
        limit: int = Query(500, ge=1, le=1000),
    ) -> Any:
        stmt = select(m)
        for name in filters:  # e.g. ?building_id=... ; only whitelisted uuid columns
            raw = request.query_params.get(name)
            if raw:
                try:
                    stmt = stmt.where(getattr(m, name) == uuid.UUID(raw))
                except ValueError as exc:
                    raise AppError("INVALID_FILTER", 422, field=name) from exc
        if archivable and not include_archived:
            stmt = stmt.where(m.archived_at.is_(None))
        stmt = stmt.order_by(*(getattr(m, c) for c in order_by)).limit(limit)
        return (await db.scalars(stmt)).all()

    @router.get("/{item_id}", response_model=read_schema)
    async def get_item(
        item_id: uuid.UUID, db: DB, access: Access = Depends(requires(view_perm))
    ) -> Any:
        item = await db.get(m, item_id)
        if item is None:
            raise not_found(entity)
        return item

    @router.post("", response_model=read_schema, status_code=201)
    async def create_item(
        body: create_schema,  # type: ignore[valid-type]
        db: DB,
        access: Access = Depends(requires(manage_perm)),
    ) -> Any:
        item = m(hospital_id=access.principal.hospital_id, **body.model_dump())  # type: ignore[attr-defined]
        db.add(item)
        await db.flush()
        await record(
            db, hospital_id=access.principal.hospital_id, actor=_actor(access),
            entity_type=entity, entity_id=item.id, action=f"{entity}.created",
        )  # fmt: skip
        await db.refresh(item)
        return item

    @router.patch("/{item_id}", response_model=read_schema)
    async def update_item(
        item_id: uuid.UUID,
        body: update_schema,  # type: ignore[valid-type]
        db: DB,
        access: Access = Depends(requires(manage_perm)),
    ) -> Any:
        item = await db.get(m, item_id, with_for_update=True)
        if item is None:
            raise not_found(entity)
        changes = body.model_dump(exclude_unset=True)  # type: ignore[attr-defined]
        for key, value in changes.items():
            setattr(item, key, value)
        await db.flush()
        await record(
            db, hospital_id=access.principal.hospital_id, actor=_actor(access),
            entity_type=entity, entity_id=item.id, action=f"{entity}.updated",
            payload={"fields": sorted(changes)},
        )  # fmt: skip
        await db.refresh(item)
        return item

    if archivable:

        @router.delete("/{item_id}", status_code=204)
        async def archive_item(
            item_id: uuid.UUID, db: DB, access: Access = Depends(requires(manage_perm))
        ) -> None:
            item = await db.get(m, item_id, with_for_update=True)
            if item is None or item.archived_at is not None:
                raise not_found(entity)
            item.archived_at = func.now()
            await db.flush()
            await record(
                db, hospital_id=access.principal.hospital_id, actor=_actor(access),
                entity_type=entity, entity_id=item.id, action=f"{entity}.archived",
            )  # fmt: skip

    return router
