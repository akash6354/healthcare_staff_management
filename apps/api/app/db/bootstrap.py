"""One-time database bootstrap for managed Postgres (Render), run before `alembic upgrade head`.

Locally and on AWS this is done by infra/postgres/init/01-roles.sh as the superuser. On a managed
database we only have the owner account, so this creates the same extensions and the two app roles
(NOLOGIN: the prototype connects as the owner; the roles exist so migration GRANTs succeed).
Safe to run on every start.

    uv run python -m app.db.bootstrap
"""

import asyncio
import sys

from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import create_async_engine

from app.core.config import get_settings

STATEMENTS = [
    "CREATE EXTENSION IF NOT EXISTS citext",
    "CREATE EXTENSION IF NOT EXISTS pgcrypto",
    """DO $$ BEGIN
         IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'oglos_app') THEN
           CREATE ROLE oglos_app NOLOGIN;
         END IF;
         IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'oglos_platform') THEN
           CREATE ROLE oglos_platform NOLOGIN;
         END IF;
       END $$""",
]


async def main() -> int:
    engine = create_async_engine(get_settings().migrations_database_url)
    try:
        async with engine.begin() as conn:
            for stmt in STATEMENTS:
                await conn.execute(text(stmt))
    except DBAPIError as exc:
        print(
            "bootstrap failed: the database user can't create roles or extensions.\n"
            "Use the Render private-service Postgres described in docs/deploy-render.md (fallback).\n"
            f"detail: {exc.orig}",
            file=sys.stderr,
        )
        return 1
    finally:
        await engine.dispose()
    print("bootstrap ok")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
