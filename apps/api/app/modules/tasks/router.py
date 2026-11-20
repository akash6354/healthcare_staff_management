"""Task routes: templates, desk tasks, photo proof, approval, flags, dashboard, notifications."""

import uuid
from datetime import UTC, date, datetime, timedelta
from typing import Any

from fastapi import APIRouter, Depends, File, Form, Query, UploadFile
from sqlalchemy import select, update

from app.audit.models import AuditEvent
from app.audit.service import record
from app.core.crud import crud_router
from app.core.errors import AppError, not_found
from app.core.storage import MAX_UPLOAD_BYTES, signed_url
from app.modules.org.models import Desk
from app.modules.staff.models import User
from app.modules.tasks import schemas as sc
from app.modules.tasks import service as svc
from app.modules.tasks.models import (
    FlagStatus,
    Notification,
    ProofPhase,
    ProofPurge,
    Task,
    TaskFlag,
    TaskProof,
    TaskStatus,
    TaskTemplate,
)
from app.policy.deps import DB, Access, requires
from app.policy.permissions import Perm

router = APIRouter(tags=["tasks"])

router.include_router(
    crud_router(
        model=TaskTemplate, path="/task-templates", entity="task_template",
        create_schema=sc.TemplateIn, update_schema=sc.TemplatePatch, read_schema=sc.TemplateOut,
        view_perm=Perm.task_view, manage_perm=Perm.config_manage, order_by=("created_at",),
        filters=("desk_id",),
    )
)  # fmt: skip


async def _detail(db: DB, task: Task) -> sc.TaskDetail:
    out = sc.TaskDetail.model_validate(task)
    proofs = (
        await db.scalars(
            select(TaskProof)
            .where(TaskProof.task_id == task.id)
            .order_by(TaskProof.server_received_at)
        )
    ).all()
    purged = set(
        (
            await db.scalars(
                select(ProofPurge.proof_id).where(ProofPurge.proof_id.in_([p.id for p in proofs]))
            )
        ).all()
    )
    out.proofs = [
        sc.ProofOut.model_validate(p).model_copy(
            update={
                "url": None if p.id in purged else signed_url(p.object_key),
                "thumb_url": signed_url(p.thumb_key),
            }
        )
        for p in proofs
    ]
    out.flags = [
        sc.FlagOut.model_validate(f)
        for f in (await db.scalars(select(TaskFlag).where(TaskFlag.task_id == task.id))).all()
    ]
    desk = await db.get(Desk, task.desk_id)
    out.desk_name = desk.name if desk else None
    if task.submitted_by:
        u = await db.get(User, task.submitted_by)
        out.submitted_by_name = u.display_name if u else None
    return out


@router.get("/tasks", response_model=list[sc.TaskOut])
async def list_tasks(
    db: DB,
    access: Access = Depends(requires(Perm.task_view)),
    day: date | None = None,
    desk_id: uuid.UUID | None = None,
    status: TaskStatus | None = None,
    limit: int = Query(300, ge=1, le=1000),
) -> Any:
    day = day or svc.today_ist()
    await svc.materialise_day(db, access.principal.hospital_id, day)
    start, end = svc.day_bounds(day)
    stmt = select(Task).where(
        Task.due_at >= start, Task.due_at < end, await svc.desk_filter(db, access)
    )
    if desk_id:
        stmt = stmt.where(Task.desk_id == desk_id)
    if status:
        stmt = stmt.where(Task.status == status)
    return (await db.scalars(stmt.order_by(Task.due_at).limit(limit))).all()


@router.get("/me/tasks", response_model=list[sc.TaskOut])
async def my_tasks(db: DB, access: Access = Depends(requires(Perm.task_view))) -> Any:
    """The staff home screen: today's tasks on the desks I'm rostered to (oldest due first)."""
    day = svc.today_ist()
    await svc.materialise_day(db, access.principal.hospital_id, day)
    desks = await svc.my_desk_ids(db, access.principal.user_id, day)
    if not desks:
        return []
    start, end = svc.day_bounds(day)
    stmt = select(Task).where(
        Task.desk_id.in_(desks),
        # everything due today, plus open work due in the next 18 h (night shifts cross midnight)
        ((Task.due_at >= start) & (Task.due_at < end))
        | (Task.status.in_(svc.OPEN_STATES) & (Task.due_at < datetime.now(UTC) + timedelta(hours=18))),
    ).order_by(Task.due_at)  # fmt: skip
    return (await db.scalars(stmt)).all()


@router.get("/me/desks")
async def my_desks(db: DB, access: Access = Depends(requires(Perm.task_view))) -> Any:
    """Desks I'm rostered to today (shown in the staff app header)."""
    ids = await svc.my_desk_ids(db, access.principal.user_id, svc.today_ist())
    if not ids:
        return []
    desks = (await db.scalars(select(Desk).where(Desk.id.in_(ids)).order_by(Desk.code))).all()
    return [{"id": str(d.id), "name": d.name, "code": d.code} for d in desks]


@router.post("/tasks", response_model=sc.TaskOut, status_code=201)
async def create_one_time(
    body: sc.OneTimeTaskIn, db: DB, access: Access = Depends(requires(Perm.task_create))
) -> Any:
    svc.ensure_reviewer(access)
    desk = await db.get(Desk, body.desk_id)
    if desk is None or not svc.desk_in_scope(access, desk):
        raise not_found("desk")
    task = Task(
        hospital_id=access.principal.hospital_id, number=await svc.next_number(db, access.principal.hospital_id),
        desk_id=desk.id, branch_id=desk.branch_id, title_i18n=body.title_i18n,
        instructions_i18n=body.instructions_i18n, checklist=[c.model_dump() for c in body.checklist],
        requires_before_photo=body.requires_before_photo, requires_after_photo=body.requires_after_photo,
        due_at=body.due_at, created_by=access.principal.user_id,
    )  # fmt: skip
    db.add(task)
    await db.flush()
    await record(
        db, hospital_id=task.hospital_id, actor=svc.actor_of(access), entity_type="task",
        entity_id=task.id, task_id=task.id, action="task.created", to_state="pending",
    )  # fmt: skip
    await db.refresh(task)
    return task


@router.get("/tasks/{task_id}", response_model=sc.TaskDetail)
async def get_task(
    task_id: uuid.UUID, db: DB, access: Access = Depends(requires(Perm.task_view))
) -> Any:
    return await _detail(db, await svc.get_task_in_scope(db, access, task_id))


@router.get("/tasks/{task_id}/timeline")
async def task_timeline(
    task_id: uuid.UUID, db: DB, access: Access = Depends(requires(Perm.task_view))
) -> Any:
    task = await svc.get_task_in_scope(db, access, task_id)
    events = (
        await db.scalars(
            select(AuditEvent).where(AuditEvent.task_id == task.id).order_by(AuditEvent.seq)
        )
    ).all()
    names = {
        u.id: u.display_name
        for u in (
            await db.scalars(
                select(User).where(User.id.in_({e.actor_id for e in events if e.actor_id}))
            )
        ).all()
    }
    return [
        {"seq": e.seq, "action": e.action, "from": e.from_state, "to": e.to_state, "at": e.server_ts,
         "actor": names.get(e.actor_id) if e.actor_id else "System", "role": e.actor_role}
        for e in events
    ]  # fmt: skip


@router.post("/tasks/{task_id}/start", response_model=sc.TaskOut)
async def start(
    task_id: uuid.UUID, db: DB, access: Access = Depends(requires(Perm.task_view))
) -> Any:
    task = await svc.get_task_in_scope(db, access, task_id)
    await svc.start_task(db, access, task)
    return task


@router.post("/tasks/{task_id}/proofs", response_model=sc.ProofOut, status_code=201)
async def upload_proof(
    task_id: uuid.UUID,
    db: DB,
    phase: ProofPhase = Form(...),
    photo: UploadFile = File(...),
    client_captured_at: datetime | None = Form(None),
    access: Access = Depends(requires(Perm.task_view)),
) -> Any:
    task = await svc.get_task_in_scope(db, access, task_id)
    raw = await photo.read(MAX_UPLOAD_BYTES + 1)
    proof = await svc.add_proof(db, access, task, phase, raw, client_captured_at)
    return sc.ProofOut.model_validate(proof).model_copy(
        update={"thumb_url": signed_url(proof.thumb_key)}
    )


@router.post("/tasks/{task_id}/submit", response_model=sc.SubmitResult)
async def submit(
    task_id: uuid.UUID,
    body: sc.SubmitIn,
    db: DB,
    access: Access = Depends(requires(Perm.task_view)),
) -> Any:
    task = await svc.get_task_in_scope(db, access, task_id)
    flags = await svc.submit_task(db, access, task, body.checklist)
    return sc.SubmitResult(
        task=sc.TaskOut.model_validate(task), flags=[sc.FlagOut.model_validate(f) for f in flags]
    )


@router.post("/tasks/{task_id}/approve", response_model=sc.TaskOut)
async def approve(
    task_id: uuid.UUID,
    body: sc.ReviewIn,
    db: DB,
    access: Access = Depends(requires(Perm.task_verify)),
) -> Any:
    task = await svc.get_task_in_scope(db, access, task_id)
    await svc.review_task(db, access, task, True, body.note)
    return task


@router.post("/tasks/{task_id}/reject", response_model=sc.TaskOut)
async def reject(
    task_id: uuid.UUID,
    body: sc.ReviewIn,
    db: DB,
    access: Access = Depends(requires(Perm.task_verify)),
) -> Any:
    task = await svc.get_task_in_scope(db, access, task_id)
    await svc.review_task(db, access, task, False, body.note)
    return task


@router.post("/tasks/{task_id}/cancel", response_model=sc.TaskOut)
async def cancel(
    task_id: uuid.UUID,
    body: sc.CancelIn,
    db: DB,
    access: Access = Depends(requires(Perm.task_cancel)),
) -> Any:
    task = await svc.get_task_in_scope(db, access, task_id)
    await svc.cancel_task(db, access, task, body.reason)
    return task


@router.get("/flags", response_model=list[sc.FlagOut])
async def list_flags(
    db: DB,
    access: Access = Depends(requires(Perm.task_verify)),
    status: FlagStatus = FlagStatus.open,
) -> Any:
    scope = await svc.desk_filter(db, access)
    stmt = (
        select(TaskFlag)
        .join(Task, Task.id == TaskFlag.task_id)
        .where(TaskFlag.status == status, scope)
    )
    return (await db.scalars(stmt.order_by(TaskFlag.created_at.desc()).limit(200))).all()


@router.post("/flags/{flag_id}/review", response_model=sc.FlagOut)
async def review_flag(
    flag_id: uuid.UUID,
    body: sc.FlagReviewIn,
    db: DB,
    access: Access = Depends(requires(Perm.task_verify)),
) -> Any:
    flag = await db.get(TaskFlag, flag_id, with_for_update=True)
    if flag is None:
        raise not_found("flag")
    await svc.get_task_in_scope(db, access, flag.task_id)  # scope check
    if flag.status != FlagStatus.open:
        raise AppError("FLAG_ALREADY_REVIEWED", 409)
    flag.status = FlagStatus(body.status)
    flag.reviewed_by, flag.reviewed_at = access.principal.user_id, datetime.now(UTC)
    await db.flush()
    await record(
        db, hospital_id=flag.hospital_id, actor=svc.actor_of(access), entity_type="task_flag",
        entity_id=flag.id, task_id=flag.task_id, action=f"flag.{body.status}",
    )  # fmt: skip
    return flag


@router.get("/dashboard/today")
async def dashboard_today(
    db: DB, access: Access = Depends(requires(Perm.board_view)), day: date | None = None
) -> Any:
    day = day or svc.today_ist()
    await svc.materialise_day(db, access.principal.hospital_id, day)
    await svc.sla_sweep(db, access.principal.hospital_id)
    return await svc.dashboard(db, access, day)


@router.get("/notifications", response_model=list[sc.NotificationOut])
async def my_notifications(db: DB, access: Access = Depends(requires(Perm.self_service))) -> Any:
    stmt = select(Notification).where(Notification.user_id == access.principal.user_id)
    return (await db.scalars(stmt.order_by(Notification.created_at.desc()).limit(50))).all()


@router.post("/notifications/read-all", status_code=204)
async def read_all(db: DB, access: Access = Depends(requires(Perm.self_service))) -> None:
    await db.execute(
        update(Notification)
        .where(Notification.user_id == access.principal.user_id, Notification.read_at.is_(None))
        .values(read_at=datetime.now(UTC))
    )
