"""DPDP data-principal rights and retention (docs/compliance/data-inventory.md).

- export: everything OGLOS holds about one staff member, as JSON (photos listed, not embedded)
- erase: anonymise a person who has left, keeping audit ids so the hash chain and records stay valid
- retention: full photos deleted after `photo_full_days` (thumbnail + record kept);
  deactivated staff anonymised after `deactivated_staff_months`
"""

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import delete, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.audit.service import SYSTEM, Actor, record
from app.core.crypto import decrypt_field
from app.core.errors import AppError, not_found
from app.core.storage import delete_object
from app.modules.auth.models import AuthSession, Credential, OtpChallenge, RefreshToken
from app.modules.staff.models import RosterEntry, ShiftCheckin, User, UserRole, UserStatus
from app.modules.tasks.models import NoticeAcknowledgement, ProofPurge, Task, TaskProof
from app.modules.tasks.service import hospital_settings


def _iso(v: datetime | None) -> str | None:
    return v.isoformat() if v else None


async def export_user(db: AsyncSession, user_id: uuid.UUID, actor: Actor) -> dict[str, Any]:
    user = await db.get(User, user_id)
    if user is None:
        raise not_found("user")
    roles = (await db.scalars(select(UserRole).where(UserRole.user_id == user.id))).all()
    roster = (await db.scalars(select(RosterEntry).where(RosterEntry.user_id == user.id))).all()
    checkins = (await db.scalars(select(ShiftCheckin).where(ShiftCheckin.user_id == user.id))).all()
    tasks = (
        await db.scalars(
            select(Task).where(or_(Task.started_by == user.id, Task.submitted_by == user.id))
        )
    ).all()
    proofs = (await db.scalars(select(TaskProof).where(TaskProof.captured_by == user.id))).all()
    acks = (
        await db.scalars(
            select(NoticeAcknowledgement).where(NoticeAcknowledgement.user_id == user.id)
        )
    ).all()
    data = {
        "exported_at": datetime.now(UTC).isoformat(),
        "profile": {
            "id": str(user.id),
            "employee_code": user.employee_code,
            "display_name": user.display_name,
            "email": user.email,
            "phone": decrypt_field(user.phone_enc) if user.phone_enc else None,
            "emergency_contact": decrypt_field(user.emergency_contact_enc) if user.emergency_contact_enc else None,
            "preferred_language": user.preferred_language.value,
            "employment_type": user.employment_type.value,
            "joining_date": user.joining_date.isoformat() if user.joining_date else None,
            "status": user.status.value,
        },
        "roles": [{"role": r.role.value, "scope_type": r.scope_type.value} for r in roles],
        "roster": [{"work_date": r.work_date.isoformat(), "desk_id": str(r.desk_id) if r.desk_id else None} for r in roster],
        "attendance": [{"kind": c.kind, "method": c.method.value, "at": _iso(c.server_ts)} for c in checkins],
        "tasks": [
            {"number": t.number, "title": t.title_i18n.get("en"), "status": t.status.value,
             "started_at": _iso(t.started_at), "submitted_at": _iso(t.submitted_at)}
            for t in tasks
        ],
        "photos": [{"id": str(p.id), "task_id": str(p.task_id), "phase": p.phase.value, "at": _iso(p.server_received_at)} for p in proofs],
        "notice_acknowledgements": [{"notice_id": str(a.notice_id), "at": _iso(a.server_ts)} for a in acks],
    }  # fmt: skip
    await record(
        db, hospital_id=user.hospital_id, actor=actor, entity_type="user", entity_id=user.id,
        action="privacy.exported",
    )  # fmt: skip
    return data


async def erase_user(db: AsyncSession, user_id: uuid.UUID, actor: Actor) -> None:
    """Anonymise. Ids stay (audit chain, task history); names and contact details go."""
    user = await db.get(User, user_id, with_for_update=True)
    if user is None:
        raise not_found("user")
    if user.status == UserStatus.erased:
        return
    if user.status != UserStatus.deactivated:
        raise AppError("ERASE_REQUIRES_DEACTIVATION", 409)
    user.display_name = f"Staff #{user.employee_code}"
    user.email = None
    user.phone_enc = user.phone_hash = None
    user.emergency_contact_enc = None
    user.joining_date = None
    user.status = UserStatus.erased
    user.erased_at = datetime.now(UTC)
    await db.execute(
        update(Credential)
        .where(Credential.user_id == user.id)
        .values(password_hash=None, pin_hash=None, totp_secret_enc=None, recovery_code_hashes=[])
    )
    sessions = select(AuthSession.id).where(AuthSession.user_id == user.id)
    await db.execute(delete(RefreshToken).where(RefreshToken.session_id.in_(sessions)))
    await db.execute(
        update(AuthSession)
        .where(AuthSession.user_id == user.id, AuthSession.revoked_at.is_(None))
        .values(revoked_at=datetime.now(UTC), revoke_reason="erased")
    )
    await db.execute(delete(OtpChallenge).where(OtpChallenge.user_id == user.id))
    await db.flush()
    await record(
        db, hospital_id=user.hospital_id, actor=actor, entity_type="user", entity_id=user.id,
        action="privacy.erased", from_state="deactivated", to_state="erased",
    )  # fmt: skip


async def apply_retention(
    db: AsyncSession, hospital_id: uuid.UUID, now: datetime | None = None
) -> dict[str, int]:
    now = now or datetime.now(UTC)
    retention = (await hospital_settings(db, hospital_id)).retention
    cutoff = now - timedelta(days=retention.photo_full_days)
    purged = select(ProofPurge.proof_id)
    due = (
        await db.scalars(
            select(TaskProof)
            .where(TaskProof.server_received_at < cutoff, TaskProof.id.not_in(purged))
            .limit(500)
        )
    ).all()
    for proof in due:
        await delete_object(db, proof.object_key)
        db.add(ProofPurge(hospital_id=hospital_id, proof_id=proof.id))
    if due:
        await db.flush()
        await record(
            db, hospital_id=hospital_id, actor=SYSTEM, entity_type="task_proof", action="retention.photos_purged",
            payload={"count": len(due), "older_than_days": retention.photo_full_days},
        )  # fmt: skip

    staff_cutoff = now - timedelta(days=30 * retention.deactivated_staff_months)
    leavers = (
        await db.scalars(
            select(User.id).where(
                User.status == UserStatus.deactivated, User.deactivated_at < staff_cutoff
            )
        )
    ).all()
    for uid in leavers:
        await erase_user(db, uid, SYSTEM)
    return {"photos_purged": len(due), "staff_anonymised": len(leavers)}
