from __future__ import annotations

import logging
import os
from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from m8flow_backend import workflow
from m8flow_backend.auth import install_postgres_rls_hook
from m8flow_backend.config import celery_worker_state_db
from m8flow_backend.db import session_scope
from m8flow_backend.models.m8flow_tenant import M8flowTenantModel, TenantStatus
from m8flow_backend.scheduler.celery_tenant import TenantAwareCelery, install_celery_tenant_signals
from m8flow_backend.auth.tenant_context import reset_context_tenant_id, set_context_tenant_id

logger = logging.getLogger(__name__)


def _active_tenant_ids(session) -> list[str]:
    return list(
        session.scalars(
            select(M8flowTenantModel.id)
            .where(M8flowTenantModel.status == TenantStatus.ACTIVE)
            .order_by(M8flowTenantModel.id)
        ).all()
    )


def _failed_job_backoff() -> timedelta:
    return timedelta(seconds=float(os.environ.get("M8FLOW_SCHEDULER_FAILED_JOB_BACKOFF_SECONDS") or 300))


def _postpone_next_due_job(tenant_id: str, now: datetime) -> str | None:
    """Move the job ``run_due(limit=1)`` just failed on out of the due window.

    Core claims due, unlocked jobs by (run_at, id) and releases the lock of one
    that fails; the failed attempt itself is rolled back. Left as it is, the same
    job is claimed first again on every poll -- for a timer start, a new failing
    instance every tick -- and is never followed by the jobs due after it.
    """
    from m8flow_core.models.scheduler_job import SchedulerJobModel

    with session_scope() as session:
        job = session.scalars(
            select(SchedulerJobModel)
            .where(
                SchedulerJobModel.m8f_tenant_id == tenant_id,
                SchedulerJobModel.locked_by.is_(None),
                SchedulerJobModel.run_at <= now,
            )
            .order_by(SchedulerJobModel.run_at, SchedulerJobModel.id)
            .limit(1)
        ).first()
        if job is None:
            return None
        job.run_at = now + _failed_job_backoff()
        job.updated_at = now
        return job.job_key


def poll_due_jobs(*, limit: int = 100, worker_id: str | None = None) -> int:
    """Run due scheduler jobs per active tenant, one job per transaction.

    Beat has no HTTP tenant. Passing ``tenant_id=None`` into ``workflow.run_due``
    mixes tenants on SQLite and sees no rows under PostgreSQL RLS. Bind each
    active tenant into the ContextVar (so ``SET LOCAL`` matches request-time
    RLS) and pass that id into core.

    Core runs a batch in the caller's session and raises after it if any job
    failed, so a whole batch would roll back with its one failure. Running one
    job per session commits each success on its own; a failing job is logged and
    postponed (M8FLOW_SCHEDULER_FAILED_JOB_BACKOFF_SECONDS, default 300) so the
    jobs behind it still run. ``limit`` caps the jobs run or failed per poll.
    """
    worker = worker_id or os.environ.get("M8FLOW_SCHEDULER_WORKER_ID") or "celery"
    now = datetime.now(timezone.utc)
    with session_scope() as session:
        tenant_ids = _active_tenant_ids(session)

    processed = 0
    attempts = 0
    for tenant_id in tenant_ids:
        token = set_context_tenant_id(tenant_id)
        try:
            while attempts < limit:
                try:
                    with session_scope() as session:
                        done = workflow.run_due(
                            session, now=now, limit=1, worker_id=worker, tenant_id=tenant_id
                        )
                except Exception:
                    attempts += 1
                    job_key = _postpone_next_due_job(tenant_id, now)
                    logger.exception(
                        "Scheduler job %s failed for tenant %s; retrying in %ss",
                        job_key, tenant_id, int(_failed_job_backoff().total_seconds()),
                    )
                    if job_key is None:
                        break
                    continue
                if not done:
                    break
                attempts += done
                processed += done
        finally:
            reset_context_tenant_id(token)
    return processed


def create_celery_app():
    app = TenantAwareCelery("m8flow_backend")
    # Worker, Flower and the monitoring page may read this before (or without)
    # apply_m8flow_env_mapping(), so the documented M8FLOW_BACKEND_* names come first.
    broker = (
        os.environ.get("M8FLOW_BACKEND_CELERY_BROKER_URL")
        or os.environ.get("M8FLOW_CELERY_BROKER_URL")
        or os.environ.get("SPIFFWORKFLOW_BACKEND_CELERY_BROKER_URL")
        or "redis://localhost:6379/0"
    )
    app.conf.broker_url = broker
    app.conf.result_backend = os.environ.get("M8FLOW_BACKEND_CELERY_RESULT_BACKEND") or broker
    app.conf.beat_schedule = {
        "m8flow-run-due": {
            "task": "m8flow_backend.scheduler.poll_due_task",
            "schedule": float(os.environ.get("M8FLOW_SCHEDULER_POLL_SECONDS") or 10),
        }
    }
    # Set as config rather than --statedb so the worker reports it through inspect conf,
    # which is how the Celery page knows whether that worker's revokes survive a restart.
    if state_db := celery_worker_state_db():
        app.conf.worker_state_db = state_db
    install_celery_tenant_signals()
    from m8flow_backend.services.celery_monitoring_service import install_celery_worker_commands
    from m8flow_backend.services.celery_task_history_service import install_celery_task_history_signals

    install_celery_task_history_signals()
    install_celery_worker_commands()
    # The worker never runs create_app(); without this the tenant bound above
    # and in poll_due_jobs never becomes app.current_tenant under RLS.
    install_postgres_rls_hook()
    # Nor does it get create_app()'s core hooks (service-task registry, proxy API
    # key, authorization policy, ...): without them every service task a scheduled
    # job runs (timer starts, tasks after a timer) fails.
    from m8flow_backend.startup.engine_hooks import install_host_engine_hooks

    install_host_engine_hooks()
    return app


celery_app = create_celery_app()


@celery_app.task(name="m8flow_backend.scheduler.poll_due_task")
def poll_due_task() -> int:
    return poll_due_jobs()
