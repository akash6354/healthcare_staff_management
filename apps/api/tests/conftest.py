"""Test fixtures. Tests run against the real PostgreSQL (database `oglos_test`) so RLS is exercised.

Start the stack first: `make dev` (or `pwsh scripts/dev.ps1 dev`).
"""

import os
import re
import subprocess
import sys
import uuid
from collections.abc import AsyncIterator
from dataclasses import dataclass
from pathlib import Path

import pytest


def _load_dotenv() -> None:
    """Read the repo .env into os.environ (CI sets real env vars instead)."""
    env_file = Path(__file__).resolve().parents[3] / ".env"
    if not env_file.exists():
        return
    for line in env_file.read_text(encoding="utf-8").splitlines():
        if line.strip() and not line.lstrip().startswith("#") and "=" in line:
            key, _, value = line.partition("=")
            os.environ.setdefault(key.strip(), value.strip())


_load_dotenv()
_TEST_DB = os.environ.get("TEST_DATABASE_NAME", "oglos_test")
for _key in ("DATABASE_URL", "MIGRATIONS_DATABASE_URL", "PLATFORM_DATABASE_URL"):
    os.environ[_key] = re.sub(r"/[A-Za-z0-9_]+$", f"/{_TEST_DB}", os.environ[_key])
os.environ["APP_ENV"] = "test"
os.environ["EMAIL_PROVIDER"] = "console"
os.environ["BREACHED_PASSWORD_CHECK"] = "off"

import httpx  # noqa: E402
import pytest_asyncio  # noqa: E402

from app.core.db import tenant_session  # noqa: E402
from app.core.ratelimit import redis_client  # noqa: E402
from app.main import app  # noqa: E402
from app.modules.auth.service import _create_session  # noqa: E402
from app.modules.platform.service import create_hospital  # noqa: E402
from app.modules.staff.models import EmploymentType, Role, ScopeType, User, UserRole  # noqa: E402

API_DIR = Path(__file__).resolve().parents[1]


def _alembic(*args: str) -> None:
    env = {**os.environ, "OGLOS_MIGRATIONS_URL": os.environ["MIGRATIONS_DATABASE_URL"]}
    subprocess.run(  # noqa: S603
        [sys.executable, "-m", "alembic", *args], cwd=API_DIR, env=env, check=True,
        capture_output=True,
    )  # fmt: skip


@pytest.fixture(scope="session", autouse=True)
def migrated_db() -> None:
    _alembic("downgrade", "base")
    _alembic("upgrade", "head")


@pytest_asyncio.fixture(autouse=True)
async def _reset_rate_limits() -> AsyncIterator[None]:
    r = redis_client()
    keys = [k async for k in r.scan_iter("rl:*")]
    if keys:
        await r.delete(*keys)
    yield


@pytest_asyncio.fixture
async def client() -> AsyncIterator[httpx.AsyncClient]:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="https://test") as c:
        yield c


@dataclass(frozen=True)
class AuthedUser:
    id: uuid.UUID
    hospital_id: uuid.UUID
    token: str

    @property
    def headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.token}"}


@dataclass(frozen=True)
class Tenant:
    id: uuid.UUID
    code: str


_counter = iter(range(1, 10**9))


async def make_hospital(prefix: str = "T") -> Tenant:
    n = next(_counter)
    h = await create_hospital(
        code=f"{prefix}{n:04d}{uuid.uuid4().hex[:4]}"[:24],
        name=f"Test Hospital {n}",
        city="Bengaluru",
    )
    return Tenant(h.id, h.code)


async def make_user(
    tenant: Tenant,
    role: Role = Role.hospital_admin,
    *,
    scope_type: ScopeType = ScopeType.hospital,
    scope_id: uuid.UUID | None = None,
    email: str | None = None,
    department_id: uuid.UUID | None = None,
    mfa_pending: bool = False,
) -> AuthedUser:
    """Create a user with one role and a live session (skips the login flow; auth tests cover it)."""
    n = next(_counter)
    async with tenant_session(tenant.id) as s:
        user = User(
            hospital_id=tenant.id, employee_code=f"E{n:05d}", display_name=f"Test User {n}",
            email=email, employment_type=EmploymentType.employee, department_id=department_id,
        )  # fmt: skip
        s.add(user)
        await s.flush()
        s.add(
            UserRole(
                hospital_id=tenant.id,
                user_id=user.id,
                role=role,
                scope_type=scope_type,
                scope_id=scope_id,
            )
        )
        await s.flush()
        issued = await _create_session(s, user, amr=["test"], mfa_pending=mfa_pending)
    return AuthedUser(user.id, tenant.id, issued.access_token)


@pytest_asyncio.fixture
async def hospital_a() -> Tenant:
    return await make_hospital("A")


@pytest_asyncio.fixture
async def hospital_b() -> Tenant:
    return await make_hospital("B")


@pytest_asyncio.fixture
async def admin_a(hospital_a: Tenant) -> AuthedUser:
    return await make_user(hospital_a)


@pytest_asyncio.fixture
async def admin_b(hospital_b: Tenant) -> AuthedUser:
    return await make_user(hospital_b)
