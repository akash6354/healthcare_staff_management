"""Credentials, OTP challenges, sessions and rotating refresh tokens. Secrets are stored only as hashes."""

import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKeyConstraint,
    Integer,
    LargeBinary,
    String,
    Text,
    Uuid,
    func,
)
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, IdMixin, TenantMixin, TimestampMixin, tenant_fk


class Credential(TenantMixin, TimestampMixin, Base):
    __tablename__ = "credentials"
    __table_args__ = (  # type: ignore[assignment]
        ForeignKeyConstraint(["hospital_id"], ["hospitals.id"], ondelete="RESTRICT"),
        tenant_fk("user_id", "users"),
    )
    user_id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True)
    password_hash: Mapped[str | None] = mapped_column(Text)
    pin_hash: Mapped[str | None] = mapped_column(Text)
    totp_secret_enc: Mapped[bytes | None] = mapped_column(LargeBinary)
    totp_enabled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    recovery_code_hashes: Mapped[list[str]] = mapped_column(
        ARRAY(Text), nullable=False, default=list
    )
    failed_attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    lockout_level: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    locked_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    password_changed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class OtpChallenge(IdMixin, TenantMixin, Base):
    __tablename__ = "otp_challenges"
    __tenant_args__ = (tenant_fk("user_id", "users"),)
    user_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False, index=True)
    channel: Mapped[str] = mapped_column(String(12), nullable=False, default="email")
    code_hash: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    consumed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.clock_timestamp(), nullable=False
    )


class AuthSession(IdMixin, TenantMixin, Base):
    __tablename__ = "sessions"
    __tenant_args__ = (tenant_fk("user_id", "users"), tenant_fk("device_id", "devices"))
    user_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False, index=True)
    device_id: Mapped[uuid.UUID | None] = mapped_column(Uuid)
    amr: Mapped[list[str]] = mapped_column(ARRAY(String(12)), nullable=False)
    mfa_satisfied: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    user_agent_summary: Mapped[str | None] = mapped_column(String(120))
    ip_hash: Mapped[bytes | None] = mapped_column(LargeBinary)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.clock_timestamp(), nullable=False
    )
    absolute_expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revoke_reason: Mapped[str | None] = mapped_column(String(40))


class RefreshToken(IdMixin, TenantMixin, Base):
    __tablename__ = "refresh_tokens"
    __tenant_args__ = (tenant_fk("session_id", "sessions"),)
    session_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False, index=True)
    token_hash: Mapped[bytes] = mapped_column(LargeBinary, nullable=False, unique=True)
    parent_id: Mapped[uuid.UUID | None] = mapped_column(Uuid)
    issued_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.clock_timestamp(), nullable=False
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
