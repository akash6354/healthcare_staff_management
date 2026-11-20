"""Tenant isolation: RLS is on everywhere, and every endpoint returns 404 for another hospital's ids."""

import uuid

import pytest
from sqlalchemy import select, text
from sqlalchemy.exc import DBAPIError

from app.core.db import anonymous_session, tenant_session
from app.modules.org.models import Building
from app.modules.staff.models import User
from tests.conftest import AuthedUser, Tenant


async def test_every_tenant_table_has_forced_rls(hospital_a: Tenant) -> None:
    async with anonymous_session() as s:
        rows = (
            await s.execute(
                text(
                    """SELECT c.relname, c.relrowsecurity, c.relforcerowsecurity
                       FROM pg_class c JOIN information_schema.columns col
                         ON col.table_name = c.relname AND col.column_name = 'hospital_id'
                       WHERE c.relkind = 'r' AND col.table_schema = 'public'"""
                )
            )
        ).all()
    assert rows, "expected tenant tables"
    missing = [r.relname for r in rows if not (r.relrowsecurity and r.relforcerowsecurity)]
    assert missing == []


async def test_no_tenant_context_sees_nothing(admin_a: AuthedUser) -> None:
    async with anonymous_session() as s:
        assert (await s.scalars(select(User))).all() == []


async def test_tenant_context_sees_only_own_rows(admin_a: AuthedUser, admin_b: AuthedUser) -> None:
    async with tenant_session(admin_a.hospital_id) as s:
        ids = {u.id for u in (await s.scalars(select(User))).all()}
    assert admin_a.id in ids
    assert admin_b.id not in ids


async def test_cannot_insert_row_for_another_hospital(
    hospital_a: Tenant, hospital_b: Tenant
) -> None:
    with pytest.raises(DBAPIError):
        async with tenant_session(hospital_a.id) as s:
            s.add(Building(hospital_id=hospital_b.id, name="Sneaky", code="X1"))
            await s.flush()


async def test_composite_fk_blocks_cross_tenant_reference(
    client, admin_a: AuthedUser, admin_b: AuthedUser
) -> None:
    # A building in hospital B; hospital A tries to create a floor pointing at it.
    b = await client.post(
        "/api/v1/buildings", json={"name": "Main", "code": "MB"}, headers=admin_b.headers
    )
    resp = await client.post(
        "/api/v1/floors", json={"building_id": b.json()["id"], "label": "1", "level": 1},
        headers=admin_a.headers,
    )  # fmt: skip
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "INVALID_REFERENCE"


# ---- cross-tenant HTTP checks for every resource endpoint (CLAUDE.md rule 2) ----


async def _make_resources(client, admin: AuthedUser) -> dict[str, tuple[str, dict]]:
    h = admin.headers
    building = (
        await client.post("/api/v1/buildings", json={"name": "Main", "code": "MB"}, headers=h)
    ).json()
    floor = (
        await client.post(
            "/api/v1/floors",
            json={"building_id": building["id"], "label": "1", "level": 1},
            headers=h,
        )
    ).json()
    area_type = (
        await client.post(
            "/api/v1/area-types",
            json={"key": "test_room", "name_i18n": {"en": "Test room"}},
            headers=h,
        )
    ).json()
    dept = (
        await client.post(
            "/api/v1/departments", json={"name": "Housekeeping", "kind": "support"}, headers=h
        )
    ).json()
    area = (await client.post("/api/v1/areas", json={
        "floor_id": floor["id"], "area_type_id": area_type["id"], "code": "W1-WC", "name": "Washroom", "risk_level": "high",
    }, headers=h)).json()  # fmt: skip
    agency = (await client.post("/api/v1/agencies", json={"name": "CleanCo"}, headers=h)).json()
    vendor = (
        await client.post(
            "/api/v1/vendors", json={"name": "LiftCare", "categories": ["lift"]}, headers=h
        )
    ).json()
    shift = (
        await client.post(
            "/api/v1/shifts",
            json={"name": "Morning", "starts_at": "06:00", "ends_at": "14:00"},
            headers=h,
        )
    ).json()
    user = (await client.post("/api/v1/users", json={
        "employee_code": "HK-100", "display_name": "Worker One", "employment_type": "employee",
        "roles": [{"role": "worker"}],
    }, headers=h)).json()  # fmt: skip
    patches = {
        "buildings": {"name": "Hacked"}, "floors": {"label": "9"}, "area-types": {"default_risk": "low"},
        "departments": {"name": "Hacked"}, "areas": {"name": "Hacked"}, "agencies": {"name": "Hacked"},
        "vendors": {"name": "Hacked"}, "shifts": {"name": "Hacked"}, "users": {"display_name": "Hacked"},
    }  # fmt: skip
    created = {
        "buildings": building, "floors": floor, "area-types": area_type, "departments": dept,
        "areas": area, "agencies": agency, "vendors": vendor, "shifts": shift, "users": user,
    }  # fmt: skip
    for name, obj in created.items():
        assert "id" in obj, f"failed to create {name}: {obj}"
    return {name: (obj["id"], patches[name]) for name, obj in created.items()}


async def test_cross_tenant_access_returns_404_everywhere(
    client, admin_a: AuthedUser, admin_b: AuthedUser
) -> None:
    resources = await _make_resources(client, admin_a)
    for path, (rid, patch) in resources.items():
        url = f"/api/v1/{path}/{rid}"
        assert (await client.get(url, headers=admin_b.headers)).status_code == 404, f"GET {path}"
        assert (
            await client.patch(url, json=patch, headers=admin_b.headers)
        ).status_code == 404, f"PATCH {path}"
        listing = await client.get(f"/api/v1/{path}", headers=admin_b.headers)
        assert listing.status_code == 200
        assert rid not in {item["id"] for item in listing.json()}, f"LIST {path} leaks"
        if path != "users":
            assert (
                await client.delete(url, headers=admin_b.headers)
            ).status_code == 404, f"DELETE {path}"
        # still intact for the owner
        assert (await client.get(url, headers=admin_a.headers)).status_code == 200

    user_id = resources["users"][0]
    for sub in ("deactivate",):
        assert (
            await client.post(f"/api/v1/users/{user_id}/{sub}", headers=admin_b.headers)
        ).status_code == 404
    assert (
        await client.put(
            f"/api/v1/users/{user_id}/roles", json=[{"role": "worker"}], headers=admin_b.headers
        )
    ).status_code == 404
    assert (
        await client.put(
            f"/api/v1/users/{user_id}/pin", json={"pin": "4826"}, headers=admin_b.headers
        )
    ).status_code == 404


async def test_settings_and_hospital_are_per_tenant(
    client, admin_a: AuthedUser, admin_b: AuthedUser
) -> None:
    a = (await client.get("/api/v1/hospital", headers=admin_a.headers)).json()
    b = (await client.get("/api/v1/hospital", headers=admin_b.headers)).json()
    assert a["id"] == str(admin_a.hospital_id) and b["id"] == str(admin_b.hospital_id)
    s = (await client.get("/api/v1/hospital/settings", headers=admin_a.headers)).json()
    s["settings"]["housekeeping"]["inspect_random_pct"] = 35
    assert (
        await client.put("/api/v1/hospital/settings", json=s["settings"], headers=admin_a.headers)
    ).status_code == 200
    sb = (await client.get("/api/v1/hospital/settings", headers=admin_b.headers)).json()
    assert sb["settings"]["housekeeping"]["inspect_random_pct"] == 20


async def test_forged_token_for_other_hospital_rejected(
    client, admin_a: AuthedUser, hospital_b: Tenant
) -> None:
    import jwt

    from app.core.config import get_settings

    claims = jwt.decode(admin_a.token, options={"verify_signature": False})
    claims["hid"] = str(hospital_b.id)  # same session id, other hospital
    forged = jwt.encode(claims, get_settings().jwt_signing_key, algorithm="HS256")
    resp = await client.get("/api/v1/users", headers={"Authorization": f"Bearer {forged}"})
    assert resp.status_code == 401  # session lookup runs under hospital B's RLS and finds nothing


async def test_random_ids_are_404(client, admin_a: AuthedUser) -> None:
    assert (
        await client.get(f"/api/v1/areas/{uuid.uuid4()}", headers=admin_a.headers)
    ).status_code == 404
