from __future__ import annotations

import logging
import os
import time

from m8flow_backend.db import session_scope
from m8flow_backend import workflow

LOGGER = logging.getLogger(__name__)


def poll_due_jobs(*, limit: int = 100, worker_id: str | None = None) -> int:
    worker = worker_id or os.environ.get("M8FLOW_SCHEDULER_WORKER_ID") or "celery"
    with session_scope() as session:
        return workflow.run_due(
            session,
            now_in_seconds=int(time.time()),
            limit=limit,
            worker_id=worker,
            tenant_id=None,
        )


def create_celery_app():
    from celery import Celery

    app = Celery("m8flow_backend")
    broker = os.environ.get("M8FLOW_CELERY_BROKER_URL") or os.environ.get(
        "SPIFFWORKFLOW_BACKEND_CELERY_BROKER_URL"
    ) or "redis://localhost:6379/0"
    app.conf.broker_url = broker
    app.conf.result_backend = broker
    app.conf.beat_schedule = {
        "m8flow-run-due": {
            "task": "m8flow_backend.scheduler.poll_due_task",
            "schedule": float(os.environ.get("M8FLOW_SCHEDULER_POLL_SECONDS") or 10),
        }
    }
    return app


celery_app = create_celery_app()


@celery_app.task(name="m8flow_backend.scheduler.poll_due_task")
def poll_due_task() -> int:
    return poll_due_jobs()
