"""Append-only audit events with a per-hospital SHA-256 hash chain.

oglos_app has no UPDATE/DELETE grant on this table, and a trigger rejects both anyway.
Payloads hold ids and reason codes only, never names (they survive staff erasure).
"""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import BigInteger, DateTime, Index, LargeBinary, String, UniqueConstraint, Uuid
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, IdMixin, TenantMixin


class AuditEvent(IdMixin, TenantMixin, Base):
    __tablename__ = "audit_events"
    __tenant_args__ = (
        UniqueConstraint("hospital_id", "seq"),
        Index("ix_audit_events_task", "hospital_id", "task_id", "seq"),
        Index("ix_audit_events_entity", "hospital_id", "entity_type", "entity_id"),
        Index("ix_audit_events_ts", "hospital_id", "server_ts"),
    )
    seq: Mapped[int] = mapped_column(BigInteger, nullable=False)
    actor_id: Mapped[uuid.UUID | None] = mapped_column(Uuid)
    actor_role: Mapped[str] = mapped_column(String(40), nullable=False)
    entity_type: Mapped[str] = mapped_column(String(40), nullable=False)
    entity_id: Mapped[uuid.UUID | None] = mapped_column(Uuid)
    task_id: Mapped[uuid.UUID | None] = mapped_column(Uuid)
    action: Mapped[str] = mapped_column(String(60), nullable=False)
    from_state: Mapped[str | None] = mapped_column(String(40))
    to_state: Mapped[str | None] = mapped_column(String(40))
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    server_ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    prev_hash: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    hash: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
