"""DPDP rights and retention: export, erase (anonymise, keep audit chain), photo purge, leaver purge."""

from datetime import UTC, datetime, timedelta

from botocore.exceptions import ClientError
from sqlalchemy import select, text

from app.audit.service import verify_chain
from app.core.config import get_settings
from app.core.db import tenant_session
from app.core.storage import s3
from app.modules.privacy.service import apply_retention
from app.modules.staff.models import Role, User
from app.modules.tasks.models import TaskProof
from tests.conftest import Tenant, make_user
from tests.test_tasks import jpeg, one_time_task, photo, setup_desk


async def test_export_contains_my_data_and_is_admin_only(client, hospital_a: Tenant) -> None:
    s = await setup_desk(client, hospital_a)
    task = await one_time_task(client, s)
    await client.post(f"/api/v1/tasks/{task['id']}/start", headers=s.worker.headers)
    await photo(client, s.worker, task["id"], "before")
    r = await client.get(f"/api/v1/privacy/users/{s.worker.id}/export", headers=s.admin.headers)
    assert r.status_code == 200
    body = r.json()
    assert body["profile"]["id"] == str(s.worker.id)
    assert body["roster"] and body["tasks"] and body["photos"]
    denied = await client.get(
        f"/api/v1/privacy/users/{s.worker.id}/export", headers=s.supervisor.headers
    )
    assert denied.status_code == 403


async def test_erase_anonymises_and_keeps_chain(
    client, hospital_a: Tenant, hospital_b: Tenant
) -> None:
    admin = await make_user(hospital_a)
    created = await client.post("/api/v1/users", headers=admin.headers, json={
        "employee_code": "LEFT-1", "display_name": "Leaving Person", "email": "leaver@sunrise.example.org",
        "phone": "+919812345678", "emergency_contact": "Relative, 9812300000",
        "employment_type": "employee", "roles": [{"role": "worker"}],
    })  # fmt: skip
    uid = created.json()["id"]
    early = await client.post(f"/api/v1/privacy/users/{uid}/erase", headers=admin.headers)
    assert early.json()["error"]["code"] == "ERASE_REQUIRES_DEACTIVATION"
    await client.post(f"/api/v1/users/{uid}/deactivate", headers=admin.headers)
    admin_b = await make_user(hospital_b)
    for method, path in [
        ("POST", f"/api/v1/privacy/users/{uid}/erase"),
        ("GET", f"/api/v1/privacy/users/{uid}/export"),
    ]:
        assert (await client.request(method, path, headers=admin_b.headers)).status_code == 404
    assert (
        await client.post(f"/api/v1/privacy/users/{uid}/erase", headers=admin.headers)
    ).status_code == 204
    async with tenant_session(hospital_a.id) as db:
        u = (await db.scalars(select(User).where(User.id == uid))).one()
        assert u.display_name == "Staff #LEFT-1"
        assert u.email is None and u.phone_enc is None and u.emergency_contact_enc is None
        assert u.status.value == "erased"
        assert (await verify_chain(db, hospital_a.id)).ok


async def test_retention_purges_old_photos_and_leavers(client, hospital_a: Tenant) -> None:
    s = await setup_desk(client, hospital_a)
    task = await one_time_task(client, s)
    await client.post(f"/api/v1/tasks/{task['id']}/start", headers=s.worker.headers)
    proof = (await photo(client, s.worker, task["id"], "before", jpeg((3, 3, 3)))).json()
    leaver = await make_user(hospital_a, Role.worker)
    await client.post(f"/api/v1/users/{leaver.id}/deactivate", headers=s.admin.headers)

    async with tenant_session(hospital_a.id) as db:
        stats = await apply_retention(
            db, hospital_a.id, now=datetime.now(UTC) + timedelta(days=400)
        )
        key = await db.scalar(select(TaskProof.object_key).where(TaskProof.id == proof["id"]))
        status = await db.scalar(
            text("SELECT status FROM users WHERE id = :i"), {"i": str(leaver.id)}
        )
    assert stats["photos_purged"] >= 1 and stats["staff_anonymised"] >= 1
    assert status == "erased"
    try:
        s3().head_object(Bucket=get_settings().s3_bucket, Key=key)
        raise AssertionError("full photo should be deleted")
    except ClientError:
        pass
    detail = (await client.get(f"/api/v1/tasks/{task['id']}", headers=s.supervisor.headers)).json()
    purged = next(p for p in detail["proofs"] if p["id"] == proof["id"])
    assert purged["url"] is None and purged["thumb_url"]
