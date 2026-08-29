from __future__ import annotations

from m8flow_backend import workflow

TENANT = "tenant-a"
PI_ID = 700


def _user(session, *, uid, username, display_name=None):
    from m8flow_bpmn_core.models.user import UserModel

    session.add(
        UserModel(
            id=uid,
            username=username,
            display_name=display_name,
            service="https://example.test/realms/m8flow",
            service_id=f"svc-{uid}",
        )
    )
    session.flush()


def _human_task(
    session,
    *,
    task_name,
    status,
    completed,
    created_at,
    actual_owner_id=None,
    completed_by_user_id=None,
    lane_name=None,
    updated_at=None,
):
    from m8flow_bpmn_core.models.human_task import HumanTaskModel

    ht = HumanTaskModel(
        m8f_tenant_id=TENANT,
        process_instance_id=PI_ID,
        task_name=task_name,
        task_title=task_name,
        task_type="UserTask",
        task_status=status,
        process_model_display_name="Approval",
        bpmn_process_identifier="finance/approval",
        completed=completed,
        actual_owner_id=actual_owner_id,
        completed_by_user_id=completed_by_user_id,
        lane_name=lane_name,
        created_at_in_seconds=created_at,
        updated_at_in_seconds=updated_at,
    )
    session.add(ht)
    session.flush()
    return ht


def test_approval_chain_ordering_names_and_null_completer(db_session):
    _user(db_session, uid=1, username="priya", display_name="Priya Nair")
    _user(db_session, uid=2, username="manager", display_name=None)

    # Out of insert order to prove ordering is by created_at, then id.
    _human_task(
        db_session,
        task_name="manager_review",
        status="READY",
        completed=False,
        created_at=2000,
        actual_owner_id=2,
        lane_name="Manager",
    )
    _human_task(
        db_session,
        task_name="submit_claim",
        status="COMPLETED",
        completed=True,
        created_at=1000,
        completed_by_user_id=1,
        actual_owner_id=1,
        updated_at=1500,
    )
    # System-inactivated task: completed but no human owner/completer.
    _human_task(
        db_session,
        task_name="auto_step",
        status="COMPLETED",
        completed=True,
        created_at=1800,
        updated_at=1850,
    )

    chain = workflow.list_human_tasks_for_instance(
        db_session, tenant_id=TENANT, process_instance_id=PI_ID
    )
    assert [row["status"] for row in chain] == ["COMPLETED", "COMPLETED", "READY"]
    # First: completer/owner display name resolved.
    assert chain[0] == {
        "name": "Priya Nair",
        "status": "COMPLETED",
        "completed": True,
        "is_current": False,
        "lane_name": None,
        "completed_at_in_seconds": 1500,
    }
    # Second: system-completed -> name None, completed_at from updated_at.
    assert chain[1]["name"] is None
    assert chain[1]["completed"] is True
    assert chain[1]["completed_at_in_seconds"] == 1850
    # Third: current task -> username fallback (no display_name), no completed_at.
    assert chain[2] == {
        "name": "manager",
        "status": "READY",
        "completed": False,
        "is_current": True,
        "lane_name": "Manager",
        "completed_at_in_seconds": None,
    }


def test_approval_chain_is_tenant_scoped(db_session):
    _user(db_session, uid=1, username="priya", display_name="Priya Nair")
    _human_task(
        db_session,
        task_name="mine",
        status="READY",
        completed=False,
        created_at=1000,
        actual_owner_id=1,
    )
    # Same instance id, different tenant -> must not leak.
    from m8flow_bpmn_core.models.human_task import HumanTaskModel

    db_session.add(
        HumanTaskModel(
            m8f_tenant_id="other-tenant",
            process_instance_id=PI_ID,
            task_name="theirs",
            task_type="UserTask",
            task_status="READY",
            process_model_display_name="X",
            bpmn_process_identifier="x",
            completed=False,
            created_at_in_seconds=1000,
        )
    )
    db_session.flush()
    chain = workflow.list_human_tasks_for_instance(
        db_session, tenant_id=TENANT, process_instance_id=PI_ID
    )
    assert [row["name"] for row in chain] == ["Priya Nair"]


def _event(session, *, event_type, timestamp, user_id=None, task_guid=None):
    from m8flow_bpmn_core.models.process_instance_event import ProcessInstanceEventModel

    session.add(
        ProcessInstanceEventModel(
            m8f_tenant_id=TENANT,
            process_instance_id=PI_ID,
            event_type=event_type,
            timestamp=timestamp,
            user_id=user_id,
            task_guid=task_guid,
        )
    )
    session.flush()


def test_activity_events_ordering_actor_and_task_title(db_session):
    _user(db_session, uid=1, username="priya", display_name="Priya Nair")
    # A human task whose task_guid matches an event -> supplies task_title.
    _human_task(
        db_session,
        task_name="submit_claim",
        status="COMPLETED",
        completed=True,
        created_at=1000,
        completed_by_user_id=1,
        updated_at=1100,
    )
    from m8flow_bpmn_core.models.human_task import HumanTaskModel

    ht = db_session.query(HumanTaskModel).filter_by(task_name="submit_claim").first()
    ht.task_guid = "task-guid-1"
    ht.task_title = "Submit Expense Claim"
    db_session.flush()

    # System event (no user), then a user+task event; insert reversed.
    _event(db_session, event_type="task_completed", timestamp=1756000200.5, user_id=1, task_guid="task-guid-1")
    _event(db_session, event_type="process_instance_created", timestamp=1756000100.0)

    events = workflow.list_instance_events(
        db_session, tenant_id=TENANT, process_instance_id=PI_ID
    )
    assert events == [
        {
            "event_type": "process_instance_created",
            "actor_name": None,
            "timestamp": 1756000100.0,
            "task_guid": None,
            "task_title": None,
        },
        {
            "event_type": "task_completed",
            "actor_name": "Priya Nair",
            "timestamp": 1756000200.5,
            "task_guid": "task-guid-1",
            "task_title": "Submit Expense Claim",
        },
    ]


def test_activity_events_tenant_scoped(db_session):
    _event(db_session, event_type="process_instance_created", timestamp=1.0)
    from m8flow_bpmn_core.models.process_instance_event import ProcessInstanceEventModel

    db_session.add(
        ProcessInstanceEventModel(
            m8f_tenant_id="other-tenant",
            process_instance_id=PI_ID,
            event_type="process_instance_completed",
            timestamp=2.0,
        )
    )
    db_session.flush()
    events = workflow.list_instance_events(
        db_session, tenant_id=TENANT, process_instance_id=PI_ID
    )
    assert [e["event_type"] for e in events] == ["process_instance_created"]
