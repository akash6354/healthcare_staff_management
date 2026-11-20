"""Hospital structure: hospitals, settings, modules, buildings, floors, area types, areas, departments.

No patient data: beds are areas identified by a bed code only.
"""

import enum
import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, IdMixin, TenantMixin, TimestampMixin, str_enum, tenant_fk


class HospitalStatus(enum.StrEnum):
    active = "active"
    suspended = "suspended"


class RiskLevel(enum.StrEnum):
    high = "high"
    medium = "medium"
    low = "low"


class AreaStatus(enum.StrEnum):
    active = "active"
    out_of_service = "out_of_service"


class DepartmentKind(enum.StrEnum):
    clinical_unit = "clinical_unit"
    support = "support"
    admin = "admin"


class Module(enum.StrEnum):
    housekeeping = "housekeeping"
    maintenance = "maintenance"
    requests = "requests"
    public_qr = "public_qr"
    vendor_portal = "vendor_portal"


class Hospital(IdMixin, TimestampMixin, Base):
    """The tenant itself. RLS policy: id = app.hospital_id."""

    __tablename__ = "hospitals"
    code: Mapped[str] = mapped_column(String(24), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    city: Mapped[str] = mapped_column(String(80), nullable=False)
    timezone: Mapped[str] = mapped_column(String(40), nullable=False, default="Asia/Kolkata")
    status: Mapped[HospitalStatus] = mapped_column(
        str_enum(HospitalStatus, "hospital_status"), nullable=False, default=HospitalStatus.active
    )


class HospitalSettings(TenantMixin, Base):
    __tablename__ = "hospital_settings"
    __table_args__ = ()  # type: ignore[assignment]  # PK is hospital_id; no separate id
    hospital_id: Mapped[uuid.UUID] = mapped_column(  # type: ignore[assignment]
        Uuid, ForeignKey("hospitals.id", ondelete="RESTRICT"), primary_key=True
    )
    schema_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    settings: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    updated_by: Mapped[uuid.UUID | None] = mapped_column(Uuid, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class HospitalModule(TenantMixin, Base):
    __tablename__ = "hospital_modules"
    __table_args__ = ()  # type: ignore[assignment]
    hospital_id: Mapped[uuid.UUID] = mapped_column(  # type: ignore[assignment]
        Uuid, ForeignKey("hospitals.id", ondelete="RESTRICT"), primary_key=True
    )
    module: Mapped[Module] = mapped_column(str_enum(Module, "module"), primary_key=True)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    changed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class Building(IdMixin, TenantMixin, TimestampMixin, Base):
    __tablename__ = "buildings"
    __tenant_args__ = (UniqueConstraint("hospital_id", "code"),)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    code: Mapped[str] = mapped_column(String(24), nullable=False)
    sort: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Floor(IdMixin, TenantMixin, TimestampMixin, Base):
    __tablename__ = "floors"
    __tenant_args__ = (
        tenant_fk("building_id", "buildings"),
        UniqueConstraint("hospital_id", "building_id", "label"),
    )
    building_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False, index=True)
    label: Mapped[str] = mapped_column(String(16), nullable=False)  # "B1", "G", "1"
    level: Mapped[int] = mapped_column(Integer, nullable=False)  # ordering: B1=-1, G=0, 1=1
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class AreaType(IdMixin, TenantMixin, TimestampMixin, Base):
    __tablename__ = "area_types"
    __tenant_args__ = (UniqueConstraint("hospital_id", "key"),)
    key: Mapped[str] = mapped_column(String(40), nullable=False)
    name_i18n: Mapped[dict[str, str]] = mapped_column(JSONB, nullable=False)
    default_risk: Mapped[RiskLevel] = mapped_column(
        str_enum(RiskLevel, "risk_level"), nullable=False, default=RiskLevel.medium
    )
    evidence_rules: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Department(IdMixin, TenantMixin, TimestampMixin, Base):
    __tablename__ = "departments"
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    kind: Mapped[DepartmentKind] = mapped_column(
        str_enum(DepartmentKind, "department_kind"), nullable=False
    )
    head_user_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, nullable=True)
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Area(IdMixin, TenantMixin, TimestampMixin, Base):
    __tablename__ = "areas"
    __tenant_args__ = (
        tenant_fk("floor_id", "floors"),
        tenant_fk("area_type_id", "area_types"),
        tenant_fk("department_id", "departments"),
        tenant_fk("parent_area_id", "areas"),
        UniqueConstraint("hospital_id", "code"),
    )
    floor_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False, index=True)
    area_type_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    department_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, nullable=True)
    parent_area_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, nullable=True)
    code: Mapped[str] = mapped_column(String(32), nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    risk_level: Mapped[RiskLevel] = mapped_column(str_enum(RiskLevel, "risk_level"), nullable=False)
    status: Mapped[AreaStatus] = mapped_column(
        str_enum(AreaStatus, "area_status"), nullable=False, default=AreaStatus.active
    )
    qr_token_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    grid_x: Mapped[int | None] = mapped_column(Integer)
    grid_y: Mapped[int | None] = mapped_column(Integer)
    grid_w: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    notes: Mapped[str | None] = mapped_column(Text)
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
