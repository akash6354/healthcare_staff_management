"""Staff, roles, agencies, vendors, shifts, roster, check-ins and shared devices.

Personal data is limited to: display name, employee code, work email, optional phone (encrypted).
See docs/compliance/data-inventory.md.
"""

import enum
import uuid
from datetime import date, datetime, time

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    Index,
    LargeBinary,
    String,
    Time,
    UniqueConstraint,
    Uuid,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import ARRAY, CITEXT
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, IdMixin, TenantMixin, TimestampMixin, str_enum, tenant_fk


class Role(enum.StrEnum):
    hospital_admin = "hospital_admin"
    management_viewer = "management_viewer"
    ops_manager = "ops_manager"
    dept_head = "dept_head"
    supervisor = "supervisor"
    worker = "worker"
    requester = "requester"
    vendor_user = "vendor_user"
    quality_coordinator = "quality_coordinator"


class ScopeType(enum.StrEnum):
    hospital = "hospital"
    department = "department"
    area = "area"
    vendor = "vendor"


class EmploymentType(enum.StrEnum):
    employee = "employee"
    agency = "agency"
    vendor = "vendor"


class UserStatus(enum.StrEnum):
    active = "active"
    deactivated = "deactivated"
    erased = "erased"


class Language(enum.StrEnum):
    en = "en"
    kn = "kn"
    hi = "hi"


class CheckinMethod(enum.StrEnum):
    qr = "qr"
    pin = "pin"
    app = "app"


class Agency(IdMixin, TenantMixin, TimestampMixin, Base):
    __tablename__ = "agencies"
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    contact_email: Mapped[str | None] = mapped_column(CITEXT)
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Vendor(IdMixin, TenantMixin, TimestampMixin, Base):
    __tablename__ = "vendors"
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    categories: Mapped[list[str]] = mapped_column(ARRAY(String(40)), nullable=False, default=list)
    contract_ref: Mapped[str | None] = mapped_column(String(80))
    contact_email: Mapped[str | None] = mapped_column(CITEXT)
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class User(IdMixin, TenantMixin, TimestampMixin, Base):
    __tablename__ = "users"
    __tenant_args__ = (
        tenant_fk("agency_id", "agencies"),
        tenant_fk("vendor_id", "vendors"),
        tenant_fk("department_id", "departments"),
        UniqueConstraint("hospital_id", "employee_code"),
        Index(
            "uq_users_hospital_email",
            "hospital_id",
            "email",
            unique=True,
            postgresql_where=text("email IS NOT NULL"),
        ),
        Index("ix_users_hospital_phone_hash", "hospital_id", "phone_hash"),
        CheckConstraint(
            "(employment_type <> 'agency') OR agency_id IS NOT NULL", name="agency_has_agency_id"
        ),
        CheckConstraint(
            "(employment_type <> 'vendor') OR vendor_id IS NOT NULL", name="vendor_has_vendor_id"
        ),
    )
    employee_code: Mapped[str] = mapped_column(String(32), nullable=False)
    display_name: Mapped[str] = mapped_column(String(120), nullable=False)
    email: Mapped[str | None] = mapped_column(CITEXT)
    phone_enc: Mapped[bytes | None] = mapped_column(LargeBinary)
    phone_hash: Mapped[bytes | None] = mapped_column(LargeBinary)
    preferred_language: Mapped[Language] = mapped_column(
        str_enum(Language, "language"), nullable=False, default=Language.en
    )
    employment_type: Mapped[EmploymentType] = mapped_column(
        str_enum(EmploymentType, "employment_type"), nullable=False
    )
    agency_id: Mapped[uuid.UUID | None] = mapped_column(Uuid)
    vendor_id: Mapped[uuid.UUID | None] = mapped_column(Uuid)
    department_id: Mapped[uuid.UUID | None] = mapped_column(Uuid)
    status: Mapped[UserStatus] = mapped_column(
        str_enum(UserStatus, "user_status"), nullable=False, default=UserStatus.active
    )
    deactivated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    erased_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class UserRole(IdMixin, TenantMixin, Base):
    __tablename__ = "user_roles"
    __tenant_args__ = (
        tenant_fk("user_id", "users"),
        UniqueConstraint("hospital_id", "user_id", "role", "scope_type", "scope_id"),
        CheckConstraint(
            "(scope_type = 'hospital') = (scope_id IS NULL)", name="scope_id_matches_type"
        ),
    )
    user_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False, index=True)
    role: Mapped[Role] = mapped_column(str_enum(Role, "role"), nullable=False)
    scope_type: Mapped[ScopeType] = mapped_column(str_enum(ScopeType, "scope_type"), nullable=False)
    scope_id: Mapped[uuid.UUID | None] = mapped_column(Uuid)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class Shift(IdMixin, TenantMixin, TimestampMixin, Base):
    __tablename__ = "shifts"
    name: Mapped[str] = mapped_column(String(60), nullable=False)
    starts_at: Mapped[time] = mapped_column(Time, nullable=False)
    ends_at: Mapped[time] = mapped_column(Time, nullable=False)
    crosses_midnight: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class RosterEntry(IdMixin, TenantMixin, TimestampMixin, Base):
    __tablename__ = "roster_entries"
    __tenant_args__ = (
        tenant_fk("user_id", "users"),
        tenant_fk("shift_id", "shifts"),
        tenant_fk("department_id", "departments"),
        UniqueConstraint("hospital_id", "user_id", "shift_id", "work_date"),
    )
    user_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False, index=True)
    shift_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    work_date: Mapped[date] = mapped_column(Date, nullable=False)
    department_id: Mapped[uuid.UUID | None] = mapped_column(Uuid)
    zone_area_ids: Mapped[list[uuid.UUID]] = mapped_column(
        ARRAY(Uuid), nullable=False, default=list
    )


class ShiftCheckin(IdMixin, TenantMixin, Base):
    """Append-only (Labour Codes: tamper-evident attendance). Check-out is a second row."""

    __tablename__ = "shift_checkins"
    __tenant_args__ = (
        tenant_fk("user_id", "users"),
        tenant_fk("roster_entry_id", "roster_entries"),
        tenant_fk("area_id", "areas"),
    )
    user_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False, index=True)
    roster_entry_id: Mapped[uuid.UUID | None] = mapped_column(Uuid)
    kind: Mapped[str] = mapped_column(String(12), nullable=False)  # check_in | check_out
    method: Mapped[CheckinMethod] = mapped_column(
        str_enum(CheckinMethod, "checkin_method"), nullable=False
    )
    area_id: Mapped[uuid.UUID | None] = mapped_column(Uuid)
    server_ts: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.clock_timestamp(), nullable=False
    )


class Device(IdMixin, TenantMixin, TimestampMixin, Base):
    """Shared device registered by an admin; staff sign in on it with a PIN."""

    __tablename__ = "devices"
    label: Mapped[str] = mapped_column(String(80), nullable=False)
    device_key_hash: Mapped[bytes] = mapped_column(LargeBinary, nullable=False, unique=True)
    registered_by: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
