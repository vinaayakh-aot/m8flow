from __future__ import annotations

import json
from typing import Any

from jinja2 import Environment, BaseLoader
from sqlalchemy import select
from sqlalchemy.orm import Session

from m8flow_bpmn_core.models.human_task import HumanTaskModel
from m8flow_bpmn_core.models.process_instance_metadata import ProcessInstanceMetadataModel
from m8flow_backend.models.native import (
    ExternalFormRequestModel,
    TaskDraftDataModel,
    TaskInstructionsForEndUserModel,
    TypeaheadModel,
)
from m8flow_backend import workflow


def render_instructions(template: str, context: dict[str, Any] | None = None) -> str:
    env = Environment(loader=BaseLoader(), autoescape=True)
    return env.from_string(template).render(**(context or {}))


def form_schema_for_task(_task: HumanTaskModel) -> dict[str, Any]:
    return {"type": "object", "properties": {}}


def display_task(session: Session, *, tenant_id: str, human_task_id: int) -> dict[str, Any]:
    task = session.get(HumanTaskModel, human_task_id)
    if task is None:
        return {}
    metadata = session.scalars(
        select(ProcessInstanceMetadataModel).where(
            ProcessInstanceMetadataModel.process_instance_id == task.process_instance_id,
            ProcessInstanceMetadataModel.m8f_tenant_id == tenant_id,
        )
    ).all()
    return {
        "id": task.id,
        "task_title": task.task_title or task.task_name,
        "task_name": task.task_name,
        "status": task.task_status,
        "form_schema": form_schema_for_task(task),
        "metadata": {row.key: row.value for row in metadata},
    }


def save_draft(
    session: Session,
    *,
    tenant_id: str,
    process_instance_id: int,
    task_guid: str,
    saved_form_data: dict[str, Any],
) -> TaskDraftDataModel:
    row = session.scalars(
        select(TaskDraftDataModel).where(
            TaskDraftDataModel.process_instance_id == process_instance_id,
            TaskDraftDataModel.task_guid == task_guid,
            TaskDraftDataModel.m8f_tenant_id == tenant_id,
        )
    ).first()
    payload = json.dumps(saved_form_data)
    if row is None:
        row = TaskDraftDataModel(
            process_instance_id=process_instance_id,
            task_guid=task_guid,
            saved_form_data=payload,
            m8f_tenant_id=tenant_id,
        )
        session.add(row)
    else:
        row.saved_form_data = payload
    return row


def typeahead_lookup(session: Session, *, tenant_id: str, category: str, search_term: str) -> list[str]:
    rows = session.scalars(
        select(TypeaheadModel).where(
            TypeaheadModel.m8f_tenant_id == tenant_id,
            TypeaheadModel.category == category,
            TypeaheadModel.search_term.ilike(f"%{search_term}%"),
        )
    ).all()
    return [row.result for row in rows]


def store_end_user_instructions(
    session: Session, *, tenant_id: str, process_instance_id: int, instruction: str
) -> TaskInstructionsForEndUserModel:
    row = TaskInstructionsForEndUserModel(
        process_instance_id=process_instance_id,
        instruction=instruction,
        m8f_tenant_id=tenant_id,
    )
    session.add(row)
    return row


def notify_external_form_on_materialization(
    session: Session,
    *,
    tenant_id: str,
    process_instance_id: int,
    human_task_id: int,
    email: str | None,
) -> ExternalFormRequestModel | None:
    """Re-homed from ProcessInstanceProcessor.save onto Human Task materialization."""
    if not email:
        return None
    row = ExternalFormRequestModel(
        token=f"{process_instance_id}-{human_task_id}",
        process_instance_id=process_instance_id,
        human_task_id=human_task_id,
        email=email,
        m8f_tenant_id=tenant_id,
    )
    session.add(row)
    return row


def submit_external_form(
    session: Session,
    *,
    tenant_id: str,
    human_task_id: int,
    user_id: int,
    task_payload: dict[str, Any] | None,
) -> Any:
    workflow.claim(
        session,
        tenant_id=tenant_id,
        human_task_id=human_task_id,
        user_id=user_id,
    )
    return workflow.complete(
        session,
        tenant_id=tenant_id,
        human_task_id=human_task_id,
        user_id=user_id,
        task_payload=task_payload,
    )
