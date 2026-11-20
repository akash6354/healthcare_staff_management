"""Desk-wise task engine for the pilot (decision H3): templates → tasks on desks → photo proof →
supervisor approval. Status changes only via app.modules.tasks.state_machine (CLAUDE.md rule 4)."""

import enum
import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    Index,
    Integer,
    LargeBinary,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    func,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, IdMixin, TenantMixin, TimestampMixin, str_enum, tenant_fk


class TaskStatus(enum.StrEnum):
    pending = "pending"
    in_progress = "in_progress"
    submitted = "submitted"
    approved = "approved"
    rejected = "rejected"  # sent back for rework; returns to pending via the state machine
    cancelled = "cancelled"


class SlaState(enum.StrEnum):
    on_time = "on_time"
    overdue = "overdue"  # due time passed, not yet submitted
    missed = "missed"  # shift/day ended without submission
    met = "met"
    late = "late"  # submitted after the due time


class ScheduleKind(enum.StrEnum):
    daily = "daily"
    weekly = "weekly"
    one_time = "one_time"


class ProofPhase(enum.StrEnum):
    before = "before"
    after = "after"


class FlagRule(enum.StrEnum):
    too_fast = "too_fast"
    duplicate_photo = "duplicate_photo"
    bulk_close = "bulk_close"
    far_apart = "far_apart"


class FlagStatus(enum.StrEnum):
    open = "open"
    dismissed = "dismissed"
    confirmed = "confirmed"


class Counter(TenantMixin, Base):
    """Per-hospital human-readable sequences (task numbers)."""

    __tablename__ = "counters"
    __table_args__ = (  # type: ignore[assignment]
        UniqueConstraint("hospital_id", "name"),
    )
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(40), nullable=False)
    value: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)


class TaskTemplate(IdMixin, TenantMixin, TimestampMixin, Base):
    __tablename__ = "task_templates"
    __tenant_args__ = (tenant_fk("desk_id", "desks"),)
    desk_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False, index=True)
    title_i18n: Mapped[dict[str, str]] = mapped_column(JSONB, nullable=False)
    instructions_i18n: Mapped[dict[str, str]] = mapped_column(JSONB, nullable=False, default=dict)
    checklist: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, nullable=False, default=list)
    schedule_kind: Mapped[ScheduleKind] = mapped_column(
        str_enum(ScheduleKind, "schedule_kind"), nullable=False
    )
    times: Mapped[list[str]] = mapped_column(ARRAY(String(5)), nullable=False, default=list)
    weekdays: Mapped[list[int]] = mapped_column(ARRAY(Integer), nullable=False, default=list)
    due_minutes: Mapped[int] = mapped_column(Integer, nullable=False, default=60)
    min_minutes: Mapped[int] = mapped_column(Integer, nullable=False, default=0)  # fake-work rule
    requires_before_photo: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    requires_after_photo: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Task(IdMixin, TenantMixin, TimestampMixin, Base):
    __tablename__ = "tasks"
    __tenant_args__ = (
        tenant_fk("desk_id", "desks"),
        tenant_fk("branch_id", "branches"),
        tenant_fk("template_id", "task_templates"),
        UniqueConstraint("hospital_id", "number"),
        UniqueConstraint("template_id", "scheduled_for"),  # idempotent materialisation
        Index("ix_tasks_desk_status_due", "hospital_id", "desk_id", "status", "due_at"),
        Index("ix_tasks_branch_due", "hospital_id", "branch_id", "due_at"),
        Index("ix_tasks_status_due", "hospital_id", "status", "due_at"),
    )
    number: Mapped[int] = mapped_column(BigInteger, nullable=False)
    desk_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    branch_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    template_id: Mapped[uuid.UUID | None] = mapped_column(Uuid)
    scheduled_for: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    title_i18n: Mapped[dict[str, str]] = mapped_column(JSONB, nullable=False)
    instructions_i18n: Mapped[dict[str, str]] = mapped_column(JSONB, nullable=False, default=dict)
    checklist: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, nullable=False, default=list)
    checklist_result: Mapped[dict[str, bool] | None] = mapped_column(JSONB)
    requires_before_photo: Mapped[bool] = mapped_column(Boolean, nullable=False)
    requires_after_photo: Mapped[bool] = mapped_column(Boolean, nullable=False)
    min_minutes: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    status: Mapped[TaskStatus] = mapped_column(
        str_enum(TaskStatus, "task_status"), nullable=False, default=TaskStatus.pending
    )
    sla_state: Mapped[SlaState] = mapped_column(
        str_enum(SlaState, "sla_state"), nullable=False, default=SlaState.on_time
    )
    escalation_level: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    due_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    started_by: Mapped[uuid.UUID | None] = mapped_column(Uuid)
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    submitted_by: Mapped[uuid.UUID | None] = mapped_column(Uuid)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    reviewed_by: Mapped[uuid.UUID | None] = mapped_column(Uuid)
    review_note: Mapped[str | None] = mapped_column(String(500))
    rework_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    cancel_reason: Mapped[str | None] = mapped_column(String(200))
    created_by: Mapped[uuid.UUID | None] = mapped_column(Uuid)


class TaskProof(IdMixin, TenantMixin, Base):
    """Before/after photo. Immutable (append-only grants + trigger); purge is a separate job."""

    __tablename__ = "task_proofs"
    __tenant_args__ = (
        tenant_fk("task_id", "tasks"),
        Index("ix_task_proofs_task", "hospital_id", "task_id"),
        Index("ix_task_proofs_sha", "hospital_id", "sha256"),
    )
    task_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    phase: Mapped[ProofPhase] = mapped_column(str_enum(ProofPhase, "proof_phase"), nullable=False)
    object_key: Mapped[str] = mapped_column(String(200), nullable=False)
    thumb_key: Mapped[str] = mapped_column(String(200), nullable=False)
    sha256: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    source_sha256: Mapped[bytes] = mapped_column(
        LargeBinary, nullable=False
    )  # duplicate-photo rule
    bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    width: Mapped[int] = mapped_column(Integer, nullable=False)
    height: Mapped[int] = mapped_column(Integer, nullable=False)
    captured_by: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    server_received_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.clock_timestamp(), nullable=False
    )
    client_captured_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class TaskFlag(IdMixin, TenantMixin, TimestampMixin, Base):
    """Fake-work detector output (decision H12). Always reviewed by a human; never auto-penalised."""

    __tablename__ = "task_flags"
    __tenant_args__ = (
        tenant_fk("task_id", "tasks"),
        UniqueConstraint("hospital_id", "task_id", "rule"),
    )
    task_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False, index=True)
    rule: Mapped[FlagRule] = mapped_column(str_enum(FlagRule, "flag_rule"), nullable=False)
    details: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    status: Mapped[FlagStatus] = mapped_column(
        str_enum(FlagStatus, "flag_status"), nullable=False, default=FlagStatus.open
    )
    reviewed_by: Mapped[uuid.UUID | None] = mapped_column(Uuid)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Notification(IdMixin, TenantMixin, Base):
    __tablename__ = "notifications"
    __tenant_args__ = (
        tenant_fk("user_id", "users"),
        Index("ix_notifications_user", "hospital_id", "user_id", "read_at", "created_at"),
    )
    user_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    kind: Mapped[str] = mapped_column(String(40), nullable=False)  # i18n key suffix
    task_id: Mapped[uuid.UUID | None] = mapped_column(Uuid)
    params: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.clock_timestamp(), nullable=False
    )


class PrivacyNotice(IdMixin, TenantMixin, Base):
    """Versioned staff data notice (DPDP). Shown at first login and after each new version."""

    __tablename__ = "privacy_notices"
    __tenant_args__ = (UniqueConstraint("hospital_id", "version"),)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    body_i18n: Mapped[dict[str, str]] = mapped_column(JSONB, nullable=False)
    published_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.clock_timestamp(), nullable=False
    )


class NoticeAcknowledgement(IdMixin, TenantMixin, Base):
    __tablename__ = "notice_acknowledgements"
    __tenant_args__ = (
        tenant_fk("user_id", "users"),
        tenant_fk("notice_id", "privacy_notices"),
        UniqueConstraint("hospital_id", "user_id", "notice_id"),
    )
    user_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    notice_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    server_ts: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.clock_timestamp(), nullable=False
    )


__all__ = [
    "Counter",
    "FlagRule",
    "FlagStatus",
    "NoticeAcknowledgement",
    "Notification",
    "PrivacyNotice",
    "ProofPhase",
    "ScheduleKind",
    "SlaState",
    "Task",
    "TaskFlag",
    "TaskProof",
    "TaskStatus",
    "TaskTemplate",
    "Text",
]  # fmt: skip


class ProofPurge(IdMixin, TenantMixin, Base):
    """Retention (decision H8): the full photo was deleted; the thumbnail and record stay.

    Append-only, so task_proofs itself stays immutable."""

    __tablename__ = "proof_purges"
    __tenant_args__ = (
        tenant_fk("proof_id", "task_proofs"),
        UniqueConstraint("hospital_id", "proof_id"),
    )
    proof_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    purged_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.clock_timestamp(), nullable=False
    )
