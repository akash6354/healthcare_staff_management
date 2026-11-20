"""`make seed`: demo hospital "Sunrise Multispeciality, Bengaluru" (synthetic data only, no real people).

Mirrors the Olympus pilot shape: two branches, housekeeping desks per floor, a roster for today,
task templates, and a day of tasks in mixed states so the dashboard has something to show.
Idempotent: re-running prints the logins again without duplicating data.

Everything goes through the real API (in-process), so RLS, validation and audit all apply.
"""

import asyncio
import io
import os
import sys
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
import pyotp
from PIL import Image, ImageDraw
from sqlalchemy import select

from app.core.crypto import decrypt_field
from app.core.db import dispose_engines, platform_session, tenant_session
from app.main import app
from app.modules.auth.models import Credential
from app.modules.auth.service import _create_session, set_password, set_pin
from app.modules.org.models import Hospital
from app.modules.platform.service import create_hospital
from app.modules.staff.models import EmploymentType, Role, ScopeType, User, UserRole
from app.modules.tasks.service import today_ist

CODE = "SUNRISE"
PASSWORD = os.environ.get("SEED_PASSWORD", "sunrise-demo-2026")  # demo only, never production
PIN = "4826"

# Synthetic names (not real people).
WORKERS = [
    ("HK-101", "Lakshmi R", "kn"), ("HK-102", "Manjunath S", "kn"), ("HK-103", "Shabana B", "hi"),
    ("HK-104", "Ravi Kumar", "kn"), ("HK-105", "Geetha M", "kn"), ("HK-106", "Anil Yadav", "hi"),
]  # fmt: skip

CHECKLIST_WASHROOM = [
    {"key": "floor", "icon": "mop", "label_i18n": {"en": "Floor mopped and dry", "kn": "ನೆಲ ಒರೆಸಿ ಒಣಗಿಸಲಾಗಿದೆ", "hi": "फ़र्श पोछा और सूखा"}},
    {"key": "toilet", "icon": "toilet", "label_i18n": {"en": "Toilets disinfected", "kn": "ಶೌಚಾಲಯ ಸೋಂಕುರಹಿತ", "hi": "शौचालय कीटाणुरहित"}},
    {"key": "soap", "icon": "soap", "label_i18n": {"en": "Soap and tissue refilled", "kn": "ಸೋಪು ಮತ್ತು ಟಿಶ್ಯೂ ತುಂಬಿಸಲಾಗಿದೆ", "hi": "साबुन और टिश्यू भरा"}},
    {"key": "bin", "icon": "bin", "label_i18n": {"en": "Bin emptied", "kn": "ಕಸದ ಬುಟ್ಟಿ ಖಾಲಿ", "hi": "कूड़ादान खाली"}},
]  # fmt: skip
CHECKLIST_FLOOR = [
    {"key": "corridor", "icon": "mop", "label_i18n": {"en": "Corridor mopped", "kn": "ಕಾರಿಡಾರ್ ಒರೆಸಲಾಗಿದೆ", "hi": "गलियारा पोछा"}},
    {"key": "dust", "icon": "spray", "label_i18n": {"en": "Handrails and doors wiped", "kn": "ಕೈಹಿಡಿ ಮತ್ತು ಬಾಗಿಲು ಒರೆಸಲಾಗಿದೆ", "hi": "रेलिंग और दरवाज़े पोंछे"}},
    {"key": "bins", "icon": "bin", "label_i18n": {"en": "All bins emptied", "kn": "ಎಲ್ಲ ಕಸದ ಬುಟ್ಟಿ ಖಾಲಿ", "hi": "सभी कूड़ेदान खाली"}},
]  # fmt: skip


def demo_photo(label: str, shade: tuple[int, int, int]) -> bytes:
    img = Image.new("RGB", (960, 720), shade)
    d = ImageDraw.Draw(img)
    for x in range(0, 960, 60):
        d.line([(x, 0), (x + 200, 720)], fill=tuple(min(255, c + 18) for c in shade), width=3)
    d.text((24, 24), f"DEMO PHOTO  {label}", fill=(255, 255, 255))
    buf = io.BytesIO()
    img.save(buf, "JPEG", quality=90)
    return buf.getvalue()


class Seeder:
    def __init__(self, client: httpx.AsyncClient, hid: uuid.UUID) -> None:
        self.c, self.hid = client, hid
        self.tokens: dict[uuid.UUID, str] = {}

    async def user(
        self, code: str, name: str, roles: list[tuple[Role, ScopeType, uuid.UUID | None]], *,
        email: str | None = None, lang: str = "en", dept: uuid.UUID | None = None,
        branch: uuid.UUID | None = None, password: bool = False, pin: bool = False, totp: bool = False,
    ) -> tuple[uuid.UUID, str | None]:  # fmt: skip
        async with tenant_session(self.hid) as s:
            u = User(
                hospital_id=self.hid, employee_code=code, display_name=name, email=email,
                preferred_language=lang, employment_type=EmploymentType.employee,
                department_id=dept, branch_id=branch,
                joining_date=(datetime.now(UTC) - timedelta(days=400)).date(),
            )  # fmt: skip
            s.add(u)
            await s.flush()
            for role, st, sid in roles:
                s.add(
                    UserRole(
                        hospital_id=self.hid, user_id=u.id, role=role, scope_type=st, scope_id=sid
                    )
                )
            await s.flush()
            if password:
                await set_password(s, u, PASSWORD)
            if pin:
                await set_pin(s, u, PIN)
            secret = None
            if totp:
                from app.core.crypto import encrypt_field

                secret = pyotp.random_base32()
                cred = await s.get(Credential, u.id)
                assert cred is not None  # noqa: S101 - seed script
                cred.totp_secret_enc = encrypt_field(secret)
                cred.totp_enabled_at = datetime.now(UTC)
            issued = await _create_session(s, u, amr=["seed"], mfa_pending=False)
            self.tokens[u.id] = issued.access_token
        return u.id, secret

    def h(self, uid: uuid.UUID) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.tokens[uid]}"}

    async def post(self, uid: uuid.UUID, path: str, body: Any = None, **kw: Any) -> Any:
        r = await self.c.post(f"/api/v1{path}", json=body, headers=self.h(uid), **kw)
        if r.status_code >= 400:
            raise RuntimeError(f"POST {path} -> {r.status_code} {r.text}")
        return r.json() if r.content else None

    async def get(self, uid: uuid.UUID, path: str) -> Any:
        r = await self.c.get(f"/api/v1{path}", headers=self.h(uid))
        r.raise_for_status()
        return r.json()


async def seed() -> None:
    async with platform_session() as ps:
        existing = await ps.scalar(select(Hospital).where(Hospital.code == CODE))
    if existing:
        print(f"{CODE} already seeded ({existing.id}). Logins below.\n")
        await print_logins(existing.id)
        return

    h = await create_hospital(code=CODE, name="Sunrise Multispeciality", city="Bengaluru")
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="https://seed") as c:
        sd = Seeder(c, h.id)
        admin, admin_totp = await sd.user("ADM-001", "Priya Nair (Admin)", [(Role.hospital_admin, ScopeType.hospital, None)],
                                          email="admin@sunrise.example.org", password=True, totp=True)  # fmt: skip
        A = admin
        main = await sd.post(
            A,
            "/branches",
            {"name": "Jayanagar (main)", "code": "JAY", "address_line": "Demo address, Jayanagar"},
        )
        await sd.post(
            A,
            "/branches",
            {"name": "Whitefield", "code": "WFD", "address_line": "Demo address, Whitefield"},
        )
        bld = await sd.post(
            A,
            "/buildings",
            {"branch_id": main["id"], "name": "Main block", "code": "MB", "sort": 1},
        )
        floors = {}
        for label, level in [("B1", -1), ("G", 0), ("1", 1), ("2", 2), ("3", 3), ("4", 4)]:
            floors[label] = await sd.post(
                A, "/floors", {"building_id": bld["id"], "label": label, "level": level}
            )
        hk = await sd.post(A, "/departments", {"name": "Housekeeping", "kind": "support"})
        nursing = await sd.post(A, "/departments", {"name": "Nursing", "kind": "clinical_unit"})
        await sd.post(A, "/departments", {"name": "Front office", "kind": "admin"})
        desks = {}
        for label in ["G", "1", "2", "3", "4", "B1"]:
            name = (
                "Housekeeping Basement"
                if label == "B1"
                else ("Housekeeping Ground" if label == "G" else f"Housekeeping Floor {label}")
            )
            desks[label] = await sd.post(A, "/desks", {
                "branch_id": main["id"], "department_id": hk["id"], "floor_id": floors[label]["id"],
                "name": name, "code": f"HK-{label}",
            })  # fmt: skip
        await sd.post(
            A,
            "/desks",
            {
                "branch_id": main["id"],
                "department_id": nursing["id"],
                "floor_id": floors["3"]["id"],
                "name": "Ward 3 Nurse Station",
                "code": "W3-NS",
            },
        )
        shifts = [await sd.post(A, "/shifts", s) for s in (
            {"name": "Morning", "starts_at": "07:00", "ends_at": "15:00"},
            {"name": "Evening", "starts_at": "15:00", "ends_at": "23:00"},
            {"name": "Night", "starts_at": "23:00", "ends_at": "07:00", "crosses_midnight": True},
        )]  # fmt: skip

        md, md_totp = await sd.user("MD-001", "Dr. Arvind Rao (MD)", [(Role.management_viewer, ScopeType.hospital, None)],
                                    email="md@sunrise.example.org", password=True, totp=True)  # fmt: skip
        sup, _ = await sd.user("SUP-001", "Kavitha S (Supervisor)", [(Role.supervisor, ScopeType.department, uuid.UUID(hk["id"]))],
                               email="supervisor@sunrise.example.org", dept=uuid.UUID(hk["id"]), password=True)  # fmt: skip
        await sd.user("NUR-301", "Sister Mary J (Ward 3)", [(Role.requester, ScopeType.department, uuid.UUID(nursing["id"]))],
                      email="ward3@sunrise.example.org", dept=uuid.UUID(nursing["id"]))  # fmt: skip
        worker_ids = []
        for code, name, lang in WORKERS:
            uid, _ = await sd.user(code, name, [(Role.worker, ScopeType.department, uuid.UUID(hk["id"]))],
                                   email=f"{code.lower()}@sunrise.example.org", lang=lang, dept=uuid.UUID(hk["id"]),
                                   branch=uuid.UUID(main["id"]), pin=True)  # fmt: skip
            worker_ids.append(uid)
        device = await sd.post(A, "/devices", {"label": "Housekeeping shared phone (demo)"})

        day = today_ist().isoformat()
        for uid, label in zip(worker_ids, ["G", "1", "2", "3", "4", "B1"], strict=True):
            await sd.post(A, "/roster", {"user_id": str(uid), "shift_id": shifts[0]["id"], "work_date": day,
                                        "desk_id": desks[label]["id"], "department_id": hk["id"]})  # fmt: skip

        for label, desk in desks.items():
            await sd.post(A, "/task-templates", {
                "desk_id": desk["id"], "schedule_kind": "daily", "times": ["08:00", "11:00", "14:00", "17:00"],
                "title_i18n": {"en": f"Washroom cleaning, floor {label}", "kn": f"ಶೌಚಾಲಯ ಸ್ವಚ್ಛತೆ, ಮಹಡಿ {label}", "hi": f"शौचालय सफ़ाई, मंज़िल {label}"},
                "instructions_i18n": {"en": "Use the blue bucket for washrooms only.", "kn": "ಶೌಚಾಲಯಕ್ಕೆ ನೀಲಿ ಬಕೆಟ್ ಮಾತ್ರ ಬಳಸಿ.", "hi": "शौचालय के लिए केवल नीली बाल्टी इस्तेमाल करें।"},
                "checklist": CHECKLIST_WASHROOM, "due_minutes": 45,
                # only one floor carries the "too fast" rule, so the demo shows a few flags, not dozens
                "min_minutes": 6 if label == "3" else 0,
            })  # fmt: skip
            await sd.post(A, "/task-templates", {
                "desk_id": desk["id"], "schedule_kind": "daily", "times": ["09:30", "15:30"],
                "title_i18n": {"en": f"Corridor and common area, floor {label}", "kn": f"ಕಾರಿಡಾರ್, ಮಹಡಿ {label}", "hi": f"गलियारा, मंज़िल {label}"},
                "checklist": CHECKLIST_FLOOR, "due_minutes": 60, "min_minutes": 0,
            })  # fmt: skip

        await simulate_day(sd, worker_ids, sup)
        entrance = await sd.get(A, f"/branches/{main['id']}/entrance-qr")
        for uid in worker_ids[:5]:
            await sd.post(uid, "/attendance/scan", {"token": entrance["token"], "kind": "check_in"})

    print_block(h.id, admin_totp, md_totp, device["device_key"])
    await dispose_engines()


async def simulate_day(sd: Seeder, workers: list[uuid.UUID], sup: uuid.UUID) -> None:
    """Move earlier tasks through realistic states (done, awaiting approval, rework, overdue)."""
    now = datetime.now(UTC)
    for i, uid in enumerate(workers):
        mine = sorted(await sd.get(uid, "/me/tasks"), key=lambda t: t["due_at"])
        due_soon = [
            t for t in mine if datetime.fromisoformat(t["due_at"]) < now + timedelta(hours=1)
        ]
        # Early in the day nothing is due yet: still play out the first three tasks (finished
        # ahead of time) so a morning demo shows approvals, rework and flags.
        tasks = due_soon if len(due_soon) >= 3 else mine[:3]
        for j, t in enumerate(tasks):
            pattern = (i + j) % 5
            if pattern == 4:
                continue  # left open: becomes overdue
            await sd.post(uid, f"/tasks/{t['id']}/start")
            for phase, shade in (("before", (92, 74, 60)), ("after", (200, 214, 206))):
                await sd.c.post(f"/api/v1/tasks/{t['id']}/proofs", headers=sd.h(uid), data={"phase": phase},
                                files={"photo": ("p.jpg", demo_photo(f"{phase} {t['number']}", shade), "image/jpeg")})  # fmt: skip
            await sd.post(
                uid,
                f"/tasks/{t['id']}/submit",
                {"checklist": {i["key"]: True for i in t["checklist"]}},
            )
            if pattern in (0, 1):
                await sd.post(sup, f"/tasks/{t['id']}/approve", {})
            elif pattern == 2:
                await sd.post(
                    sup,
                    f"/tasks/{t['id']}/reject",
                    {"note": "Corner behind the door still wet. Please redo."},
                )
    await sd.get(sup, "/dashboard/today")  # runs the SLA sweep


def print_block(
    hid: uuid.UUID, admin_totp: str | None, md_totp: str | None, device_key: str | None
) -> None:
    print(f"""
Seeded demo hospital SUNRISE ({hid}). Synthetic data only.

  Web admin   http://localhost:5173      hospital code: SUNRISE
    Admin       admin@sunrise.example.org       password: {PASSWORD}   TOTP secret: {admin_totp}
    MD          md@sunrise.example.org          password: {PASSWORD}   TOTP secret: {md_totp}
    Supervisor  supervisor@sunrise.example.org  password: {PASSWORD}
  Staff app   http://localhost:5174
    Email code  hk-101@sunrise.example.org ... hk-106 (code is printed in the API console in dev)
    Shared phone PIN {PIN} with employee code HK-101 ... HK-106
    Device key  {device_key or "(already registered: register a new one under Devices)"}

  Add the TOTP secrets to any authenticator app, or run:
    uv run python -c "import pyotp;print(pyotp.TOTP('<secret>').now())"
""")


async def print_logins(hid: uuid.UUID) -> None:
    secrets_ = {}
    async with tenant_session(hid) as s:
        for email in ("admin@sunrise.example.org", "md@sunrise.example.org"):
            u = await s.scalar(select(User).where(User.email == email))
            cred = await s.get(Credential, u.id) if u else None
            secrets_[email] = (
                decrypt_field(cred.totp_secret_enc) if cred and cred.totp_secret_enc else None
            )
    print_block(
        hid, secrets_["admin@sunrise.example.org"], secrets_["md@sunrise.example.org"], None
    )
    await dispose_engines()


def reset_database() -> None:
    """Dev only: wipe every table by migrating down to base and back up (SEED_RESET=1)."""
    import subprocess

    for args in (["downgrade", "base"], ["upgrade", "head"]):
        subprocess.run([sys.executable, "-m", "alembic", *args], check=True)  # noqa: S603


if __name__ == "__main__":
    if os.environ.get("APP_ENV") == "production":
        sys.exit("Refusing to seed demo data in production.")
    if os.environ.get("SEED_RESET") == "1":
        reset_database()
    asyncio.run(seed())
