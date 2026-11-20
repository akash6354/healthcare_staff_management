"""Auth flows: email OTP, lockout, password + TOTP, PIN on a registered device, refresh rotation."""

import re

import pyotp

from app.core.db import tenant_session
from app.modules.auth.service import set_password
from app.modules.staff.models import Role, User
from app.notify.email import ConsoleEmailAdapter
from tests.conftest import Tenant, make_user


def _last_code() -> str:
    match = re.search(r"\b(\d{6})\b", ConsoleEmailAdapter.outbox[-1].body)
    assert match
    return match.group(1)


def _refresh_headers(client) -> dict[str, str]:
    return {"X-CSRF-Token": client.cookies.get("oglos_csrf", "")}


async def test_email_otp_login_and_me(client, hospital_a: Tenant) -> None:
    await make_user(hospital_a, Role.worker, email="worker1@sunrise.example.org")
    r = await client.post(
        "/api/v1/auth/otp/request",
        json={"hospital_code": hospital_a.code, "email": "worker1@sunrise.example.org"},
    )
    assert r.status_code == 202
    v = await client.post("/api/v1/auth/otp/verify", json={
        "hospital_code": hospital_a.code, "challenge_id": r.json()["challenge_id"], "code": _last_code(),
    })  # fmt: skip
    assert v.status_code == 200, v.text
    me = await client.get(
        "/api/v1/me", headers={"Authorization": f"Bearer {v.json()['access_token']}"}
    )
    assert me.json()["roles"][0]["role"] == "worker"
    assert "task.view" in me.json()["permissions"]


async def test_unknown_email_looks_identical(client, hospital_a: Tenant) -> None:
    before = len(ConsoleEmailAdapter.outbox)
    r = await client.post(
        "/api/v1/auth/otp/request",
        json={"hospital_code": hospital_a.code, "email": "nobody@nowhere.example.org"},
    )
    assert r.status_code == 202 and "challenge_id" in r.json()
    assert len(ConsoleEmailAdapter.outbox) == before  # nothing sent
    v = await client.post("/api/v1/auth/otp/verify", json={
        "hospital_code": hospital_a.code, "challenge_id": r.json()["challenge_id"], "code": "123456",
    })  # fmt: skip
    assert v.status_code == 401 and v.json()["error"]["code"] == "INVALID_CODE"


async def test_wrong_codes_lock_the_account(client, hospital_a: Tenant) -> None:
    await make_user(hospital_a, Role.worker, email="locky@sunrise.example.org")
    r = await client.post(
        "/api/v1/auth/otp/request",
        json={"hospital_code": hospital_a.code, "email": "locky@sunrise.example.org"},
    )
    cid = r.json()["challenge_id"]
    real = _last_code()
    wrong = "000000" if real != "000000" else "111111"
    for _ in range(5):
        v = await client.post(
            "/api/v1/auth/otp/verify",
            json={"hospital_code": hospital_a.code, "challenge_id": cid, "code": wrong},
        )
        assert v.status_code in (401, 423)
    v = await client.post(
        "/api/v1/auth/otp/verify",
        json={"hospital_code": hospital_a.code, "challenge_id": cid, "code": real},
    )
    assert v.status_code in (401, 423)  # challenge burnt and account locked


async def test_otp_send_is_rate_limited(client, hospital_a: Tenant) -> None:
    body = {"hospital_code": hospital_a.code, "email": "spam@sunrise.example.org"}
    codes = [
        (await client.post("/api/v1/auth/otp/request", json=body)).status_code for _ in range(4)
    ]
    assert codes[:3] == [202, 202, 202] and codes[3] == 429


async def test_admin_password_then_totp_enrolment(client, hospital_a: Tenant) -> None:
    admin = await make_user(hospital_a, Role.hospital_admin, email="admin@sunrise.example.org")
    async with tenant_session(hospital_a.id) as s:
        user = await s.get(User, admin.id)
        await set_password(s, user, "correct horse battery 42")
    body = {
        "hospital_code": hospital_a.code,
        "email": "admin@sunrise.example.org",
        "password": "correct horse battery 42",
    }

    first = await client.post("/api/v1/auth/password/login", json=body)
    assert first.status_code == 200 and first.json()["mfa_pending"] is True
    pending = {"Authorization": f"Bearer {first.json()['access_token']}"}
    assert (await client.get("/api/v1/users", headers=pending)).status_code == 403

    uri = (await client.post("/api/v1/auth/totp/enroll", headers=pending)).json()["otpauth_uri"]
    totp = pyotp.parse_uri(uri)
    confirmed = await client.post(
        "/api/v1/auth/totp/confirm", json={"code": totp.now()}, headers=pending
    )
    assert confirmed.status_code == 200 and len(confirmed.json()["recovery_codes"]) == 10
    full = {"Authorization": f"Bearer {confirmed.json()['access_token']}"}
    assert (await client.get("/api/v1/users", headers=full)).status_code == 200

    second = await client.post("/api/v1/auth/password/login", json=body)
    assert second.json()["totp_required"] is True and second.json()["access_token"] == ""
    bad = await client.post(
        "/api/v1/auth/totp/verify", json={"mfa_token": second.json()["mfa_token"], "code": "000000"}
    )
    assert bad.status_code == 401
    good = await client.post(
        "/api/v1/auth/totp/verify",
        json={"mfa_token": second.json()["mfa_token"], "code": totp.now()},
    )
    assert good.status_code == 200 and good.json()["mfa_pending"] is False


async def test_wrong_password_is_generic(client, hospital_a: Tenant) -> None:
    r = await client.post(
        "/api/v1/auth/password/login",
        json={
            "hospital_code": hospital_a.code,
            "email": "ghost@sunrise.example.org",
            "password": "whatever-long-1",
        },
    )
    assert r.status_code == 401 and r.json()["error"]["code"] == "INVALID_CREDENTIALS"


async def test_pin_login_needs_registered_device(client, hospital_a: Tenant) -> None:
    admin = await make_user(hospital_a)
    worker = await client.post("/api/v1/users", headers=admin.headers, json={
        "employee_code": "PIN-1", "display_name": "Pin Worker", "employment_type": "employee", "roles": [{"role": "worker"}],
    })  # fmt: skip
    assert (
        await client.put(
            f"/api/v1/users/{worker.json()['id']}/pin", json={"pin": "1111"}, headers=admin.headers
        )
    ).status_code == 422
    assert (
        await client.put(
            f"/api/v1/users/{worker.json()['id']}/pin", json={"pin": "4826"}, headers=admin.headers
        )
    ).status_code == 204
    device = (
        await client.post("/api/v1/devices", json={"label": "Ward 3 phone"}, headers=admin.headers)
    ).json()
    body = {
        "hospital_code": hospital_a.code,
        "device_key": device["device_key"],
        "employee_code": "PIN-1",
        "pin": "4826",
    }
    assert (await client.post("/api/v1/auth/pin/login", json=body)).status_code == 200
    assert (
        await client.post("/api/v1/auth/pin/login", json={**body, "device_key": "x" * 32})
    ).status_code == 401
    await client.post(f"/api/v1/devices/{device['id']}/revoke", headers=admin.headers)
    assert (await client.post("/api/v1/auth/pin/login", json=body)).status_code == 401


async def test_refresh_rotation_and_reuse_detection(client, hospital_a: Tenant) -> None:
    await make_user(hospital_a, Role.worker, email="rot@sunrise.example.org")
    r = await client.post(
        "/api/v1/auth/otp/request",
        json={"hospital_code": hospital_a.code, "email": "rot@sunrise.example.org"},
    )
    await client.post(
        "/api/v1/auth/otp/verify",
        json={
            "hospital_code": hospital_a.code,
            "challenge_id": r.json()["challenge_id"],
            "code": _last_code(),
        },
    )
    first_rt = client.cookies.get("oglos_rt")

    no_csrf = await client.post("/api/v1/auth/refresh")
    assert no_csrf.status_code == 403

    ok = await client.post("/api/v1/auth/refresh", headers=_refresh_headers(client))
    assert ok.status_code == 200
    assert client.cookies.get("oglos_rt") != first_rt

    # Replay the spent token: the whole session is revoked.
    client.cookies.set("oglos_rt", first_rt, path="/api/v1/auth")
    replay = await client.post("/api/v1/auth/refresh", headers=_refresh_headers(client))
    assert replay.status_code == 401
    me = await client.get(
        "/api/v1/me", headers={"Authorization": f"Bearer {ok.json()['access_token']}"}
    )
    assert me.status_code == 401


async def test_deactivation_kills_access_immediately(client, hospital_a: Tenant) -> None:
    admin = await make_user(hospital_a)
    worker = await make_user(hospital_a, Role.worker)
    assert (await client.get("/api/v1/me", headers=worker.headers)).status_code == 200
    assert (
        await client.post(f"/api/v1/users/{worker.id}/deactivate", headers=admin.headers)
    ).status_code == 204
    assert (await client.get("/api/v1/me", headers=worker.headers)).status_code == 401


async def test_logout_everywhere(client, hospital_a: Tenant) -> None:
    worker = await make_user(hospital_a, Role.worker)
    assert (
        await client.post("/api/v1/auth/sessions/revoke-all", headers=worker.headers)
    ).status_code == 204
    assert (await client.get("/api/v1/me", headers=worker.headers)).status_code == 401
