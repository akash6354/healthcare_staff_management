"""Platform CLI for Oglos staff.

    uv run python -m app.modules.platform.cli create-hospital --code SUNRISE --name "..." --city Bengaluru \
        --admin-email admin@example.org --admin-name "Hospital Admin"

Prints a one-time temporary password for the first hospital admin, who must enrol TOTP at first sign-in.
"""

import argparse
import asyncio
import secrets

from app.core.db import dispose_engines, tenant_session
from app.modules.auth.service import set_password
from app.modules.platform.service import create_hospital
from app.modules.staff.models import EmploymentType, Role, ScopeType, User, UserRole


async def _create(args: argparse.Namespace) -> None:
    h = await create_hospital(code=args.code, name=args.name, city=args.city)
    temp = secrets.token_urlsafe(12)
    async with tenant_session(h.id) as s:
        admin = User(
            hospital_id=h.id, employee_code="ADMIN-001", display_name=args.admin_name,
            email=args.admin_email, employment_type=EmploymentType.employee,
        )  # fmt: skip
        s.add(admin)
        await s.flush()
        s.add(
            UserRole(
                hospital_id=h.id,
                user_id=admin.id,
                role=Role.hospital_admin,
                scope_type=ScopeType.hospital,
            )
        )
        await set_password(s, admin, temp)
    print(f"Created hospital {h.code} ({h.id}).")
    print(f"First admin temporary password (shown once): {temp}")
    await dispose_engines()


def main() -> None:
    parser = argparse.ArgumentParser(prog="oglos-platform")
    sub = parser.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("create-hospital")
    c.add_argument("--code", required=True)
    c.add_argument("--name", required=True)
    c.add_argument("--city", required=True)
    c.add_argument("--admin-email", required=True)
    c.add_argument("--admin-name", required=True)
    args = parser.parse_args()
    if args.cmd == "create-hospital":
        asyncio.run(_create(args))


if __name__ == "__main__":
    main()
