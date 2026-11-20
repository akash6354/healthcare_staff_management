"""Celery app. Beat only *ticks*; all timer state lives in PostgreSQL (docs/architecture.md section 5).

Phase 1 ships the scaffold and the nightly audit-chain verification. SLA sweeps, schedule
materialisation, notifications and retention purges arrive with Phase 2.
"""

import asyncio

from celery import Celery
from celery.schedules import crontab

from app.core.config import get_settings

celery_app = Celery("oglos", broker=get_settings().redis_url, backend=get_settings().redis_url)
celery_app.conf.update(
    timezone="Asia/Kolkata",
    enable_utc=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    task_default_queue="oglos",
    beat_schedule={
        "retention-nightly": {
            "task": "oglos.privacy.retention",
            "schedule": crontab(hour=2, minute=0),
        },
        "audit-verify-nightly": {
            "task": "oglos.audit.verify",
            "schedule": crontab(hour=3, minute=0),
        },
    },
)


@celery_app.task(name="oglos.audit.verify")  # type: ignore[misc]
def verify_audit_chains() -> int:
    from app.audit.verify import main

    return asyncio.run(main())


@celery_app.task(name="oglos.privacy.retention")  # type: ignore[misc]
def retention() -> dict[str, int]:
    from app.modules.privacy.retention import main

    return asyncio.run(main())
