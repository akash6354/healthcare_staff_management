"""Desk-wise task engine services (product plan: Base #4, #8-#13).

All times are stored in UTC; "today" means the hospital's day in Asia/Kolkata.
"""

import uuid
from collections.abc import Sequence
from datetime import UTC, date, datetime, time, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy import and_, func, or_, select, text
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.audit.service import SYSTEM, Actor, record
from app.core.errors import AppError, forbidden, not_found
from app.core.ids import uuid7
from app.core.storage import ist_label, process_photo, put_object
from app.modules.org.models import Desk, HospitalSettings
from app.modules.org.schemas import HospitalSettingsV1
from app.modules.staff.models import Role, RosterEntry, ScopeType, User, UserRole, UserStatus
from app.modules.tasks.models import (
    FlagRule,
    Notification,
    ProofPhase,
    ScheduleKind,
    SlaState,
    Task,
    TaskFlag,
    TaskProof,
    TaskStatus,
    TaskTemplate,
)
from app.modules.tasks.state_machine import Action, set_sla, transition
from app.policy.deps import Access
from app.policy.permissions import Scope

IST = ZoneInfo("Asia/Kolkata")
OPEN_STATES = (TaskStatus.pending, TaskStatus.in_progress)


def actor_of(access: Access) -> Actor:
    return Actor(access.principal.user_id, access.principal.primary_role)


def today_ist(now: datetime | None = None) -> date:
    return (now or datetime.now(UTC)).astimezone(IST).date()


def day_bounds(day: date) -> tuple[datetime, datetime]:
    start = datetime.combine(day, time.min, tzinfo=IST).astimezone(UTC)
    return start, start + timedelta(days=1)


async def hospital_settings(db: AsyncSession, hospital_id: uuid.UUID) -> HospitalSettingsV1:
    row = await db.get(HospitalSettings, hospital_id)
    return HospitalSettingsV1.model_validate(row.settings if row else {})


# ---------- numbering & materialisation ----------


async def next_number(db: AsyncSession, hospital_id: uuid.UUID, name: str = "task") -> int:
    value = await db.scalar(
        text(
            """INSERT INTO counters (hospital_id, name, value) VALUES (:h, :n, 1)
               ON CONFLICT (hospital_id, name) DO UPDATE SET value = counters.value + 1
               RETURNING value"""
        ),
        {"h": hospital_id, "n": name},
    )
    return int(value or 0)


def occurrences(template: TaskTemplate, day: date) -> list[datetime]:
    if template.schedule_kind == ScheduleKind.one_time:
        return []
    if template.schedule_kind == ScheduleKind.weekly and day.weekday() not in template.weekdays:
        return []
    out = []
    for hhmm in template.times:
        h, m = (int(x) for x in hhmm.split(":"))
        out.append(datetime.combine(day, time(h, m), tzinfo=IST).astimezone(UTC))
    return out


async def materialise_day(db: AsyncSession, hospital_id: uuid.UUID, day: date) -> int:
    """Create the day's scheduled tasks. Idempotent: (template_id, scheduled_for) is unique."""
    templates = (
        await db.scalars(
            select(TaskTemplate).where(
                TaskTemplate.active.is_(True), TaskTemplate.archived_at.is_(None)
            )
        )
    ).all()
    if not templates:
        return 0
    start, end = day_bounds(day)
    existing = set(
        (
            await db.execute(
                select(Task.template_id, Task.scheduled_for).where(
                    Task.scheduled_for >= start, Task.scheduled_for < end
                )
            )
        ).all()
    )
    desks = {d.id: d for d in (await db.scalars(select(Desk))).all()}
    created = 0
    for t in templates:
        desk = desks.get(t.desk_id)
        if desk is None or desk.archived_at is not None:
            continue
        for when in occurrences(t, day):
            if (t.id, when) in existing:
                continue
            stmt = (
                insert(Task)
                .values(
                    id=uuid7(),
                    hospital_id=hospital_id,
                    number=await next_number(db, hospital_id),
                    desk_id=t.desk_id,
                    branch_id=desk.branch_id,
                    template_id=t.id,
                    scheduled_for=when,
                    title_i18n=t.title_i18n,
                    instructions_i18n=t.instructions_i18n,
                    checklist=t.checklist,
                    requires_before_photo=t.requires_before_photo,
                    requires_after_photo=t.requires_after_photo,
                    min_minutes=t.min_minutes,
                    status=TaskStatus.pending,
                    sla_state=SlaState.on_time,
                    due_at=when + timedelta(minutes=t.due_minutes),
                )  # fmt: skip
                .on_conflict_do_nothing(index_elements=["template_id", "scheduled_for"])
            )
            result = await db.execute(stmt)
            created += int(getattr(result, "rowcount", 0) or 0)
    return created


# ---------- desk scope ----------


async def my_desk_ids(db: AsyncSession, user_id: uuid.UUID, day: date) -> set[uuid.UUID]:
    rows = await db.scalars(
        select(RosterEntry.desk_id).where(
            RosterEntry.user_id == user_id,
            RosterEntry.work_date == day,
            RosterEntry.desk_id.is_not(None),
        )
    )
    return {d for d in rows if d}


async def desk_filter(db: AsyncSession, access: Access) -> Any:
    """SQL condition limiting tasks to the caller's scope."""
    if access.scope >= Scope.hospital:
        return True
    if access.scope >= Scope.department and access.department_ids:
        desk_ids = select(Desk.id).where(Desk.department_id.in_(access.department_ids))
        return Task.desk_id.in_(desk_ids)
    if access.scope >= Scope.area and access.area_ids:
        return Task.desk_id.in_(select(Desk.id).where(Desk.area_id.in_(access.area_ids)))
    mine = await my_desk_ids(db, access.principal.user_id, today_ist())
    return Task.desk_id.in_(mine) if mine else False


async def get_task_in_scope(db: AsyncSession, access: Access, task_id: uuid.UUID) -> Task:
    task = await db.scalar(
        select(Task).where(Task.id == task_id, await desk_filter(db, access)).with_for_update()
    )
    if task is None:
        raise not_found("task")
    return task


async def _require_on_desk(db: AsyncSession, access: Access, task: Task) -> None:
    """Workers act only on desks they are rostered to today; supervisors+ may act anywhere in scope."""
    if access.scope > Scope.self:
        return
    if task.desk_id not in await my_desk_ids(db, access.principal.user_id, today_ist()):
        raise AppError("NOT_ON_THIS_DESK", 403)


# ---------- worker actions ----------


async def start_task(db: AsyncSession, access: Access, task: Task) -> None:
    await _require_on_desk(db, access, task)
    await transition(db, task, Action.start, actor_of(access))


async def add_proof(
    db: AsyncSession,
    access: Access,
    task: Task,
    phase: ProofPhase,
    raw: bytes,
    client_captured_at: datetime | None,
) -> TaskProof:
    await _require_on_desk(db, access, task)
    if task.status != TaskStatus.in_progress:
        raise AppError("PROOF_ONLY_WHILE_IN_PROGRESS", 409)
    if phase == ProofPhase.after:
        has_before = await db.scalar(
            select(func.count()).where(
                TaskProof.task_id == task.id, TaskProof.phase == ProofPhase.before
            )
        )
        if task.requires_before_photo and not has_before:
            raise AppError("BEFORE_PHOTO_FIRST", 409)
    desk = await db.get(Desk, task.desk_id)
    user = await db.get(User, access.principal.user_id)
    now = datetime.now(UTC)
    label = (
        f"{desk.code if desk else ''}  {ist_label(now)}  Staff {user.employee_code if user else ''}"
    )
    photo = process_photo(raw, label)
    pid = uuid7()
    base = f"h/{task.hospital_id}/t/{task.id}/{pid}"
    await put_object(f"{base}.jpg", photo.jpeg, "image/jpeg")
    await put_object(f"{base}_t.jpg", photo.thumb, "image/jpeg")
    proof = TaskProof(
        id=pid, hospital_id=task.hospital_id, task_id=task.id, phase=phase,
        object_key=f"{base}.jpg", thumb_key=f"{base}_t.jpg", sha256=photo.sha256,
        source_sha256=photo.source_sha256, bytes=len(photo.jpeg), width=photo.width,
        height=photo.height, captured_by=access.principal.user_id,
        client_captured_at=client_captured_at,
    )  # fmt: skip
    db.add(proof)
    await db.flush()
    await record(
        db, hospital_id=task.hospital_id, actor=actor_of(access), entity_type="task_proof",
        entity_id=pid, task_id=task.id, action="task.proof_added",
        payload={"phase": phase.value, "bytes": len(photo.jpeg)},
    )  # fmt: skip
    return proof


async def submit_task(
    db: AsyncSession, access: Access, task: Task, checklist: dict[str, bool]
) -> list[TaskFlag]:
    await _require_on_desk(db, access, task)
    missing = [
        i["key"] for i in task.checklist if i.get("required", True) and not checklist.get(i["key"])
    ]
    if missing:
        raise AppError("CHECKLIST_INCOMPLETE", 422, missing=missing)
    phases = set(
        (await db.scalars(select(TaskProof.phase).where(TaskProof.task_id == task.id))).all()
    )
    if task.requires_before_photo and ProofPhase.before not in phases:
        raise AppError("BEFORE_PHOTO_REQUIRED", 422)
    if task.requires_after_photo and ProofPhase.after not in phases:
        raise AppError("AFTER_PHOTO_REQUIRED", 422)
    known = {i["key"] for i in task.checklist}
    task.checklist_result = {k: bool(v) for k, v in checklist.items() if k in known}
    await transition(db, task, Action.submit, actor_of(access))
    flags = await detect_fake_work(db, task)
    await _notify_reviewers(db, task, "task_submitted")
    return flags


# ---------- supervisor actions ----------


async def review_task(
    db: AsyncSession, access: Access, task: Task, approve: bool, note: str | None
) -> None:
    if task.submitted_by == access.principal.user_id:
        raise AppError("REVIEWER_IS_SUBMITTER", 403)
    if not approve and not (note and note.strip()):
        raise AppError("REJECT_REASON_REQUIRED", 422)
    task.review_note = note
    submitter = task.submitted_by
    await transition(
        db, task, Action.approve if approve else Action.reject, actor_of(access),
        payload={"note": bool(note)},
    )  # fmt: skip
    if not approve and submitter:
        await notify(db, task.hospital_id, [submitter], "task_rejected", task.id)


async def cancel_task(db: AsyncSession, access: Access, task: Task, reason: str) -> None:
    task.cancel_reason = reason
    await transition(db, task, Action.cancel, actor_of(access), payload={"reason_len": len(reason)})


# ---------- fake-work detector (rules only; humans decide) ----------


async def detect_fake_work(db: AsyncSession, task: Task) -> list[TaskFlag]:
    flags: list[TaskFlag] = []

    def add(rule: FlagRule, **details: Any) -> None:
        flags.append(
            TaskFlag(hospital_id=task.hospital_id, task_id=task.id, rule=rule, details=details)
        )

    if task.started_at and task.submitted_at and task.min_minutes:
        took = (task.submitted_at - task.started_at).total_seconds() / 60
        if took < task.min_minutes:
            add(FlagRule.too_fast, minutes=round(took, 1), expected=task.min_minutes)

    my_hashes = select(TaskProof.source_sha256).where(TaskProof.task_id == task.id)
    dup = await db.scalar(
        select(func.count()).where(
            TaskProof.source_sha256.in_(my_hashes), TaskProof.task_id != task.id
        )
    )
    if dup:
        add(FlagRule.duplicate_photo, matches=int(dup))

    if task.submitted_by and task.submitted_at:
        window = task.submitted_at - timedelta(minutes=3)
        recent = (
            await db.execute(
                select(Task.id, Desk.floor_id, Task.submitted_at)
                .join(Desk, Desk.id == Task.desk_id)
                .where(
                    Task.submitted_by == task.submitted_by,
                    Task.submitted_at >= window,
                    Task.id != task.id,
                )
            )
        ).all()
        if len(recent) >= 4:
            add(FlagRule.bulk_close, tasks_in_3_min=len(recent) + 1)
        desk = await db.get(Desk, task.desk_id)
        near = [r for r in recent if (task.submitted_at - r.submitted_at) <= timedelta(minutes=1)]
        if desk and desk.floor_id and any(r.floor_id and r.floor_id != desk.floor_id for r in near):
            add(FlagRule.far_apart, within_seconds=60)

    for f in flags:
        db.add(f)
    if flags:
        await db.flush()
        for f in flags:
            await record(
                db, hospital_id=task.hospital_id, actor=SYSTEM, entity_type="task_flag",
                entity_id=f.id, task_id=task.id, action="flag.raised", payload={"rule": f.rule.value},
            )  # fmt: skip
    return flags


# ---------- notifications & escalation ----------


async def notify(
    db: AsyncSession, hospital_id: uuid.UUID, user_ids: Sequence[uuid.UUID], kind: str,
    task_id: uuid.UUID | None = None, **params: Any,
) -> None:  # fmt: skip
    for uid in set(user_ids):
        db.add(
            Notification(
                hospital_id=hospital_id, user_id=uid, kind=kind, task_id=task_id, params=params
            )
        )
    await db.flush()


async def users_with_role_for_desk(
    db: AsyncSession, roles: Sequence[Role], desk: Desk
) -> list[uuid.UUID]:
    conds = [UserRole.scope_type == ScopeType.hospital]
    if desk.department_id:
        conds.append(
            and_(
                UserRole.scope_type == ScopeType.department, UserRole.scope_id == desk.department_id
            )
        )
    if desk.area_id:
        conds.append(and_(UserRole.scope_type == ScopeType.area, UserRole.scope_id == desk.area_id))
    rows = await db.scalars(
        select(UserRole.user_id)
        .join(User, User.id == UserRole.user_id)
        .where(UserRole.role.in_(roles), or_(*conds), User.status == UserStatus.active)
    )
    return list(set(rows))


async def _notify_reviewers(db: AsyncSession, task: Task, kind: str) -> None:
    desk = await db.get(Desk, task.desk_id)
    if desk:
        ids = await users_with_role_for_desk(db, [Role.supervisor], desk)
        await notify(db, task.hospital_id, ids, kind, task.id)


ROLE_BY_CHAIN = {
    "supervisor": Role.supervisor,
    "dept_head": Role.dept_head,
    "ops_manager": Role.ops_manager,
    "hospital_admin": Role.hospital_admin,
    "management_viewer": Role.management_viewer,
}


async def sla_sweep(
    db: AsyncSession, hospital_id: uuid.UUID, now: datetime | None = None
) -> dict[str, int]:
    """Overdue → escalate along the configured chain (default supervisor → MD); past days → missed.
    Safe to run repeatedly and concurrently (row locks, SKIP LOCKED)."""
    now = now or datetime.now(UTC)
    settings = await hospital_settings(db, hospital_id)
    chain = sorted(settings.escalation.chain, key=lambda c: c.level)
    stats = {"overdue": 0, "escalated": 0, "missed": 0}
    day_start, _ = day_bounds(today_ist(now))

    missed = (
        await db.scalars(
            select(Task)
            .where(
                Task.status.in_(OPEN_STATES),
                Task.due_at < day_start,
                Task.sla_state != SlaState.missed,
            )
            .with_for_update(skip_locked=True)
        )
    ).all()
    for t in missed:
        await set_sla(db, t, SlaState.missed, SYSTEM)
        stats["missed"] += 1

    due = (
        await db.scalars(
            select(Task)
            .where(
                Task.status.in_(OPEN_STATES), Task.due_at <= now, Task.sla_state != SlaState.missed
            )
            .with_for_update(skip_locked=True)
        )
    ).all()
    for t in due:
        late_minutes = (now - t.due_at).total_seconds() / 60
        if t.sla_state == SlaState.on_time:
            await set_sla(db, t, SlaState.overdue, SYSTEM)
            stats["overdue"] += 1
        target = [
            c for c in chain if c.after_minutes <= late_minutes and c.level > t.escalation_level
        ]
        if not target:
            continue
        level = target[-1]
        desk = await db.get(Desk, t.desk_id)
        role = ROLE_BY_CHAIN.get(level.role)
        if desk and role:
            ids = await users_with_role_for_desk(db, [role], desk)
            await notify(db, hospital_id, ids, "task_escalated", t.id, level=level.level)
        await set_sla(db, t, SlaState.overdue, SYSTEM, level=level.level)
        stats["escalated"] += 1
    return stats


# ---------- dashboard ----------


async def dashboard(db: AsyncSession, access: Access, day: date) -> dict[str, Any]:
    start, end = day_bounds(day)
    scope = await desk_filter(db, access)
    in_day = and_(Task.due_at >= start, Task.due_at < end, scope)
    rows = (
        await db.execute(
            select(Task.status, Task.sla_state, func.count())
            .where(in_day)
            .group_by(Task.status, Task.sla_state)
        )
    ).all()
    counts = {"total": 0, "done": 0, "awaiting_approval": 0, "in_progress": 0, "pending": 0,
              "overdue": 0, "missed": 0, "late": 0, "cancelled": 0}  # fmt: skip
    for status, sla, n in rows:
        counts["total"] += n
        if status == TaskStatus.approved:
            counts["done"] += n
        elif status == TaskStatus.submitted:
            counts["awaiting_approval"] += n
        elif status == TaskStatus.cancelled:
            counts["cancelled"] += n
        elif sla == SlaState.missed:
            counts["missed"] += n
        elif sla == SlaState.overdue:
            counts["overdue"] += n
        elif status == TaskStatus.in_progress:
            counts["in_progress"] += n
        else:
            counts["pending"] += n
        if sla == SlaState.late:
            counts["late"] += n
    by_desk = (
        await db.execute(
            select(
                Desk.id, Desk.name, Desk.code,
                func.count(Task.id),
                func.count(Task.id).filter(Task.status == TaskStatus.approved),
                func.count(Task.id).filter(Task.sla_state.in_([SlaState.overdue, SlaState.missed])),
            )
            .join(Task, Task.desk_id == Desk.id)
            .where(in_day)
            .group_by(Desk.id, Desk.name, Desk.code)
            .order_by(Desk.code)
        )
    ).all()  # fmt: skip
    open_flags = await db.scalar(
        select(func.count()).select_from(TaskFlag).join(Task, Task.id == TaskFlag.task_id)
        .where(TaskFlag.status == "open", scope)
    )  # fmt: skip
    return {
        "day": day.isoformat(),
        "counts": counts,
        "open_flags": int(open_flags or 0),
        "desks": [
            {"id": str(r[0]), "name": r[1], "code": r[2], "total": r[3], "done": r[4], "late": r[5]}
            for r in by_desk
        ],
    }


def ensure_reviewer(access: Access) -> None:
    if access.scope <= Scope.self:
        raise forbidden()
