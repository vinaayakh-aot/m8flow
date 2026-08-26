"""Regression coverage for architecture review finding W1: ExternalFormService
was wired to models.native.ExternalFormRequestModel, a legacy definition
targeting the wrong (unmigrated, singular-named) table with a completely
different schema (token/human_task_id) than the real migrated table
(reference_id/task_guid/status/...). Any real usage raised AttributeError at
first touch of `.status`/`.task_guid`/etc; this file's own directory had zero
tests, so nothing caught it. models/external_form_request.py now defines the
model against the real table -- these tests exercise it end-to-end.

ExternalFormService reads/writes through `db.session` (m8flow_backend.db.db),
which resolves to `g.db_session` inside a request context -- so tests run
inside `app.test_request_context()` with `g.db_session` pinned to the shared
`db_session` fixture, the same way a real request would provide it.
"""

from __future__ import annotations

import pytest
from flask import g

from m8flow_backend.errors import ApiError
from m8flow_backend.models.external_form_request import ExternalFormRequestStatus
from m8flow_backend.services.external_form_service import ExternalFormService


@pytest.fixture(autouse=True)
def _bind_request_scoped_session(app, db_session):
    with app.test_request_context("/"):
        g.db_session = db_session
        yield


def test_create_requests_for_task_persists_with_the_real_schema(db_session):
    created = ExternalFormService.create_requests_for_task(
        tenant_id="t1",
        process_instance_id=123,
        task_guid="task-guid-1",
        external_form_url="https://forms.example/task-guid-1",
        recipients=[{"user_id": 1, "email": "a@example.com", "user_details": {"name": "A"}}],
    )
    assert len(created) == 1
    row = created[0]
    assert row.id is not None
    assert row.status == ExternalFormRequestStatus.pending.value
    assert row.is_actionable() is True
    assert row.attempts == 0


def test_create_requests_for_task_skips_recipients_with_an_actionable_link(db_session):
    first = ExternalFormService.create_requests_for_task(
        tenant_id="t1",
        process_instance_id=123,
        task_guid="task-guid-1",
        external_form_url="https://forms.example/task-guid-1",
        recipients=[{"user_id": 1, "email": "a@example.com"}],
    )
    second = ExternalFormService.create_requests_for_task(
        tenant_id="t1",
        process_instance_id=123,
        task_guid="task-guid-1",
        external_form_url="https://forms.example/task-guid-1",
        recipients=[{"user_id": 1, "email": "a@example.com"}],
    )
    assert len(first) == 1
    assert second == []


def test_get_form_context_reports_status_and_actionability(db_session):
    [row] = ExternalFormService.create_requests_for_task(
        tenant_id="t1",
        process_instance_id=123,
        task_guid="task-guid-1",
        external_form_url="https://forms.example/task-guid-1",
        recipients=[{"user_id": 1, "email": "a@example.com"}],
    )

    context = ExternalFormService.get_form_context(row.reference_id)

    assert context["reference_id"] == row.reference_id
    assert context["status"] == ExternalFormRequestStatus.pending.value
    assert context["actionable"] is True
    assert context["external_form_url"] == "https://forms.example/task-guid-1"
    # to_public_dict must not leak internal-only fields.
    assert "attempts" not in context
    assert "user_details" not in context
    assert "form_submission_data" not in context


def test_get_form_context_unknown_reference_id_is_404(db_session):
    with pytest.raises(ApiError) as excinfo:
        ExternalFormService.get_form_context("does-not-exist")
    assert excinfo.value.status_code == 404


def test_expired_request_reports_not_actionable(db_session):
    [row] = ExternalFormService.create_requests_for_task(
        tenant_id="t1",
        process_instance_id=123,
        task_guid="task-guid-1",
        external_form_url="https://forms.example/task-guid-1",
        recipients=[{"user_id": 1, "email": "a@example.com"}],
        expires_at_in_seconds=1,  # already in the past
    )

    context = ExternalFormService.get_form_context(row.reference_id)

    assert context["status"] == ExternalFormRequestStatus.expired.value
    assert context["actionable"] is False
