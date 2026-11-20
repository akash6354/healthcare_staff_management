import uuid
from datetime import date, datetime, time
from typing import Literal

from pydantic import EmailStr, Field, field_validator

from app.core.schemas import In, Out
from app.modules.staff.models import (
    CheckinMethod,
    EmploymentType,
    Language,
    Role,
    ScopeType,
    UserStatus,
)

PHONE_PATTERN = r"^\+?[0-9]{10,13}$"


class RoleGrantIn(In):
    role: Role
    scope_type: ScopeType = ScopeType.hospital
    scope_id: uuid.UUID | None = None

    @field_validator("scope_id")
    @classmethod
    def _scope(cls, v: uuid.UUID | None, info):  # type: ignore[no-untyped-def]
        st = info.data.get("scope_type")
        if (st == ScopeType.hospital) != (v is None):
            raise ValueError("scope_id is required unless scope_type is hospital")
        return v


class RoleGrantOut(Out):
    role: Role
    scope_type: ScopeType
    scope_id: uuid.UUID | None


class UserIn(In):
    employee_code: str = Field(min_length=1, max_length=32, pattern=r"^[A-Za-z0-9_-]+$")
    display_name: str = Field(min_length=2, max_length=120)
    email: EmailStr | None = None
    phone: str | None = Field(None, pattern=PHONE_PATTERN)
    preferred_language: Language = Language.en
    employment_type: EmploymentType
    agency_id: uuid.UUID | None = None
    vendor_id: uuid.UUID | None = None
    department_id: uuid.UUID | None = None
    roles: list[RoleGrantIn] = Field(min_length=1, max_length=10)


class UserPatch(In):
    display_name: str | None = Field(None, min_length=2, max_length=120)
    email: EmailStr | None = None
    phone: str | None = Field(None, pattern=PHONE_PATTERN)
    preferred_language: Language | None = None
    department_id: uuid.UUID | None = None


class UserOut(Out):
    id: uuid.UUID
    employee_code: str
    display_name: str
    email: str | None
    phone: str | None = None  # masked unless the viewer has staff.manage
    preferred_language: Language
    employment_type: EmploymentType
    agency_id: uuid.UUID | None
    vendor_id: uuid.UUID | None
    department_id: uuid.UUID | None
    status: UserStatus
    roles: list[RoleGrantOut] = []


class SetPinIn(In):
    pin: str = Field(min_length=4, max_length=6)


class SetPasswordIn(In):
    password: str = Field(min_length=10, max_length=128)


class AgencyIn(In):
    name: str = Field(min_length=2, max_length=160)
    contact_email: EmailStr | None = None


class AgencyPatch(In):
    name: str | None = Field(None, min_length=2, max_length=160)
    contact_email: EmailStr | None = None


class AgencyOut(Out):
    id: uuid.UUID
    name: str
    contact_email: str | None
    archived_at: datetime | None


VendorCategory = Literal["electrical", "plumbing", "hvac", "lift", "civil", "biomedical", "housekeeping", "security", "other"]  # fmt: skip


class VendorIn(In):
    name: str = Field(min_length=2, max_length=160)
    categories: list[VendorCategory] = []
    contract_ref: str | None = Field(None, max_length=80)
    contact_email: EmailStr | None = None


class VendorPatch(In):
    name: str | None = Field(None, min_length=2, max_length=160)
    categories: list[VendorCategory] | None = None
    contract_ref: str | None = Field(None, max_length=80)
    contact_email: EmailStr | None = None


class VendorOut(Out):
    id: uuid.UUID
    name: str
    categories: list[str]
    contract_ref: str | None
    contact_email: str | None
    archived_at: datetime | None


class ShiftIn(In):
    name: str = Field(min_length=1, max_length=60)
    starts_at: time
    ends_at: time
    crosses_midnight: bool = False


class ShiftPatch(In):
    name: str | None = Field(None, min_length=1, max_length=60)
    starts_at: time | None = None
    ends_at: time | None = None
    crosses_midnight: bool | None = None


class ShiftOut(Out):
    id: uuid.UUID
    name: str
    starts_at: time
    ends_at: time
    crosses_midnight: bool
    archived_at: datetime | None


class RosterIn(In):
    user_id: uuid.UUID
    shift_id: uuid.UUID
    work_date: date
    department_id: uuid.UUID | None = None
    zone_area_ids: list[uuid.UUID] = Field(default_factory=list, max_length=200)


class RosterOut(Out):
    id: uuid.UUID
    user_id: uuid.UUID
    shift_id: uuid.UUID
    work_date: date
    department_id: uuid.UUID | None
    zone_area_ids: list[uuid.UUID]


class CheckinIn(In):
    kind: Literal["check_in", "check_out"]
    method: CheckinMethod = CheckinMethod.app
    roster_entry_id: uuid.UUID | None = None


class CheckinOut(Out):
    id: uuid.UUID
    user_id: uuid.UUID
    kind: str
    method: CheckinMethod
    server_ts: datetime


class DeviceIn(In):
    label: str = Field(min_length=2, max_length=80)


class DeviceOut(Out):
    id: uuid.UUID
    label: str
    last_seen_at: datetime | None
    revoked_at: datetime | None
    created_at: datetime


class DeviceRegistered(DeviceOut):
    device_key: str  # shown once; store it on the device
