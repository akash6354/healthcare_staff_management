"""Import every model so Base.metadata is complete (Alembic, tests)."""

from app.audit.models import AuditEvent
from app.db.base import Base
from app.modules.auth.models import AuthSession, Credential, OtpChallenge, RefreshToken
from app.modules.org.models import (
    Area,
    AreaType,
    Branch,
    Building,
    Department,
    Desk,
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
from app.modules.tasks.models import (
    Counter,
    NoticeAcknowledgement,
    Notification,
    PrivacyNotice,
    Task,
    TaskFlag,
    TaskProof,
    TaskTemplate,
)

__all__ = [
    "Agency",
    "Area",
    "AreaType",
    "AuditEvent",
    "AuthSession",
    "Base",
    "Branch",
    "Building",
    "Counter",
    "Credential",
    "Department",
    "Desk",
    "Device",
    "Floor",
    "Hospital",
    "HospitalModule",
    "HospitalSettings",
    "NoticeAcknowledgement",
    "Notification",
    "OtpChallenge",
    "PrivacyNotice",
    "RefreshToken",
    "RosterEntry",
    "Shift",
    "ShiftCheckin",
    "Task",
    "TaskFlag",
    "TaskProof",
    "TaskTemplate",
    "User",
    "UserRole",
    "Vendor",
]  # fmt: skip
