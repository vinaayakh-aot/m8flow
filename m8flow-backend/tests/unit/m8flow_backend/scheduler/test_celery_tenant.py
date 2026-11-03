from __future__ import annotations

import subprocess
import sys
import os
from pathlib import Path
from types import SimpleNamespace

from celery import Celery

from m8flow_backend.identity import ensure_tenant
from m8flow_backend.models.m8flow_tenant import TenantStatus
from m8flow_backend.scheduler import poll_due_jobs
from m8flow_backend.scheduler.celery_tenant import (
    TenantAwareCelery,
    bind_celery_task_tenant,
    clear_celery_task_tenant,
)
from m8flow_backend.auth.tenant_context import (
    TENANT_SELECTION_HEADER_NAME,
    get_context_tenant_id,
    reset_context_tenant_id,
    set_context_tenant_id,
)


def test_send_task_injects_header_from_context(monkeypatch):
    captured: dict[str, object] = {}

    def fake_send(self, name, args=None, kwargs=None, **options):
        captured["name"] = name
        captured["headers"] = options.get("headers")
        return "ok"

    monkeypatch.setattr(Celery, "send_task", fake_send)
    app = TenantAwareCelery("m8flow-test")
    token = set_context_tenant_id("tenant-a")
    try:
        result = app.send_task("demo.task")
    finally:
        reset_context_tenant_id(token)

    assert result == "ok"
    assert captured["name"] == "demo.task"
    assert captured["headers"][TENANT_SELECTION_HEADER_NAME] == "tenant-a"


def test_send_task_skips_header_when_tenant_missing(monkeypatch):
    captured: dict[str, object] = {}

    def fake_send(self, name, args=None, kwargs=None, **options):
        captured["headers"] = options.get("headers")
        return "ok"

    monkeypatch.setattr(Celery, "send_task", fake_send)
    app = TenantAwareCelery("m8flow-test")
    app.send_task("demo.task")
    assert captured["headers"] is None


def test_send_task_does_not_overwrite_existing_header(monkeypatch):
    captured: dict[str, object] = {}

    def fake_send(self, name, args=None, kwargs=None, **options):
        captured["headers"] = options.get("headers")
        return "ok"

    monkeypatch.setattr(Celery, "send_task", fake_send)
    app = TenantAwareCelery("m8flow-test")
    token = set_context_tenant_id("from-context")
    try:
        app.send_task("demo.task", headers={TENANT_SELECTION_HEADER_NAME: "already"})
    finally:
        reset_context_tenant_id(token)

    assert captured["headers"][TENANT_SELECTION_HEADER_NAME] == "already"


def test_prerun_restores_context_from_header_and_postrun_clears():
    task = SimpleNamespace(
        request=SimpleNamespace(headers={TENANT_SELECTION_HEADER_NAME: "t9"})
    )
    bind_celery_task_tenant(task_id="abc", task=task)
    try:
        assert get_context_tenant_id() == "t9"
    finally:
        clear_celery_task_tenant(task_id="abc")
    assert get_context_tenant_id() is None


def test_prerun_ignores_task_without_tenant_header():
    task = SimpleNamespace(request=SimpleNamespace(headers={}))
    bind_celery_task_tenant(task_id="none", task=task)
    try:
        assert get_context_tenant_id() is None
    finally:
        clear_celery_task_tenant(task_id="none")


def test_poll_due_jobs_runs_per_active_tenant_never_none(monkeypatch, db_session):
    ensure_tenant(db_session, tenant_id="t-b", slug="t-b")
    ensure_tenant(db_session, tenant_id="t-a", slug="t-a")
    inactive = ensure_tenant(db_session, tenant_id="t-dead", slug="t-dead")
    inactive.status = TenantStatus.INACTIVE
    db_session.commit()

    calls: list[tuple[str | None, str | None]] = []

    def fake_run_due(session, **kwargs):
        calls.append((kwargs.get("tenant_id"), get_context_tenant_id()))
        return 0

    monkeypatch.setattr("m8flow_backend.workflow.run_due", fake_run_due)
    processed = poll_due_jobs(limit=100, worker_id="test-worker")

    assert processed == 0
    assert calls == [("t-a", "t-a"), ("t-b", "t-b")]
    assert all(tenant_id is not None for tenant_id, _ in calls)


def test_poll_due_jobs_with_no_tenants_does_not_call_run_due(monkeypatch, db_session):
    called = []

    def fake_run_due(session, **kwargs):
        called.append(kwargs)
        return 1

    monkeypatch.setattr("m8flow_backend.workflow.run_due", fake_run_due)
    assert poll_due_jobs() == 0
    assert called == []


def test_poll_due_jobs_shares_the_attempt_budget_across_tenants(monkeypatch, db_session):
    ensure_tenant(db_session, tenant_id="t1", slug="t1")
    ensure_tenant(db_session, tenant_id="t2", slug="t2")
    ensure_tenant(db_session, tenant_id="t3", slug="t3")
    db_session.commit()

    due = {"t1": 80, "t2": 30, "t3": 5}
    calls: list[tuple[str, int]] = []

    def fake_run_due(session, **kwargs):
        tenant_id = kwargs["tenant_id"]
        calls.append((tenant_id, kwargs["limit"]))
        if due[tenant_id] == 0:
            return 0
        due[tenant_id] -= 1
        return 1

    monkeypatch.setattr("m8flow_backend.workflow.run_due", fake_run_due)
    assert poll_due_jobs(limit=100, worker_id="test-worker") == 100
    # One job per transaction, so one failure never rolls back another job.
    assert {limit for _, limit in calls} == {1}
    # t1 runs all 80 of its jobs, t2 the 20 left in the budget, t3 none.
    assert due == {"t1": 0, "t2": 10, "t3": 5}
    assert all(tenant != "t3" for tenant, _ in calls)


def _scheduler_job(session, *, tenant_id: str, job_key: str, run_at):
    from m8flow_core.models.scheduler_job import SchedulerJobModel

    job = SchedulerJobModel(
        m8f_tenant_id=tenant_id, job_key=job_key, job_type="intermediate_timer", run_at=run_at,
        payload_json={}, created_at=run_at, updated_at=run_at,
    )
    session.add(job)
    return job


def test_failing_job_is_postponed_and_the_jobs_behind_it_still_run(monkeypatch, db_session):
    """Core raises after a batch if any job failed; the host must not let one bad job
    roll back or starve the others, nor retry it on every tick."""
    from datetime import datetime, timedelta, timezone

    from m8flow_core.models.scheduler_job import SchedulerJobModel

    ensure_tenant(db_session, tenant_id="t-fail", slug="t-fail")
    past = datetime.now(timezone.utc) - timedelta(minutes=5)
    _scheduler_job(db_session, tenant_id="t-fail", job_key="bad", run_at=past)
    _scheduler_job(db_session, tenant_id="t-fail", job_key="good", run_at=past + timedelta(seconds=1))
    db_session.commit()

    outcomes = iter([RuntimeError("service task failed"), 1, 0])

    def fake_run_due(session, **kwargs):
        outcome = next(outcomes)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome

    monkeypatch.setenv("M8FLOW_SCHEDULER_FAILED_JOB_BACKOFF_SECONDS", "600")
    monkeypatch.setattr("m8flow_backend.workflow.run_due", fake_run_due)
    before = datetime.now(timezone.utc)
    assert poll_due_jobs(limit=10, worker_id="test-worker") == 1

    db_session.expire_all()
    jobs = {j.job_key: j for j in db_session.query(SchedulerJobModel).filter_by(m8f_tenant_id="t-fail")}

    def aware(value):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)

    assert aware(jobs["bad"].run_at) >= before + timedelta(seconds=590)
    assert aware(jobs["good"].run_at) == aware(past + timedelta(seconds=1))


def test_worker_process_installs_the_host_engine_hooks():
    """The worker never calls ``create_app()``. Without the host's core hooks every
    service task a scheduled job runs fails: empty registry, no proxy API key."""
    probe = (
        "import m8flow_backend.scheduler\n"
        "from m8flow_core.services import authorization, connector_proxy_service_tasks, service_tasks\n"
        "from m8flow_backend.authorization import HostAuthorizationPolicy\n"
        "from m8flow_backend.secrets import build_host_service_task_registry\n"
        "assert service_tasks._DEFAULT_SERVICE_TASK_REGISTRY_FACTORY is build_host_service_task_registry\n"
        "assert authorization._DEFAULT_POLICY_FACTORY is HostAuthorizationPolicy\n"
        "assert connector_proxy_service_tasks._connector_proxy_json_request.__name__ == '_with_api_key'\n"
    )
    env = os.environ.copy()
    env["PYTHONPATH"] = str(Path(__file__).resolve().parents[4] / "src")
    env["M8FLOW_CONNECTOR_PROXY_API_KEY"] = "test-key"
    subprocess.run([sys.executable, "-c", probe], check=True, env=env)


def test_worker_process_installs_postgres_rls_hook():
    """The Celery worker never calls ``create_app()``. Without the after_begin
    hook, the tenant ``poll_due_jobs`` and task headers bind never becomes
    ``app.current_tenant``, so RLS hides every tenant row from the worker and
    rejects its writes. A fresh interpreter, because this test process already
    registered the hook through ``create_app()``."""
    probe = (
        "import m8flow_backend.scheduler\n"
        "from sqlalchemy import event\n"
        "from sqlalchemy.orm import Session\n"
        "from m8flow_backend.auth.bind import _on_session_after_begin\n"
        "assert event.contains(Session, 'after_begin', _on_session_after_begin)\n"
    )
    env = os.environ.copy()
    env["PYTHONPATH"] = str(Path(__file__).resolve().parents[4] / "src")
    subprocess.run([sys.executable, "-c", probe], check=True, env=env)


def test_worker_state_db_reaches_the_celery_config(monkeypatch):
    """Set as config, not --statedb, so the worker reports it through inspect conf."""
    from m8flow_backend.scheduler import create_celery_app

    monkeypatch.delenv("M8FLOW_BACKEND_CELERY_WORKER_STATE_DB", raising=False)
    assert create_celery_app().conf.worker_state_db is None
    monkeypatch.setenv("M8FLOW_BACKEND_CELERY_WORKER_STATE_DB", "/var/lib/m8flow/celery/worker.state")
    app = create_celery_app()
    assert app.conf.worker_state_db == "/var/lib/m8flow/celery/worker.state"
    assert app.conf.table(with_defaults=False)["worker_state_db"] == "/var/lib/m8flow/celery/worker.state"
