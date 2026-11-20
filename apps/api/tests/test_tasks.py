"""Desk-wise task flow for the Olympus pilot: roster → my tasks → before/after photos → submit →
approve/reject, plus guards, fake-work flags, SLA escalation, entrance QR attendance and the notice."""

import io
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import pytest
from PIL import Image
from sqlalchemy import select, text
from sqlalchemy.exc import DBAPIError

from app.audit.service import verify_chain
from app.core.db import tenant_session
from app.modules.staff.models import Role, ScopeType
from app.modules.tasks.models import Task
from app.modules.tasks.service import sla_sweep, today_ist
from tests.conftest import AuthedUser, Tenant, make_user


def jpeg(color: tuple[int, int, int] = (200, 30, 30), size: int = 900) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (size, size), color).save(buf, "JPEG", quality=95)
    return buf.getvalue()


@dataclass
class Setup:
    admin: AuthedUser
    supervisor: AuthedUser
    worker: AuthedUser
    md: AuthedUser
    branch: dict
    desk: dict
    dept: dict


async def setup_desk(client, tenant: Tenant) -> Setup:
    admin = await make_user(tenant)
    h = admin.headers
    branch = (
        await client.post(
            "/api/v1/branches", json={"name": "Main branch", "code": "MAIN"}, headers=h
        )
    ).json()
    dept = (
        await client.post(
            "/api/v1/departments", json={"name": "Housekeeping", "kind": "support"}, headers=h
        )
    ).json()
    desk = (await client.post("/api/v1/desks", json={
        "branch_id": branch["id"], "department_id": dept["id"], "name": "Housekeeping Floor 2", "code": "HK-F2",
    }, headers=h)).json()  # fmt: skip
    shift = (
        await client.post(
            "/api/v1/shifts",
            json={"name": "Day", "starts_at": "00:00", "ends_at": "23:59"},
            headers=h,
        )
    ).json()
    supervisor = await make_user(
        tenant, Role.supervisor, scope_type=ScopeType.department, scope_id=dept["id"]
    )
    md = await make_user(tenant, Role.management_viewer)
    worker = await make_user(tenant, Role.worker, department_id=dept["id"])
    r = await client.post("/api/v1/roster", json={
        "user_id": str(worker.id), "shift_id": shift["id"], "work_date": today_ist().isoformat(),
        "desk_id": desk["id"], "department_id": dept["id"],
    }, headers=h)  # fmt: skip
    assert r.status_code == 201, r.text
    return Setup(admin, supervisor, worker, md, branch, desk, dept)


async def one_time_task(client, s: Setup, due_in_minutes: int = 120, **extra) -> dict:
    body = {
        "desk_id": s.desk["id"], "title_i18n": {"en": "Clean washroom W2", "kn": "ಶೌಚಾಲಯ", "hi": "शौचालय"},
        "checklist": [{"key": "floor", "label_i18n": {"en": "Floor mopped"}},
                      {"key": "soap", "label_i18n": {"en": "Soap refilled"}, "required": False}],
        "due_at": (datetime.now(UTC) + timedelta(minutes=due_in_minutes)).isoformat(), **extra,
    }  # fmt: skip
    r = await client.post("/api/v1/tasks", json=body, headers=s.supervisor.headers)
    assert r.status_code == 201, r.text
    return r.json()


async def photo(client, user: AuthedUser, task_id: str, phase: str, data: bytes | None = None):
    return await client.post(
        f"/api/v1/tasks/{task_id}/proofs", headers=user.headers,
        data={"phase": phase}, files={"photo": ("p.jpg", data or jpeg(), "image/jpeg")},
    )  # fmt: skip


async def test_full_desk_task_flow(client, hospital_a: Tenant) -> None:
    s = await setup_desk(client, hospital_a)
    task = await one_time_task(client, s)
    mine = (await client.get("/api/v1/me/tasks", headers=s.worker.headers)).json()
    assert [t["id"] for t in mine] == [task["id"]]

    w = s.worker.headers
    assert (await client.post(f"/api/v1/tasks/{task['id']}/start", headers=w)).json()[
        "status"
    ] == "in_progress"
    assert (await photo(client, s.worker, task["id"], "after")).status_code == 409  # before first
    before = await photo(client, s.worker, task["id"], "before", jpeg((10, 10, 10)))
    assert before.status_code == 201, before.text
    incomplete = await client.post(
        f"/api/v1/tasks/{task['id']}/submit", json={"checklist": {}}, headers=w
    )
    assert incomplete.json()["error"]["code"] == "CHECKLIST_INCOMPLETE"
    no_after = await client.post(
        f"/api/v1/tasks/{task['id']}/submit", json={"checklist": {"floor": True}}, headers=w
    )
    assert no_after.json()["error"]["code"] == "AFTER_PHOTO_REQUIRED"
    assert (
        await photo(client, s.worker, task["id"], "after", jpeg((240, 240, 240)))
    ).status_code == 201
    submitted = await client.post(
        f"/api/v1/tasks/{task['id']}/submit", json={"checklist": {"floor": True}}, headers=w
    )
    assert submitted.status_code == 200 and submitted.json()["task"]["status"] == "submitted"

    # worker can't approve own work; supervisor can
    assert (
        await client.post(f"/api/v1/tasks/{task['id']}/approve", json={}, headers=w)
    ).status_code == 403
    approved = await client.post(
        f"/api/v1/tasks/{task['id']}/approve", json={}, headers=s.supervisor.headers
    )
    assert approved.status_code == 200, approved.text
    assert approved.json()["status"] == "approved"

    detail = (await client.get(f"/api/v1/tasks/{task['id']}", headers=s.supervisor.headers)).json()
    assert {p["phase"] for p in detail["proofs"]} == {"before", "after"}
    assert all(p["url"] and p["thumb_url"] for p in detail["proofs"])
    timeline = (
        await client.get(f"/api/v1/tasks/{task['id']}/timeline", headers=s.supervisor.headers)
    ).json()
    assert [e["action"] for e in timeline] == [
        "task.created",
        "task.start",
        "task.proof_added",
        "task.proof_added",
        "task.submit",
        "task.approve",
    ]
    dash = (await client.get("/api/v1/dashboard/today", headers=s.md.headers)).json()
    assert dash["counts"]["done"] >= 1
    async with tenant_session(hospital_a.id) as db:
        assert (await verify_chain(db, hospital_a.id)).ok


async def test_reject_sends_back_for_rework(client, hospital_a: Tenant) -> None:
    s = await setup_desk(client, hospital_a)
    task = await one_time_task(client, s, requires_before_photo=False, requires_after_photo=False)
    w = s.worker.headers
    await client.post(f"/api/v1/tasks/{task['id']}/start", headers=w)
    await client.post(
        f"/api/v1/tasks/{task['id']}/submit", json={"checklist": {"floor": True}}, headers=w
    )
    no_reason = await client.post(
        f"/api/v1/tasks/{task['id']}/reject", json={}, headers=s.supervisor.headers
    )
    assert no_reason.status_code == 422
    rej = await client.post(
        f"/api/v1/tasks/{task['id']}/reject",
        json={"note": "Corner still dirty"},
        headers=s.supervisor.headers,
    )
    assert rej.json()["status"] == "pending" and rej.json()["rework_count"] == 1
    notes = (await client.get("/api/v1/notifications", headers=w)).json()
    assert any(n["kind"] == "task_rejected" for n in notes)


async def test_worker_off_desk_cannot_see_or_act(client, hospital_a: Tenant) -> None:
    s = await setup_desk(client, hospital_a)
    task = await one_time_task(client, s)
    other = await make_user(hospital_a, Role.worker)
    assert (
        await client.get(f"/api/v1/tasks/{task['id']}", headers=other.headers)
    ).status_code == 404
    assert (
        await client.post(f"/api/v1/tasks/{task['id']}/start", headers=other.headers)
    ).status_code == 404
    assert (await client.get("/api/v1/me/tasks", headers=other.headers)).json() == []


async def test_tasks_are_tenant_isolated(client, hospital_a: Tenant, hospital_b: Tenant) -> None:
    s = await setup_desk(client, hospital_a)
    task = await one_time_task(client, s)
    admin_b = await make_user(hospital_b)
    for method, path in [
        ("GET", f"/api/v1/tasks/{task['id']}"), ("POST", f"/api/v1/tasks/{task['id']}/start"),
        ("GET", f"/api/v1/desks/{s.desk['id']}"), ("GET", f"/api/v1/branches/{s.branch['id']}"),
        ("GET", f"/api/v1/branches/{s.branch['id']}/entrance-qr"),
    ]:  # fmt: skip
        assert (
            await client.request(method, path, headers=admin_b.headers)
        ).status_code == 404, path
    assert task["id"] not in {
        t["id"] for t in (await client.get("/api/v1/tasks", headers=admin_b.headers)).json()
    }


async def test_status_cannot_be_set_outside_state_machine(client, hospital_a: Tenant) -> None:
    s = await setup_desk(client, hospital_a)
    task = await one_time_task(client, s)
    with pytest.raises(DBAPIError):
        async with tenant_session(hospital_a.id) as db:
            await db.execute(
                text("UPDATE tasks SET status = 'approved' WHERE id = :i"), {"i": task["id"]}
            )


async def test_fake_work_flags(client, hospital_a: Tenant) -> None:
    s = await setup_desk(client, hospital_a)
    w = s.worker.headers
    reused = jpeg((1, 2, 3))
    first = await one_time_task(client, s)
    await client.post(f"/api/v1/tasks/{first['id']}/start", headers=w)
    await photo(client, s.worker, first["id"], "before", reused)
    await photo(client, s.worker, first["id"], "after", jpeg((9, 9, 9)))
    await client.post(
        f"/api/v1/tasks/{first['id']}/submit", json={"checklist": {"floor": True}}, headers=w
    )

    async with tenant_session(
        hospital_a.id
    ) as db:  # make the second task "expected to take 10 min"
        second = await one_time_task(client, s)
        await db.execute(
            text("UPDATE tasks SET min_minutes = 10 WHERE id = :i"), {"i": second["id"]}
        )
    await client.post(f"/api/v1/tasks/{second['id']}/start", headers=w)
    await photo(client, s.worker, second["id"], "before", reused)  # same photo again
    await photo(client, s.worker, second["id"], "after", jpeg((8, 8, 8)))
    res = (
        await client.post(
            f"/api/v1/tasks/{second['id']}/submit", json={"checklist": {"floor": True}}, headers=w
        )
    ).json()
    assert {f["rule"] for f in res["flags"]} >= {"too_fast", "duplicate_photo"}
    flags = (await client.get("/api/v1/flags", headers=s.supervisor.headers)).json()
    reviewed = await client.post(
        f"/api/v1/flags/{flags[0]['id']}/review",
        json={"status": "dismissed"},
        headers=s.supervisor.headers,
    )
    assert reviewed.json()["status"] == "dismissed"


async def test_overdue_escalates_supervisor_then_md(client, hospital_a: Tenant) -> None:
    s = await setup_desk(client, hospital_a)
    task = await one_time_task(client, s, due_in_minutes=1)
    due = datetime.fromisoformat(task["due_at"])
    async with tenant_session(hospital_a.id) as db:
        stats = await sla_sweep(db, hospital_a.id, now=due + timedelta(minutes=5))
    assert stats["overdue"] == 1
    assert any(
        n["kind"] == "task_escalated"
        for n in (await client.get("/api/v1/notifications", headers=s.supervisor.headers)).json()
    )
    assert not (await client.get("/api/v1/notifications", headers=s.md.headers)).json()
    async with tenant_session(hospital_a.id) as db:
        await sla_sweep(db, hospital_a.id, now=due + timedelta(minutes=61))
        row = (await db.scalars(select(Task).where(Task.id == task["id"]))).one()
        assert row.escalation_level == 2
    assert any(
        n["kind"] == "task_escalated"
        for n in (await client.get("/api/v1/notifications", headers=s.md.headers)).json()
    )


async def test_scheduled_templates_materialise_once(client, hospital_a: Tenant) -> None:
    s = await setup_desk(client, hospital_a)
    t = await client.post("/api/v1/task-templates", json={
        "desk_id": s.desk["id"], "title_i18n": {"en": "Morning round"}, "schedule_kind": "daily",
        "times": ["09:00", "13:00", "17:00"], "checklist": [{"key": "bins", "label_i18n": {"en": "Bins emptied"}}],
    }, headers=s.admin.headers)  # fmt: skip
    assert t.status_code == 201, t.text
    for _ in range(2):
        mine = (await client.get("/api/v1/me/tasks", headers=s.worker.headers)).json()
    assert len([m for m in mine if m["title_i18n"]["en"] == "Morning round"]) == 3


async def test_entrance_qr_attendance(client, hospital_a: Tenant, hospital_b: Tenant) -> None:
    s = await setup_desk(client, hospital_a)
    qr = (
        await client.get(f"/api/v1/branches/{s.branch['id']}/entrance-qr", headers=s.admin.headers)
    ).json()
    assert qr["svg"].startswith("<?xml") or "<svg" in qr["svg"]
    ok = await client.post(
        "/api/v1/attendance/scan",
        json={"token": qr["token"], "kind": "check_in"},
        headers=s.worker.headers,
    )
    assert ok.status_code == 201
    forged = qr["token"][:-3] + ("AAA" if not qr["token"].endswith("AAA") else "BBB")
    assert (
        await client.post(
            "/api/v1/attendance/scan",
            json={"token": forged, "kind": "check_in"},
            headers=s.worker.headers,
        )
    ).status_code == 422
    other = await make_user(hospital_b, Role.worker)
    assert (
        await client.post(
            "/api/v1/attendance/scan",
            json={"token": qr["token"], "kind": "check_in"},
            headers=other.headers,
        )
    ).status_code == 422
    await client.post(
        f"/api/v1/branches/{s.branch['id']}/entrance-qr/rotate", headers=s.admin.headers
    )
    old = await client.post(
        "/api/v1/attendance/scan",
        json={"token": qr["token"], "kind": "check_out"},
        headers=s.worker.headers,
    )
    assert old.json()["error"]["code"] == "QR_NO_LONGER_ACTIVE"
    today = (await client.get("/api/v1/attendance/today", headers=s.supervisor.headers)).json()
    assert len(today) == 1 and today[0]["kind"] == "check_in"


async def test_staff_notice_must_be_acknowledged(client, hospital_a: Tenant) -> None:
    worker = await make_user(hospital_a, Role.worker)
    notice = (await client.get("/api/v1/notice/current", headers=worker.headers)).json()
    assert notice["acknowledged"] is False and set(notice["body_i18n"]) == {"en", "kn", "hi"}
    assert "GPS" in notice["body_i18n"]["en"]
    assert (
        await client.post(f"/api/v1/notice/{notice['id']}/ack", headers=worker.headers)
    ).status_code == 204
    assert (await client.get("/api/v1/notice/current", headers=worker.headers)).json()[
        "acknowledged"
    ] is True


async def test_photo_validation(client, hospital_a: Tenant) -> None:
    s = await setup_desk(client, hospital_a)
    task = await one_time_task(client, s)
    await client.post(f"/api/v1/tasks/{task['id']}/start", headers=s.worker.headers)
    bad = await photo(client, s.worker, task["id"], "before", b"%PDF-1.4 not an image")
    assert bad.json()["error"]["code"] == "PHOTO_TYPE_NOT_ALLOWED"
    big = jpeg(size=3000)
    ok = await photo(client, s.worker, task["id"], "before", big)
    assert ok.status_code == 201
    async with tenant_session(hospital_a.id) as db:
        size = await db.scalar(
            text("SELECT bytes FROM task_proofs WHERE id = :i"), {"i": ok.json()["id"]}
        )
    assert size <= 200 * 1024
