"""Declarative base, naming conventions and tenant helpers shared by all models."""

import enum
import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    DateTime,
    Enum,
    ForeignKeyConstraint,
    MetaData,
    UniqueConstraint,
    Uuid,
    func,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, declared_attr, mapped_column

from app.core.ids import uuid7

NAMING = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_N_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_N_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING)


def str_enum(e: type[enum.StrEnum], name: str) -> Enum:
    """Portable enum stored as text with a CHECK constraint (easy, reversible migrations)."""
    return Enum(
        e,
        name=name,
        native_enum=False,
        create_constraint=True,
        length=40,
        values_callable=lambda x: [m.value for m in x],
    )


class IdMixin:
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid7)


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class TenantMixin:
    """hospital_id on every tenant table + UNIQUE(hospital_id, id) as a composite-FK target.

    RLS is enabled for these tables by `enable_tenant_rls()` in migrations; a test fails if any
    table with a hospital_id column lacks it.
    """

    @declared_attr
    def hospital_id(cls) -> Mapped[uuid.UUID]:
        return mapped_column(Uuid, nullable=False, index=True)

    @declared_attr.directive
    def __table_args__(cls) -> Any:
        return _tenant_args(cls)


def _tenant_args(cls: Any) -> tuple[Any, ...]:
    args: list[Any] = [
        ForeignKeyConstraint(["hospital_id"], ["hospitals.id"], ondelete="RESTRICT"),
    ]
    if "id" in getattr(cls, "__annotations__", {}) or hasattr(cls, "id"):
        args.append(UniqueConstraint("hospital_id", "id"))
    extra = getattr(cls, "__tenant_args__", ())
    return (*args, *extra)


def tenant_fk(column: str, target_table: str, ondelete: str = "RESTRICT") -> ForeignKeyConstraint:
    """Composite FK (hospital_id, column) -> target(hospital_id, id): a row can never point
    at another hospital's row, even if application code has a bug."""
    return ForeignKeyConstraint(
        ["hospital_id", column],
        [f"{target_table}.hospital_id", f"{target_table}.id"],
        ondelete=ondelete,
    )
