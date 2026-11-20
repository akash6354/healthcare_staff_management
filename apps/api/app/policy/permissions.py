"""The single source of truth for who may do what (docs/security.md §3).

Deny by default: a (role, permission) pair that is not listed here is denied.
Scopes: hospital ⊃ department ⊃ area; self = assignee/requester; vendor = own vendor.
"""

import enum

from app.modules.staff.models import Role


class Perm(enum.StrEnum):
    settings_view = "settings.view"
    settings_manage = "settings.manage"
    config_manage = "config.manage"
    org_view = "org.view"
    org_manage = "org.manage"
    staff_view = "staff.view"
    staff_manage = "staff.manage"
    roster_manage = "roster.manage"
    vendor_manage = "vendor.manage"
    device_manage = "device.manage"
    task_view = "task.view"
    task_create = "task.create"
    task_assign = "task.assign"
    task_verify = "task.verify"
    task_hold = "task.hold"
    task_cancel = "task.cancel"
    inspection_perform = "inspection.perform"
    board_view = "board.view"
    report_view = "report.view"
    audit_view = "audit.view"
    audit_export = "audit.export"
    asset_manage = "asset.manage"
    privacy_manage = "privacy.manage"
    breach_manage = "breach.manage"
    discharge_trigger = "discharge.trigger"
    self_service = "self.service"  # own profile, sessions, check-in, notifications


class Scope(enum.IntEnum):
    """Ordered from narrowest to widest so `max()` gives the widest grant."""

    self = 1
    vendor = 2
    area = 3
    department = 4
    hospital = 5


H, D, A, S, V = Scope.hospital, Scope.department, Scope.area, Scope.self, Scope.vendor
P = Perm

_EVERYONE: dict[Perm, Scope] = {P.self_service: S, P.org_view: H}

ROLE_PERMISSIONS: dict[Role, dict[Perm, Scope]] = {
    Role.hospital_admin: {
        **_EVERYONE,
        P.settings_view: H, P.settings_manage: H, P.config_manage: H, P.org_manage: H,
        P.staff_view: H, P.staff_manage: H, P.roster_manage: H, P.vendor_manage: H,
        P.device_manage: H, P.task_view: H, P.task_create: H, P.task_assign: H,
        P.task_hold: H, P.task_cancel: H, P.board_view: H, P.report_view: H,
        P.audit_view: H, P.audit_export: H, P.asset_manage: H, P.privacy_manage: H,
        P.breach_manage: H, P.discharge_trigger: H,
    },
    Role.management_viewer: {
        **_EVERYONE,
        P.settings_view: H, P.staff_view: H, P.task_view: H, P.board_view: H,
        P.report_view: H, P.audit_view: H, P.audit_export: H,
    },
    Role.ops_manager: {
        **_EVERYONE,
        P.settings_view: H, P.config_manage: H, P.org_manage: H, P.staff_view: H,
        P.staff_manage: H, P.roster_manage: H, P.vendor_manage: H, P.device_manage: H,
        P.task_view: H, P.task_create: H, P.task_assign: H, P.task_verify: H,
        P.task_hold: H, P.task_cancel: H, P.inspection_perform: H, P.board_view: H,
        P.report_view: H, P.audit_view: H, P.audit_export: H, P.asset_manage: H,
        P.discharge_trigger: H,
    },
    Role.dept_head: {
        **_EVERYONE,
        P.staff_view: D, P.staff_manage: D, P.roster_manage: D, P.task_view: D,
        P.task_create: D, P.task_assign: D, P.task_verify: D, P.task_hold: D,
        P.task_cancel: D, P.inspection_perform: D, P.board_view: D, P.report_view: D,
        P.audit_view: D, P.discharge_trigger: D,
    },
    Role.supervisor: {
        **_EVERYONE,
        P.staff_view: A, P.roster_manage: A, P.task_view: A, P.task_create: A,
        P.task_assign: A, P.task_verify: A, P.task_hold: A, P.task_cancel: A,
        P.inspection_perform: A, P.board_view: A, P.report_view: A, P.audit_view: A,
        P.discharge_trigger: A,
    },
    Role.worker: {**_EVERYONE, P.task_view: S, P.task_create: S, P.report_view: S},
    Role.requester: {**_EVERYONE, P.task_view: S, P.task_create: S, P.discharge_trigger: A},
    Role.vendor_user: {P.self_service: S, P.task_view: V, P.report_view: V},
    Role.quality_coordinator: {
        **_EVERYONE,
        P.task_view: H, P.task_verify: H, P.inspection_perform: H, P.board_view: H,
        P.report_view: H, P.audit_view: H, P.audit_export: H,
    },
}  # fmt: skip

# Roles that must have TOTP 2FA before using anything except enrolment (security.md §2).
MFA_REQUIRED_ROLES = frozenset(
    {
        Role.hospital_admin,
        Role.management_viewer,
        Role.ops_manager,
        Role.dept_head,
        Role.quality_coordinator,
    }
)

# Roles that sign in with a password (+TOTP where required) rather than email OTP / PIN.
PASSWORD_ROLES = MFA_REQUIRED_ROLES | {Role.vendor_user}
