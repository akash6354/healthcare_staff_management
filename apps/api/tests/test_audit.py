"""Audit log: every write is chained, the chain verifies, and rows can't be changed or deleted."""

import pytest
from sqlalchemy import select, text
from sqlalchemy.exc import DBAPIError

from app.audit.models import AuditEvent
from app.audit.service import compute_hash, hashed_fields, verify_chain
from app.core.db import tenant_session
from tests.conftest import AuthedUser


async def test_writes_are_audited_and_chain_verifies(client, admin_a: AuthedUser) -> None:
    h = admin_a.headers
    b = (
        await client.post("/api/v1/buildings", json={"name": "Main", "code": "AU1"}, headers=h)
    ).json()
    await client.patch(f"/api/v1/buildings/{b['id']}", json={"name": "Main block"}, headers=h)
    await client.delete(f"/api/v1/buildings/{b['id']}", headers=h)
    async with tenant_session(admin_a.hospital_id) as s:
        actions = [e.action for e in (await s.scalars(
            select(AuditEvent).where(AuditEvent.entity_id == b["id"]).order_by(AuditEvent.seq)
        )).all()]  # fmt: skip
        result = await verify_chain(s, admin_a.hospital_id)
    assert actions == ["building.created", "building.updated", "building.archived"]
    assert result.ok, result


async def test_tampering_is_detected(admin_a: AuthedUser) -> None:
    async with tenant_session(admin_a.hospital_id) as s:
        event = (await s.scalars(select(AuditEvent).order_by(AuditEvent.seq).limit(1))).one()
        fields = hashed_fields(event)
        assert compute_hash(event.prev_hash, fields) == bytes(event.hash)
        fields["payload"] = {"tampered": True}
        assert compute_hash(event.prev_hash, fields) != bytes(event.hash)


@pytest.mark.parametrize(
    "statement", ["UPDATE audit_events SET action = 'x'", "DELETE FROM audit_events"]
)
async def test_audit_rows_are_immutable(admin_a: AuthedUser, statement: str) -> None:
    with pytest.raises(DBAPIError):
        async with tenant_session(admin_a.hospital_id) as s:
            await s.execute(text(statement))


async def test_sequences_are_per_hospital(admin_a: AuthedUser, admin_b: AuthedUser) -> None:
    for user in (admin_a, admin_b):
        async with tenant_session(user.hospital_id) as s:
            first = (await s.scalars(select(AuditEvent).order_by(AuditEvent.seq).limit(1))).one()
            assert first.seq == 1 and first.action == "hospital.created"
