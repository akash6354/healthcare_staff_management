import uuid
from datetime import date, datetime
from typing import Annotated, Any, Literal

from pydantic import Field, StringConstraints, field_validator

from app.core.schemas import In, Out
from app.modules.tasks.models import (
    FlagRule,
    FlagStatus,
    ProofPhase,
    ScheduleKind,
    SlaState,
    TaskStatus,
)

Short = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]
Long = Annotated[str, StringConstraints(strip_whitespace=True, max_length=1000)]
I18n = dict[Literal["en", "kn", "hi"], Short]
I18nLong = dict[Literal["en", "kn", "hi"], Long]


class ChecklistItem(In):
    key: str = Field(min_length=1, max_length=40, pattern=r"^[a-z0-9_]+$")
    label_i18n: I18n
    required: bool = True
    icon: str | None = Field(None, max_length=40)  # pictogram id for low-literacy screens


class TemplateIn(In):
    desk_id: uuid.UUID
    title_i18n: I18n
    instructions_i18n: I18nLong = {}
    checklist: list[ChecklistItem] = Field(default_factory=list, max_length=30)
    schedule_kind: ScheduleKind
    times: list[str] = Field(default_factory=list, max_length=48)
    weekdays: list[int] = Field(default_factory=list, max_length=7)
    due_minutes: int = Field(60, ge=5, le=1440)
    min_minutes: int = Field(0, ge=0, le=600)
    requires_before_photo: bool = True
    requires_after_photo: bool = True
    active: bool = True

    @field_validator("times")
    @classmethod
    def _times(cls, v: list[str]) -> list[str]:
        for t in v:
            h, _, m = t.partition(":")
            if not (
                h.isdigit()
                and m.isdigit()
                and 0 <= int(h) < 24
                and 0 <= int(m) < 60
                and len(t) == 5
            ):
                raise ValueError("times must be HH:MM")
        return sorted(set(v))

    @field_validator("weekdays")
    @classmethod
    def _weekdays(cls, v: list[int]) -> list[int]:
        if any(d < 0 or d > 6 for d in v):
            raise ValueError("weekdays are 0 (Mon) to 6 (Sun)")
        return sorted(set(v))


class TemplatePatch(In):
    title_i18n: I18n | None = None
    instructions_i18n: I18nLong | None = None
    checklist: list[ChecklistItem] | None = None
    times: list[str] | None = None
    weekdays: list[int] | None = None
    due_minutes: int | None = Field(None, ge=5, le=1440)
    min_minutes: int | None = Field(None, ge=0, le=600)
    requires_before_photo: bool | None = None
    requires_after_photo: bool | None = None
    active: bool | None = None

    _times = field_validator("times")(TemplateIn._times.__func__)  # type: ignore[attr-defined]
    _weekdays = field_validator("weekdays")(TemplateIn._weekdays.__func__)  # type: ignore[attr-defined]


class TemplateOut(Out):
    id: uuid.UUID
    desk_id: uuid.UUID
    title_i18n: dict[str, str]
    instructions_i18n: dict[str, str]
    checklist: list[dict[str, Any]]
    schedule_kind: ScheduleKind
    times: list[str]
    weekdays: list[int]
    due_minutes: int
    min_minutes: int
    requires_before_photo: bool
    requires_after_photo: bool
    active: bool
    archived_at: datetime | None


class OneTimeTaskIn(In):
    desk_id: uuid.UUID
    title_i18n: I18n
    instructions_i18n: I18nLong = {}
    checklist: list[ChecklistItem] = Field(default_factory=list, max_length=30)
    due_at: datetime
    requires_before_photo: bool = True
    requires_after_photo: bool = True


class ProofOut(Out):
    id: uuid.UUID
    phase: ProofPhase
    server_received_at: datetime
    url: str | None = None
    thumb_url: str | None = None
    width: int
    height: int


class FlagOut(Out):
    id: uuid.UUID
    task_id: uuid.UUID
    rule: FlagRule
    details: dict[str, Any]
    status: FlagStatus
    created_at: datetime


class TaskOut(Out):
    id: uuid.UUID
    number: int
    desk_id: uuid.UUID
    branch_id: uuid.UUID
    title_i18n: dict[str, str]
    instructions_i18n: dict[str, str]
    checklist: list[dict[str, Any]]
    checklist_result: dict[str, bool] | None
    requires_before_photo: bool
    requires_after_photo: bool
    status: TaskStatus
    sla_state: SlaState
    escalation_level: int
    scheduled_for: datetime | None
    due_at: datetime
    started_at: datetime | None
    submitted_at: datetime | None
    submitted_by: uuid.UUID | None
    reviewed_at: datetime | None
    review_note: str | None
    rework_count: int


class TaskDetail(TaskOut):
    proofs: list[ProofOut] = []
    flags: list[FlagOut] = []
    desk_name: str | None = None
    submitted_by_name: str | None = None


class SubmitIn(In):
    checklist: dict[str, bool] = Field(default_factory=dict)


class ReviewIn(In):
    note: str | None = Field(None, max_length=500)


class CancelIn(In):
    reason: str = Field(min_length=3, max_length=200)


class FlagReviewIn(In):
    status: Literal["dismissed", "confirmed"]


class SubmitResult(Out):
    task: TaskOut
    flags: list[FlagOut]


class DayQuery(In):
    day: date | None = None


class NotificationOut(Out):
    id: uuid.UUID
    kind: str
    task_id: uuid.UUID | None
    params: dict[str, Any]
    read_at: datetime | None
    created_at: datetime
