"""Entrance QR attendance (Base #3) and the staff data notice (Base #18, DPDP).

No biometrics and no GPS: a check-in records who scanned which branch's entrance code, at server time.
"""

import uuid
from datetime import UTC, datetime
from typing import Any, Literal

from fastapi import APIRouter, Depends
from pydantic import Field
from sqlalchemy import select

from app.audit.service import Actor, record
from app.core import qr
from app.core.errors import AppError, not_found
from app.core.schemas import In, Out
from app.modules.org.models import Branch
from app.modules.staff.models import CheckinMethod, ShiftCheckin, User
from app.modules.tasks.models import NoticeAcknowledgement, PrivacyNotice
from app.modules.tasks.service import day_bounds, today_ist
from app.policy.deps import DB, Access, requires
from app.policy.permissions import Perm, Scope

router = APIRouter(tags=["attendance"])
ENTRANCE = "entrance"


def _actor(access: Access) -> Actor:
    return Actor(access.principal.user_id, access.principal.primary_role)


class EntranceQrOut(Out):
    branch_id: uuid.UUID
    version: int
    token: str
    svg: str


class ScanIn(In):
    token: str = Field(min_length=10, max_length=400)
    kind: Literal["check_in", "check_out"]


class CheckinOut(Out):
    id: uuid.UUID
    user_id: uuid.UUID
    kind: str
    server_ts: datetime
    branch_id: uuid.UUID | None
    display_name: str | None = None


@router.get("/branches/{branch_id}/entrance-qr", response_model=EntranceQrOut)
async def entrance_qr(
    branch_id: uuid.UUID, db: DB, access: Access = Depends(requires(Perm.org_manage))
) -> Any:
    branch = await db.get(Branch, branch_id)
    if branch is None:
        raise not_found("branch")
    token = qr.sign(ENTRANCE, branch.hospital_id, branch.id, branch.entrance_qr_version)
    return EntranceQrOut(
        branch_id=branch.id, version=branch.entrance_qr_version, token=token, svg=qr.svg(token)
    )


@router.post("/branches/{branch_id}/entrance-qr/rotate", response_model=EntranceQrOut)
async def rotate_entrance_qr(
    branch_id: uuid.UUID, db: DB, access: Access = Depends(requires(Perm.org_manage))
) -> Any:
    branch = await db.get(Branch, branch_id, with_for_update=True)
    if branch is None:
        raise not_found("branch")
    branch.entrance_qr_version += 1
    await db.flush()
    await record(
        db, hospital_id=branch.hospital_id, actor=_actor(access), entity_type="branch",
        entity_id=branch.id, action="branch.entrance_qr_rotated",
        payload={"version": branch.entrance_qr_version},
    )  # fmt: skip
    token = qr.sign(ENTRANCE, branch.hospital_id, branch.id, branch.entrance_qr_version)
    return EntranceQrOut(
        branch_id=branch.id, version=branch.entrance_qr_version, token=token, svg=qr.svg(token)
    )


@router.post("/attendance/scan", response_model=CheckinOut, status_code=201)
async def scan(body: ScanIn, db: DB, access: Access = Depends(requires(Perm.self_service))) -> Any:
    claim = qr.verify(body.token, ENTRANCE)
    if claim is None or claim.hospital_id != access.principal.hospital_id:
        raise AppError("QR_INVALID", 422)
    branch = await db.get(Branch, claim.object_id)
    if (
        branch is None
        or branch.archived_at is not None
        or branch.entrance_qr_version != claim.version
    ):
        raise AppError("QR_NO_LONGER_ACTIVE", 422)
    row = ShiftCheckin(
        hospital_id=branch.hospital_id, user_id=access.principal.user_id, branch_id=branch.id,
        kind=body.kind, method=CheckinMethod.qr,
    )  # fmt: skip
    db.add(row)
    await db.flush()
    await db.refresh(row)
    return row


@router.get("/attendance/today", response_model=list[CheckinOut])
async def attendance_today(db: DB, access: Access = Depends(requires(Perm.staff_view))) -> Any:
    start, end = day_bounds(today_ist())
    stmt = (
        select(ShiftCheckin, User.display_name)
        .join(User, User.id == ShiftCheckin.user_id)
        .where(ShiftCheckin.server_ts >= start, ShiftCheckin.server_ts < end)
    )
    if access.scope < Scope.hospital:
        stmt = stmt.where(User.department_id.in_(access.department_ids))
    rows = (await db.execute(stmt.order_by(ShiftCheckin.server_ts.desc()))).all()
    return [
        CheckinOut.model_validate(c).model_copy(update={"display_name": name}) for c, name in rows
    ]


@router.get("/me/attendance", response_model=list[CheckinOut])
async def my_attendance(db: DB, access: Access = Depends(requires(Perm.self_service))) -> Any:
    start, end = day_bounds(today_ist())
    stmt = select(ShiftCheckin).where(
        ShiftCheckin.user_id == access.principal.user_id,
        ShiftCheckin.server_ts >= start, ShiftCheckin.server_ts < end,
    )  # fmt: skip
    return (await db.scalars(stmt.order_by(ShiftCheckin.server_ts))).all()


# ---------- staff data notice ----------


class NoticeOut(Out):
    id: uuid.UUID
    version: int
    body_i18n: dict[str, str]
    published_at: datetime
    acknowledged: bool = False


class NoticeIn(In):
    body_i18n: dict[Literal["en", "kn", "hi"], str]


@router.get("/notice/current", response_model=NoticeOut | None)
async def current_notice(
    db: DB, access: Access = Depends(requires(Perm.self_service, allow_mfa_pending=True))
) -> Any:
    notice = await db.scalar(select(PrivacyNotice).order_by(PrivacyNotice.version.desc()).limit(1))
    if notice is None:
        return None
    ack = await db.scalar(
        select(NoticeAcknowledgement.id).where(
            NoticeAcknowledgement.user_id == access.principal.user_id,
            NoticeAcknowledgement.notice_id == notice.id,
        )
    )
    return NoticeOut.model_validate(notice).model_copy(update={"acknowledged": ack is not None})


@router.post("/notice/{notice_id}/ack", status_code=204)
async def acknowledge(
    notice_id: uuid.UUID,
    db: DB,
    access: Access = Depends(requires(Perm.self_service, allow_mfa_pending=True)),
) -> None:
    notice = await db.get(PrivacyNotice, notice_id)
    if notice is None:
        raise not_found("notice")
    exists = await db.scalar(
        select(NoticeAcknowledgement.id).where(
            NoticeAcknowledgement.user_id == access.principal.user_id,
            NoticeAcknowledgement.notice_id == notice.id,
        )
    )
    if exists:
        return
    db.add(
        NoticeAcknowledgement(
            hospital_id=notice.hospital_id, user_id=access.principal.user_id, notice_id=notice.id
        )
    )
    await record(
        db, hospital_id=notice.hospital_id, actor=_actor(access), entity_type="privacy_notice",
        entity_id=notice.id, action="notice.acknowledged", payload={"version": notice.version},
    )  # fmt: skip


@router.post("/notice", response_model=NoticeOut, status_code=201)
async def publish_notice(
    body: NoticeIn, db: DB, access: Access = Depends(requires(Perm.privacy_manage))
) -> Any:
    if set(body.body_i18n) != {"en", "kn", "hi"}:
        raise AppError("NOTICE_NEEDS_ALL_LANGUAGES", 422)
    latest = await db.scalar(
        select(PrivacyNotice.version).order_by(PrivacyNotice.version.desc()).limit(1)
    )
    notice = PrivacyNotice(
        hospital_id=access.principal.hospital_id, version=(latest or 0) + 1, body_i18n=dict(body.body_i18n),
        published_at=datetime.now(UTC),
    )  # fmt: skip
    db.add(notice)
    await db.flush()
    await record(
        db, hospital_id=notice.hospital_id, actor=_actor(access), entity_type="privacy_notice",
        entity_id=notice.id, action="notice.published", payload={"version": notice.version},
    )  # fmt: skip
    return notice
