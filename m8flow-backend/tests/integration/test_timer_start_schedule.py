"""Timer start events are scheduled only while their model is published.

Core schedules a definition's timer start events on every import, and the
catalog imports on every BPMN save -- drafts included -- so before this a draft
started instances on its own and a deleted model kept doing so forever.
"""

from __future__ import annotations

import pytest
import sqlalchemy as sa

from .support import new_tenant_id, provision_member, tenant_session

pytestmark = pytest.mark.usefixtures("host_db")

MODEL = "schedules/heartbeat"

TIMER_START_BPMN = """<?xml version="1.0" encoding="UTF-8"?>
<bpmn:definitions xmlns:bpmn="http://www.omg.org/spec/BPMN/20100524/MODEL"
  xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" id="Definitions_heartbeat"
  targetNamespace="http://bpmn.io/schema/bpmn">
  <bpmn:process id="heartbeat" isExecutable="true">
    <bpmn:startEvent id="start_heartbeat">
      <bpmn:outgoing>flow_1</bpmn:outgoing>
      <bpmn:timerEventDefinition>
        <bpmn:timeCycle xsi:type="bpmn:tFormalExpression">"R/PT1H"</bpmn:timeCycle>
      </bpmn:timerEventDefinition>
    </bpmn:startEvent>
    <bpmn:scriptTask id="beat"><bpmn:incoming>flow_1</bpmn:incoming><bpmn:outgoing>flow_2</bpmn:outgoing>
      <bpmn:script>ok = True</bpmn:script></bpmn:scriptTask>
    <bpmn:endEvent id="end_heartbeat"><bpmn:incoming>flow_2</bpmn:incoming></bpmn:endEvent>
    <bpmn:sequenceFlow id="flow_1" sourceRef="start_heartbeat" targetRef="beat" />
    <bpmn:sequenceFlow id="flow_2" sourceRef="beat" targetRef="end_heartbeat" />
  </bpmn:process>
</bpmn:definitions>
"""


def _timer_start_jobs(session) -> list[str]:
    from m8flow_core.models.bpmn_process_definition import (
        PROCESS_MODEL_IDENTIFIER_PROPERTY_KEY,
        BpmnProcessDefinitionModel,
    )
    from m8flow_core.models.scheduler_job import SchedulerJobModel

    return list(
        session.scalars(
            sa.select(SchedulerJobModel.job_key)
            .join(
                BpmnProcessDefinitionModel,
                BpmnProcessDefinitionModel.id == SchedulerJobModel.bpmn_process_definition_id,
            )
            .where(
                SchedulerJobModel.job_type == "timer_start",
                BpmnProcessDefinitionModel.properties_json[PROCESS_MODEL_IDENTIFIER_PROPERTY_KEY].as_string()
                == MODEL,
            )
        ).all()
    )


def _set_status(tenant_id: str, user_id: int, status: str) -> None:
    from m8flow_backend import catalog, workflow

    with tenant_session(tenant_id) as session:
        catalog.update_process_model_metadata(
            tenant_id=tenant_id, process_model_identifier=MODEL, status=status
        )
        workflow.sync_timer_start_schedule(
            session, tenant_id=tenant_id, user_id=user_id, process_model_identifier=MODEL
        )


def test_timer_start_follows_publish_status_and_deletion():
    from m8flow_backend import catalog, workflow

    tenant_id = new_tenant_id("tstart")
    with tenant_session(tenant_id) as session:
        editor = provision_member(session, tenant_id=tenant_id, role="editor")
        catalog.add_process_model(
            {"id": MODEL, "display_name": "Heartbeat", "status": "draft",
             "primary_file_name": "heartbeat.bpmn"},
            tenant_id=tenant_id,
        )
        catalog.save(session, path=MODEL, xml=TIMER_START_BPMN, tenant_id=tenant_id,
                     user_id=editor.id, file_name="heartbeat.bpmn")
    with tenant_session(tenant_id) as session:
        assert _timer_start_jobs(session) == [], "saving a draft must not schedule it"

    _set_status(tenant_id, editor.id, "published")
    with tenant_session(tenant_id) as session:
        assert len(_timer_start_jobs(session)) == 1, "publishing schedules the timer start"

    # Saving a new version while published keeps exactly one schedule (the new one).
    with tenant_session(tenant_id) as session:
        catalog.save(session, path=MODEL, xml=TIMER_START_BPMN.replace("R/PT1H", "R/PT2H"),
                     tenant_id=tenant_id, user_id=editor.id, file_name="heartbeat.bpmn")
    with tenant_session(tenant_id) as session:
        assert len(_timer_start_jobs(session)) == 1

    _set_status(tenant_id, editor.id, "draft")
    with tenant_session(tenant_id) as session:
        assert _timer_start_jobs(session) == [], "unpublishing removes the schedule"

    _set_status(tenant_id, editor.id, "published")
    with tenant_session(tenant_id) as session:
        assert len(_timer_start_jobs(session)) == 1
        workflow.sync_timer_start_schedule(
            session, tenant_id=tenant_id, user_id=editor.id, process_model_identifier=MODEL,
            removing=True,
        )
    with tenant_session(tenant_id) as session:
        assert _timer_start_jobs(session) == [], "deleting the model removes the schedule"
