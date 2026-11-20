"""Policy matrix: every role x representative endpoint is allowed exactly when ROLE_PERMISSIONS says so."""

import pytest

from app.main import app
from app.modules.staff.models import Role, ScopeType
from app.policy.deps import undeclared_routes
from app.policy.permissions import ROLE_PERMISSIONS, Perm
from tests.conftest import Tenant, make_user

# (method, path, body, permission it needs)
ENDPOINTS: list[tuple[str, str, dict | None, Perm]] = [
    ("GET", "/api/v1/hospital/settings", None, Perm.settings_view),
    ("GET", "/api/v1/hospital/modules", None, Perm.settings_view),
    ("POST", "/api/v1/buildings", {"name": "B", "code": "PB"}, Perm.org_manage),
    ("GET", "/api/v1/buildings", None, Perm.org_view),
    (
        "POST",
        "/api/v1/area-types",
        {"key": "pol_room", "name_i18n": {"en": "Room"}},
        Perm.config_manage,
    ),
    ("GET", "/api/v1/users", None, Perm.staff_view),
    ("POST", "/api/v1/vendors", {"name": "Vendor"}, Perm.vendor_manage),
    ("GET", "/api/v1/devices", None, Perm.device_manage),
    ("GET", "/api/v1/me", None, Perm.self_service),
]


def test_all_routes_declare_permission_or_public() -> None:
    assert undeclared_routes(app) == []


def test_matrix_has_every_role() -> None:
    assert set(ROLE_PERMISSIONS) == set(Role)


@pytest.mark.parametrize("role", list(Role))
async def test_role_matrix(client, hospital_a: Tenant, role: Role) -> None:
    scope_type, scope_id = ScopeType.hospital, None
    user = await make_user(hospital_a, role, scope_type=scope_type, scope_id=scope_id)
    for method, path, body, perm in ENDPOINTS:
        if body and "code" in body:
            body = {**body, "code": f"{body['code']}{role.value[:3].upper()}"}
        if body and "key" in body:
            body = {**body, "key": f"{body['key']}_{role.value[:3]}"}
        resp = await client.request(method, path, json=body, headers=user.headers)
        allowed = perm in ROLE_PERMISSIONS[role]
        if allowed:
            assert (
                resp.status_code < 400
            ), f"{role} {method} {path} -> {resp.status_code} {resp.text}"
        else:
            assert (
                resp.status_code == 403
            ), f"{role} {method} {path} should be denied, got {resp.status_code}"


async def test_mfa_pending_blocks_everything_except_enrolment(client, hospital_a: Tenant) -> None:
    user = await make_user(hospital_a, Role.hospital_admin, mfa_pending=True)
    resp = await client.get("/api/v1/users", headers=user.headers)
    assert resp.status_code == 403
    assert resp.json()["error"]["code"] == "MFA_ENROLLMENT_REQUIRED"
    assert (await client.get("/api/v1/me", headers=user.headers)).status_code == 200
    assert (await client.post("/api/v1/auth/totp/enroll", headers=user.headers)).status_code == 200


async def test_dept_head_limited_to_own_department(client, hospital_a: Tenant) -> None:
    admin = await make_user(hospital_a)
    d1 = (
        await client.post(
            "/api/v1/departments", json={"name": "HK", "kind": "support"}, headers=admin.headers
        )
    ).json()
    d2 = (
        await client.post(
            "/api/v1/departments", json={"name": "Maint", "kind": "support"}, headers=admin.headers
        )
    ).json()
    head = await make_user(
        hospital_a, Role.dept_head, scope_type=ScopeType.department, scope_id=d1["id"]
    )

    ok = await client.post("/api/v1/users", headers=head.headers, json={
        "employee_code": "HK-7", "display_name": "Own Dept Worker", "employment_type": "employee",
        "department_id": d1["id"], "roles": [{"role": "worker", "scope_type": "department", "scope_id": d1["id"]}],
    })  # fmt: skip
    assert ok.status_code == 201, ok.text
    other = await client.post("/api/v1/users", headers=head.headers, json={
        "employee_code": "MT-7", "display_name": "Other Dept", "employment_type": "employee",
        "department_id": d2["id"], "roles": [{"role": "worker", "scope_type": "department", "scope_id": d2["id"]}],
    })  # fmt: skip
    assert other.status_code == 403
    escalate = await client.post("/api/v1/users", headers=head.headers, json={
        "employee_code": "HK-8", "display_name": "Wannabe Admin", "employment_type": "employee",
        "department_id": d1["id"], "roles": [{"role": "hospital_admin"}],
    })  # fmt: skip
    assert escalate.status_code == 403
    listed = {
        u["employee_code"] for u in (await client.get("/api/v1/users", headers=head.headers)).json()
    }
    assert "HK-7" in listed and "MT-7" not in listed


async def test_phone_masked_for_viewers_without_staff_manage(client, hospital_a: Tenant) -> None:
    admin = await make_user(hospital_a)
    created = await client.post("/api/v1/users", headers=admin.headers, json={
        "employee_code": "PH-1", "display_name": "Phone Person", "employment_type": "employee",
        "phone": "+919876543210", "roles": [{"role": "worker"}],
    })  # fmt: skip
    assert created.json()["phone"] == "+919876543210"
    viewer = await make_user(hospital_a, Role.management_viewer)
    seen = await client.get(f"/api/v1/users/{created.json()['id']}", headers=viewer.headers)
    assert seen.json()["phone"] == "98•••••210"
