"""Signed photo URLs for the "db" storage backend (free-tier prototype).

Same contract as S3 presigned URLs: anyone holding the link can read the object until it expires
(5 minutes); the HMAC covers the key and expiry, so keys can't be guessed or the expiry extended.
The hospital id in the key selects the tenant, so RLS still applies to the lookup.
"""

import uuid

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy import select

from app.core.db import tenant_session
from app.core.errors import not_found
from app.core.storage import verify_file_sig
from app.modules.tasks.models import StoredObject
from app.policy.deps import public

router = APIRouter(tags=["files"])


@router.get("/files/{key:path}", dependencies=[Depends(public())])
async def get_file(key: str, e: int = Query(...), s: str = Query(..., max_length=40)) -> Response:
    if not verify_file_sig(key, e, s):
        raise not_found("file")
    try:
        hospital_id = uuid.UUID(key.split("/")[1])
    except (IndexError, ValueError) as exc:
        raise not_found("file") from exc
    async with tenant_session(hospital_id) as db:
        obj = await db.scalar(select(StoredObject).where(StoredObject.key == key))
    if obj is None:
        raise not_found("file")
    return Response(
        content=obj.data,
        media_type=obj.content_type,
        headers={"Cache-Control": "private, max-age=300", "X-Content-Type-Options": "nosniff"},
    )
