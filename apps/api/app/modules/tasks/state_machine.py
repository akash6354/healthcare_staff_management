"""The only code allowed to change tasks.status (CLAUDE.md rule 4; a DB trigger enforces it).

Desk-wise pilot lifecycle (docs/state-machine.md §5):

    pending ──start──▶ in_progress ──submit──▶ submitted ──approve──▶ approved
       ▲                                           │
       └──────────────── reject (rework) ──────────┘
    pending / in_progress ──cancel──▶ cancelled

Every transition writes an audit event in the same transaction.
"""

import enum
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.audit.service import Actor, record
from app.core.errors import AppError
from app.modules.tasks.models import SlaState, Task, TaskStatus


class Action(enum.StrEnum):
    start = "start"
    submit = "submit"
    approve = "approve"
    reject = "reject"
    cancel = "cancel"


TRANSITIONS: dict[tuple[TaskStatus, Action], TaskStatus] = {
    (TaskStatus.pending, Action.start): TaskStatus.in_progress,
    (TaskStatus.in_progress, Action.submit): TaskStatus.submitted,
    (TaskStatus.submitted, Action.approve): TaskStatus.approved,
    (TaskStatus.submitted, Action.reject): TaskStatus.pending,
    (TaskStatus.pending, Action.cancel): TaskStatus.cancelled,
    (TaskStatus.in_progress, Action.cancel): TaskStatus.cancelled,
}


@dataclass(frozen=True)
class Transition:
    from_state: TaskStatus
    to_state: TaskStatus


def next_state(current: TaskStatus, action: Action) -> TaskStatus:
    target = TRANSITIONS.get((current, action))
    if target is None:
        raise AppError(
            "TASK_INVALID_TRANSITION", 409, from_state=current.value, action=action.value
        )
    return target


async def transition(
    session: AsyncSession,
    task: Task,
    action: Action,
    actor: Actor,
    payload: dict[str, Any] | None = None,
) -> Transition:
    """Apply one action. Callers check guards (photos, checklist, scope) before calling."""
    before = task.status
    after = next_state(before, action)
    now = datetime.now(UTC)
    await session.execute(text("SELECT set_config('app.task_sm', 'on', true)"))
    task.status = after
    if action == Action.start:
        task.started_at, task.started_by = now, actor.user_id
    elif action == Action.submit:
        task.submitted_at, task.submitted_by = now, actor.user_id
        task.sla_state = SlaState.met if now <= task.due_at else SlaState.late
    elif action in (Action.approve, Action.reject):
        task.reviewed_at, task.reviewed_by = now, actor.user_id
        if action == Action.reject:
            task.rework_count += 1
            task.started_at = task.started_by = task.submitted_at = task.submitted_by = None
            task.checklist_result = None  # rework needs a fresh checklist and fresh photos
            task.sla_state = SlaState.overdue if now > task.due_at else SlaState.on_time
    await session.flush()
    await session.execute(text("SELECT set_config('app.task_sm', 'off', true)"))
    await record(
        session,
        hospital_id=task.hospital_id,
        actor=actor,
        entity_type="task",
        entity_id=task.id,
        task_id=task.id,
        action=f"task.{action.value}",
        from_state=before.value,
        to_state=after.value,
        payload=payload or {},
    )
    return Transition(before, after)


async def set_sla(
    session: AsyncSession, task: Task, sla: SlaState, actor: Actor, level: int | None = None
) -> None:
    """SLA track changes (overdue, missed, escalation level). Status is untouched."""
    before = task.sla_state
    task.sla_state = sla
    if level is not None:
        task.escalation_level = level
    await session.flush()
    await record(
        session,
        hospital_id=task.hospital_id,
        actor=actor,
        entity_type="task",
        entity_id=task.id,
        task_id=task.id,
        action="task.sla",
        from_state=before.value,
        to_state=sla.value,
        payload={"level": task.escalation_level},
    )
