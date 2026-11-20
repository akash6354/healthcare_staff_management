"""Database engines and tenant-scoped sessions.

Every tenant query runs inside a transaction that first calls
`set_config('app.hospital_id', <id>, true)` (equivalent to SET LOCAL). PostgreSQL RLS policies
read that setting; without it, tenant tables return zero rows (deny by default).
"""

import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from functools import lru_cache

from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import get_settings
from app.core.logging import hospital_id_var


@lru_cache
def app_engine() -> AsyncEngine:
    return create_async_engine(get_settings().database_url, pool_pre_ping=True, pool_size=10)


@lru_cache
def platform_engine() -> AsyncEngine:
    """BYPASSRLS role. Only app.modules.platform and the seed script may use it."""
    return create_async_engine(
        get_settings().platform_database_url, pool_pre_ping=True, pool_size=2
    )


@lru_cache
def _app_sessionmaker() -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(app_engine(), expire_on_commit=False)


@lru_cache
def _platform_sessionmaker() -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(platform_engine(), expire_on_commit=False)


async def set_tenant(
    session: AsyncSession, hospital_id: uuid.UUID, user_id: uuid.UUID | None = None
) -> None:
    """Bind the current transaction to one hospital (and optionally a user) for RLS."""
    await session.execute(
        text("SELECT set_config('app.hospital_id', :h, true)"), {"h": str(hospital_id)}
    )
    await session.execute(
        text("SELECT set_config('app.user_id', :u, true)"), {"u": str(user_id) if user_id else ""}
    )
    hospital_id_var.set(str(hospital_id))


@asynccontextmanager
async def tenant_session(
    hospital_id: uuid.UUID, user_id: uuid.UUID | None = None
) -> AsyncIterator[AsyncSession]:
    """One transaction scoped to one hospital. Commits on success, rolls back on error."""
    async with _app_sessionmaker()() as session, session.begin():
        await set_tenant(session, hospital_id, user_id)
        yield session


@asynccontextmanager
async def anonymous_session() -> AsyncIterator[AsyncSession]:
    """A transaction with no tenant bound: tenant tables are invisible until set_tenant() is called."""
    async with _app_sessionmaker()() as session, session.begin():
        yield session


@asynccontextmanager
async def platform_session() -> AsyncIterator[AsyncSession]:
    async with _platform_sessionmaker()() as session, session.begin():
        yield session


async def resolve_hospital_code(session: AsyncSession, code: str) -> uuid.UUID | None:
    """Look up an active hospital id by its public code (SECURITY DEFINER function, id only)."""
    result = await session.execute(text("SELECT resolve_hospital_code(:c)"), {"c": code})
    value = result.scalar_one_or_none()
    return uuid.UUID(str(value)) if value else None


async def dispose_engines() -> None:
    for factory in (app_engine, platform_engine):
        if factory.cache_info().currsize:
            await factory().dispose()
