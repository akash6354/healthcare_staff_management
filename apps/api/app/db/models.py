"""Import every model so Base.metadata is complete (Alembic, tests)."""

from app.audit.models import AuditEvent
from app.db.base import Base
from app.modules.auth.models import AuthSession, Credential, OtpChallenge, RefreshToken
from app.modules.org.models import (
    Area,
    AreaType,
    Building,
    Department,
    Floor,
    Hospital,
    HospitalModule,
    HospitalSettings,
)
from app.modules.staff.models import (
    Agency,
    Device,
    RosterEntry,
    Shift,
    ShiftCheckin,
    User,
    UserRole,
    Vendor,
)

__all__ = [
    "Agency", "Area", "AreaType", "AuditEvent", "AuthSession", "Base", "Building", "Credential",
    "Department", "Device", "Floor", "Hospital", "HospitalModule", "HospitalSettings",
    "OtpChallenge", "RefreshToken", "RosterEntry", "Shift", "ShiftCheckin", "User", "UserRole",
    "Vendor",
]  # fmt: skip
