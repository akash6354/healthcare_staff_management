"""Org schemas, including the versioned per-hospital settings document (decisions.md §G)."""

import uuid
from datetime import datetime
from typing import Literal

from pydantic import Field

from app.core.schemas import In, Out
from app.modules.org.models import AreaStatus, DepartmentKind, Module, RiskLevel

Code = Field(min_length=1, max_length=32, pattern=r"^[A-Za-z0-9][A-Za-z0-9_-]*$")
Name = Field(min_length=1, max_length=120)
I18nName = dict[Literal["en", "kn", "hi"], str]


# ---------- settings (configurable platform: every rule is a per-hospital setting) ----------


class SlaMinutes(In):
    response: int = Field(ge=1, le=10080)
    resolution: int = Field(ge=1, le=43200)


class HousekeepingSettings(In):
    require_start_scan: bool = True  # decision 14
    require_end_scan: bool = True
    photo_required: Literal["always", "high_risk", "never"] = "always"
    before_photo_area_types: list[str] = ["icu", "ot"]  # G12
    inspect_high_risk_pct: int = Field(100, ge=0, le=100)  # decision 15
    inspect_random_pct: int = Field(20, ge=0, le=100)
    failed_inspection_creates_reclean: bool = True  # decision 16
    failed_inspection_affects_score: bool = True
    inspection_pass_mark: int = Field(80, ge=0, le=100)  # G9
    verify_within_minutes: int = Field(60, ge=5, le=1440)  # G6
    sla_by_risk: dict[Literal["high", "medium", "low"], SlaMinutes] = {  # G7
        "high": SlaMinutes(response=30, resolution=60),
        "medium": SlaMinutes(response=60, resolution=120),
        "low": SlaMinutes(response=120, resolution=240),
    }


class MaintenanceSettings(In):
    sla_by_priority: dict[Literal["critical", "high", "normal"], SlaMinutes] = {  # decision 17
        "critical": SlaMinutes(response=30, resolution=240),
        "high": SlaMinutes(response=120, resolution=1440),
        "normal": SlaMinutes(response=480, resolution=4320),
    }
    business_hours_categories: list[str] = ["civil"]  # G8
    business_hours: tuple[str, str] = ("08:00", "20:00")
    business_days: list[int] = [0, 1, 2, 3, 4, 5]  # Mon-Sat


class EscalationLevel(In):
    level: int = Field(ge=1, le=6)
    role: Literal["supervisor", "dept_head", "ops_manager", "hospital_admin"]
    after_minutes: int = Field(ge=0, le=10080)


class EscalationSettings(In):
    at_risk_pct: int = Field(75, ge=10, le=99)
    chain: list[EscalationLevel] = [  # decision 19 + G13
        EscalationLevel(level=1, role="supervisor", after_minutes=0),
        EscalationLevel(level=2, role="dept_head", after_minutes=30),
        EscalationLevel(level=3, role="ops_manager", after_minutes=60),
    ]
    critical_chain_minutes: list[int] = [0, 15, 30]


class RetentionSettings(In):
    photos_months: int = Field(18, ge=1, le=120)  # decision 23
    audit_years: int = Field(3, ge=1, le=10)
    deactivated_staff_months: int = Field(12, ge=1, le=120)
    public_reporter_phone_days: int = Field(90, ge=1, le=365)  # G15


class LoginSettings(In):
    email_otp: bool = True  # decision 13
    shared_device_pin: bool = True
    shift_checkin_required: bool = False  # G18


class NotificationSettings(In):
    in_app: bool = True  # decision 20
    web_push: bool = True
    email: bool = True
    md_daily_summary_time: str = "08:00"  # G14


class HospitalSettingsV1(In):
    languages: list[Literal["en", "kn", "hi"]] = ["en", "kn", "hi"]  # decision 11
    default_language: Literal["en", "kn", "hi"] = "en"
    login: LoginSettings = LoginSettings()
    housekeeping: HousekeepingSettings = HousekeepingSettings()
    maintenance: MaintenanceSettings = MaintenanceSettings()
    escalation: EscalationSettings = EscalationSettings()
    notifications: NotificationSettings = NotificationSettings()
    retention: RetentionSettings = RetentionSettings()


class SettingsOut(Out):
    schema_version: int
    settings: HospitalSettingsV1
    updated_at: datetime


class ModuleOut(Out):
    module: Module
    enabled: bool


# ---------- hospital ----------


class HospitalOut(Out):
    id: uuid.UUID
    code: str
    name: str
    city: str
    timezone: str


class HospitalUpdate(In):
    name: str | None = Field(None, min_length=2, max_length=160)
    city: str | None = Field(None, min_length=2, max_length=80)


# ---------- structure ----------


class BuildingIn(In):
    name: str = Name
    code: str = Code
    sort: int = 0


class BuildingPatch(In):
    name: str | None = Field(None, min_length=1, max_length=120)
    code: str | None = Field(None, min_length=1, max_length=32)
    sort: int | None = None


class BuildingOut(Out):
    id: uuid.UUID
    name: str
    code: str
    sort: int
    archived_at: datetime | None


class FloorIn(In):
    building_id: uuid.UUID
    label: str = Field(min_length=1, max_length=16)
    level: int = Field(ge=-10, le=200)


class FloorPatch(In):
    label: str | None = Field(None, min_length=1, max_length=16)
    level: int | None = Field(None, ge=-10, le=200)


class FloorOut(Out):
    id: uuid.UUID
    building_id: uuid.UUID
    label: str
    level: int
    archived_at: datetime | None


class AreaTypeIn(In):
    key: str = Field(min_length=2, max_length=40, pattern=r"^[a-z][a-z0-9_]*$")
    name_i18n: I18nName
    default_risk: RiskLevel = RiskLevel.medium
    evidence_rules: dict[str, bool] = {}


class AreaTypePatch(In):
    name_i18n: I18nName | None = None
    default_risk: RiskLevel | None = None
    evidence_rules: dict[str, bool] | None = None


class AreaTypeOut(Out):
    id: uuid.UUID
    key: str
    name_i18n: dict[str, str]
    default_risk: RiskLevel
    evidence_rules: dict[str, bool]
    archived_at: datetime | None


class DepartmentIn(In):
    name: str = Name
    kind: DepartmentKind
    head_user_id: uuid.UUID | None = None


class DepartmentPatch(In):
    name: str | None = Field(None, min_length=1, max_length=120)
    kind: DepartmentKind | None = None
    head_user_id: uuid.UUID | None = None


class DepartmentOut(Out):
    id: uuid.UUID
    name: str
    kind: DepartmentKind
    head_user_id: uuid.UUID | None
    archived_at: datetime | None


class AreaIn(In):
    floor_id: uuid.UUID
    area_type_id: uuid.UUID
    department_id: uuid.UUID | None = None
    parent_area_id: uuid.UUID | None = None
    code: str = Code
    name: str = Name
    risk_level: RiskLevel
    grid_x: int | None = Field(None, ge=0, le=200)
    grid_y: int | None = Field(None, ge=0, le=200)
    grid_w: int = Field(1, ge=1, le=8)
    notes: str | None = Field(None, max_length=500)


class AreaPatch(In):
    area_type_id: uuid.UUID | None = None
    department_id: uuid.UUID | None = None
    code: str | None = Field(None, min_length=1, max_length=32)
    name: str | None = Field(None, min_length=1, max_length=120)
    risk_level: RiskLevel | None = None
    grid_x: int | None = Field(None, ge=0, le=200)
    grid_y: int | None = Field(None, ge=0, le=200)
    grid_w: int | None = Field(None, ge=1, le=8)
    notes: str | None = Field(None, max_length=500)


class AreaOut(Out):
    id: uuid.UUID
    floor_id: uuid.UUID
    area_type_id: uuid.UUID
    department_id: uuid.UUID | None
    parent_area_id: uuid.UUID | None
    code: str
    name: str
    risk_level: RiskLevel
    status: AreaStatus
    qr_token_version: int
    grid_x: int | None
    grid_y: int | None
    grid_w: int
    notes: str | None
    archived_at: datetime | None
