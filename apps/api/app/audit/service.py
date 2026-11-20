"""Append-only, hash-chained audit log (one chain per hospital).

hash = sha256(prev_hash || canonical_json(event without hash)). Inserts for one hospital are
serialised with a transaction-scoped advisory lock so `seq` has no gaps and the chain never forks.
"""

import hashlib
import json
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.audit.models import AuditEvent
from app.core.ids import uuid7

GENESIS = b"\x00" * 32


def canonical(fields: dict[str, Any]) -> bytes:
    return json.dumps(fields, sort_keys=True, separators=(",", ":"), default=str).encode()


def _ts(value: datetime) -> str:
    return value.astimezone(UTC).isoformat(timespec="microseconds")


def compute_hash(prev_hash: bytes, fields: dict[str, Any]) -> bytes:
    return hashlib.sha256(bytes(prev_hash) + canonical(fields)).digest()


def hashed_fields(e: AuditEvent) -> dict[str, Any]:
    return {
        "id": str(e.id),
        "hospital_id": str(e.hospital_id),
        "seq": e.seq,
        "actor_id": str(e.actor_id) if e.actor_id else None,
        "actor_role": e.actor_role,
        "entity_type": e.entity_type,
        "entity_id": str(e.entity_id) if e.entity_id else None,
        "task_id": str(e.task_id) if e.task_id else None,
        "action": e.action,
        "from_state": e.from_state,
        "to_state": e.to_state,
        "payload": e.payload,
        "server_ts": _ts(e.server_ts),
    }


@dataclass(frozen=True)
class Actor:
    user_id: uuid.UUID | None
    role: str  # e.g. "supervisor", "system", "platform_admin", "public"


SYSTEM = Actor(None, "system")


async def record(
    session: AsyncSession,
    *,
    hospital_id: uuid.UUID,
    actor: Actor,
    entity_type: str,
    action: str,
    entity_id: uuid.UUID | None = None,
    task_id: uuid.UUID | None = None,
    from_state: str | None = None,
    to_state: str | None = None,
    payload: dict[str, Any] | None = None,
) -> AuditEvent:
    """Write one audit event in the caller's transaction (so it commits or rolls back with the change)."""
    await session.execute(
        text("SELECT pg_advisory_xact_lock(hashtextextended(:h, 0))"), {"h": str(hospital_id)}
    )
    last = (
        await session.execute(
            select(AuditEvent.seq, AuditEvent.hash)
            .where(AuditEvent.hospital_id == hospital_id)
            .order_by(AuditEvent.seq.desc())
            .limit(1)
        )
    ).first()
    seq = (last.seq + 1) if last else 1
    prev_hash = bytes(last.hash) if last else GENESIS
    server_ts: datetime = (await session.execute(text("SELECT clock_timestamp()"))).scalar_one()

    event = AuditEvent(
        id=uuid7(),
        hospital_id=hospital_id,
        seq=seq,
        actor_id=actor.user_id,
        actor_role=actor.role,
        entity_type=entity_type,
        entity_id=entity_id,
        task_id=task_id,
        action=action,
        from_state=from_state,
        to_state=to_state,
        payload=payload or {},
        server_ts=server_ts,
        prev_hash=prev_hash,
    )
    event.hash = compute_hash(prev_hash, hashed_fields(event))
    session.add(event)
    await session.flush()
    return event


@dataclass(frozen=True)
class VerifyResult:
    ok: bool
    events: int
    first_bad_seq: int | None = None
    reason: str | None = None


async def verify_chain(session: AsyncSession, hospital_id: uuid.UUID) -> VerifyResult:
    prev = GENESIS
    expected_seq = 1
    count = 0
    stream = await session.stream_scalars(
        select(AuditEvent).where(AuditEvent.hospital_id == hospital_id).order_by(AuditEvent.seq)
    )
    async for e in stream:
        count += 1
        if e.seq != expected_seq:
            return VerifyResult(False, count, e.seq, "sequence gap")
        if bytes(e.prev_hash) != prev:
            return VerifyResult(False, count, e.seq, "prev_hash mismatch")
        if compute_hash(prev, hashed_fields(e)) != bytes(e.hash):
            return VerifyResult(False, count, e.seq, "hash mismatch")
        prev = bytes(e.hash)
        expected_seq += 1
    return VerifyResult(True, count)
