from __future__ import annotations

import time
import uuid

from m8flow_backend.auth import encode_auth_token
from m8flow_backend.identity import ensure_membership, ensure_tenant, ensure_user, sync_groups
from m8flow_backend.tenancy import SELECTED_TENANT_COOKIE_NAME


def _login_user(
    client, db_session, *, username: str, groups: list[str], tenant_id: str, v1_role: str = "user"
):
    from m8flow_bpmn_core.services.authorization import ensure_v1_role

    ensure_tenant(db_session, tenant_id=tenant_id, slug=tenant_id)
    user = ensure_user(
        db_session,
        username=username,
        service="https://example.test/realms/m8flow",
        service_id=username,
    )
    ensure_membership(db_session, user, ensure_tenant(db_session, tenant_id=tenant_id, slug=tenant_id))
    sync_groups(db_session, user=user, group_identifiers=groups, tenant_id=tenant_id)
    ensure_v1_role(db_session, tenant_id=tenant_id, role_name=v1_role, user_ids=(user.id,))
    db_session.commit()
    token = encode_auth_token(user=user)
    client.set_cookie(SELECTED_TENANT_COOKIE_NAME, tenant_id)
    return user, token


def _seed_instance(
    db_session,
    *,
    tenant_id: str,
    initiator_id: int,
    process_model_identifier: str,
    start: int | None,
    status: str = "complete",
    bpmn_process_definition_id: int | None = None,
):
    from m8flow_bpmn_core.models.process_instance import ProcessInstanceModel

    now = int(time.time())
    terminal = status in {"complete", "error", "terminated"}
    instance = ProcessInstanceModel(
        m8f_tenant_id=tenant_id,
        process_model_identifier=process_model_identifier,
        process_model_display_name=process_model_identifier.split("/")[-1],
        process_initiator_id=initiator_id,
        bpmn_process_definition_id=bpmn_process_definition_id,
        status=status,
        start_in_seconds=start,
        end_in_seconds=start + 60 if start is not None and terminal else None,
        created_at_in_seconds=now,
        updated_at_in_seconds=now,
    )
    db_session.add(instance)
    db_session.flush()
    return instance


def _seed_definition_with_tasks(
    db_session,
    *,
    tenant_id: str,
    process_instance,
    bpmn_xml: str = "<definitions/>",
    task_states: dict[str, str] | None = None,
):
    """Seeds a BpmnProcessDefinition (source_bpmn_xml) + BpmnProcess +
    TaskDefinition/Task rows for the given instance, wires
    process_instance.bpmn_process_definition_id, and returns the
    definition. `task_states` maps bpmn_identifier -> TaskModel.state.
    """
    from m8flow_bpmn_core.models.bpmn_process import BpmnProcessModel
    from m8flow_bpmn_core.models.bpmn_process_definition import (
        SOURCE_BPMN_XML_PROPERTY_KEY,
        BpmnProcessDefinitionModel,
    )
    from m8flow_bpmn_core.models.task import TaskModel
    from m8flow_bpmn_core.models.task_definition import TaskDefinitionModel

    definition = BpmnProcessDefinitionModel(
        m8f_tenant_id=tenant_id,
        single_process_hash=uuid.uuid4().hex,
        bpmn_identifier="Process_1",
        properties_json={SOURCE_BPMN_XML_PROPERTY_KEY: bpmn_xml},
    )
    db_session.add(definition)
    db_session.flush()

    process_instance.bpmn_process_definition_id = definition.id
    db_session.flush()

    bpmn_process = BpmnProcessModel(
        m8f_tenant_id=tenant_id,
        bpmn_process_definition_id=definition.id,
        properties_json={},
        json_data_hash=uuid.uuid4().hex,
    )
    db_session.add(bpmn_process)
    db_session.flush()

    for bpmn_identifier, state in (task_states or {}).items():
        task_definition = TaskDefinitionModel(
            m8f_tenant_id=tenant_id,
            bpmn_process_definition_id=definition.id,
            bpmn_identifier=bpmn_identifier,
            typename="Task",
            properties_json={},
        )
        db_session.add(task_definition)
        db_session.flush()

        task = TaskModel(
            m8f_tenant_id=tenant_id,
            guid=str(uuid.uuid4()),
            bpmn_process_id=bpmn_process.id,
            process_instance_id=process_instance.id,
            task_definition_id=task_definition.id,
            state=state,
            properties_json={},
            json_data_hash=uuid.uuid4().hex,
            python_env_data_hash=uuid.uuid4().hex,
        )
        db_session.add(task)
    db_session.flush()
    return definition


def test_editor_lists_instances_with_pagination(client, db_session):
    user, token = _login_user(
        client, db_session, username="editor", groups=["t1:editor"], tenant_id="t1"
    )
    now = int(time.time())
    _seed_instance(
        db_session,
        tenant_id="t1",
        initiator_id=user.id,
        process_model_identifier="finance/invoice-approval",
        start=now - 60,
        status="complete",
    )
    _seed_instance(
        db_session,
        tenant_id="t1",
        initiator_id=user.id,
        process_model_identifier="finance/invoice-approval",
        start=now - 30,
        status="running",
    )
    db_session.commit()

    response = client.get(
        "/v1.0/m8flow/process-instances",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    body = response.get_json()
    assert body["pagination"] == {"count": 2, "total": 2, "pages": 1}
    assert [row["status"] for row in body["results"]] == ["running", "complete"]  # newest first
    assert body["results"][0]["started_by"] == "editor"


def test_status_and_search_filters(client, db_session):
    user, token = _login_user(
        client, db_session, username="editor2", groups=["t1:editor"], tenant_id="t1"
    )
    now = int(time.time())
    _seed_instance(
        db_session,
        tenant_id="t1",
        initiator_id=user.id,
        process_model_identifier="finance/invoice-approval",
        start=now,
        status="complete",
    )
    _seed_instance(
        db_session,
        tenant_id="t1",
        initiator_id=user.id,
        process_model_identifier="onboarding/new-hire",
        start=now,
        status="error",
    )
    db_session.commit()

    by_status = client.get(
        "/v1.0/m8flow/process-instances?status=error",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert by_status.status_code == 200
    assert [r["process_model_identifier"] for r in by_status.get_json()["results"]] == ["onboarding/new-hire"]

    by_search = client.get(
        "/v1.0/m8flow/process-instances?search=invoice",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert by_search.status_code == 200
    assert [r["process_model_identifier"] for r in by_search.get_json()["results"]] == [
        "finance/invoice-approval"
    ]


def test_pagination_pages(client, db_session):
    user, token = _login_user(
        client, db_session, username="editor3", groups=["t1:editor"], tenant_id="t1"
    )
    now = int(time.time())
    for i in range(3):
        _seed_instance(
            db_session,
            tenant_id="t1",
            initiator_id=user.id,
            process_model_identifier="finance/invoice-approval",
            start=now - i,
            status="complete",
        )
    db_session.commit()

    page1 = client.get(
        "/v1.0/m8flow/process-instances?per_page=2&page=1",
        headers={"Authorization": f"Bearer {token}"},
    )
    body1 = page1.get_json()
    assert body1["pagination"] == {"count": 2, "total": 3, "pages": 2}

    page2 = client.get(
        "/v1.0/m8flow/process-instances?per_page=2&page=2",
        headers={"Authorization": f"Bearer {token}"},
    )
    body2 = page2.get_json()
    assert body2["pagination"] == {"count": 1, "total": 3, "pages": 2}


def test_reviewer_gets_empty_page(client, db_session):
    """reviewer lacks the process-instance list grant (and editor
    fallback) in this test's unsynced-YAML fixture setup — [] not 403,
    same convention as list_process_models."""
    user, token = _login_user(
        client, db_session, username="reviewer", groups=["t1:reviewer"], tenant_id="t1"
    )
    _seed_instance(
        db_session,
        tenant_id="t1",
        initiator_id=user.id,
        process_model_identifier="finance/invoice-approval",
        start=int(time.time()),
    )
    db_session.commit()

    response = client.get(
        "/v1.0/m8flow/process-instances",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    assert response.get_json() == {"results": [], "pagination": {"count": 0, "total": 0, "pages": 0}}


def test_super_admin_requires_concrete_tenant(client, db_session):
    _user, token = _login_user(
        client, db_session, username="super-admin", groups=["super-admin"], tenant_id="t1"
    )
    client.delete_cookie(SELECTED_TENANT_COOKIE_NAME)

    missing = client.get(
        "/v1.0/m8flow/process-instances",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert missing.status_code == 400
    assert missing.get_json()["error_code"] == "tenant_required"

    ok = client.get(
        "/v1.0/m8flow/process-instances?tenantId=t1",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert ok.status_code == 200


def test_tenant_isolation_across_instances(client, db_session):
    """A t2-scoped instance never appears in t1's list."""
    user1, token1 = _login_user(
        client, db_session, username="editor-t1", groups=["t1:editor"], tenant_id="t1"
    )
    user2, _token2 = _login_user(
        client, db_session, username="editor-t2", groups=["t2:editor"], tenant_id="t2"
    )
    now = int(time.time())
    _seed_instance(
        db_session,
        tenant_id="t1",
        initiator_id=user1.id,
        process_model_identifier="finance/invoice-approval",
        start=now,
    )
    _seed_instance(
        db_session,
        tenant_id="t2",
        initiator_id=user2.id,
        process_model_identifier="finance/other",
        start=now,
    )
    db_session.commit()

    client.set_cookie(SELECTED_TENANT_COOKIE_NAME, "t1")
    response = client.get(
        "/v1.0/m8flow/process-instances",
        headers={"Authorization": f"Bearer {token1}"},
    )
    body = response.get_json()
    assert [r["process_model_identifier"] for r in body["results"]] == ["finance/invoice-approval"]


def test_editor_gets_instance_detail_with_bpmn_xml_and_task_states(client, db_session):
    user, token = _login_user(
        client, db_session, username="editor4", groups=["t1:editor"], tenant_id="t1"
    )
    instance = _seed_instance(
        db_session,
        tenant_id="t1",
        initiator_id=user.id,
        process_model_identifier="finance/invoice-approval",
        start=int(time.time()),
        status="waiting",
    )
    _seed_definition_with_tasks(
        db_session,
        tenant_id="t1",
        process_instance=instance,
        bpmn_xml="<definitions>seeded</definitions>",
        task_states={"StartEvent_1": "COMPLETED", "Activity_1": "WAITING"},
    )
    db_session.commit()

    response = client.get(
        f"/v1.0/m8flow/process-instances/{instance.id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    body = response.get_json()
    assert body["id"] == instance.id
    assert body["status"] == "waiting"
    assert body["started_by"] == "editor4"
    assert body["bpmn_xml"] == "<definitions>seeded</definitions>"
    tasks_by_id = {t["bpmn_identifier"]: t["state"] for t in body["tasks"]}
    assert tasks_by_id == {"StartEvent_1": "COMPLETED", "Activity_1": "WAITING"}


def test_instance_detail_without_definition_has_null_bpmn_xml_and_no_tasks(client, db_session):
    user, token = _login_user(
        client, db_session, username="editor5", groups=["t1:editor"], tenant_id="t1"
    )
    instance = _seed_instance(
        db_session,
        tenant_id="t1",
        initiator_id=user.id,
        process_model_identifier="finance/invoice-approval",
        start=int(time.time()),
    )
    db_session.commit()

    response = client.get(
        f"/v1.0/m8flow/process-instances/{instance.id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    body = response.get_json()
    assert body["bpmn_xml"] is None
    assert body["tasks"] == []


def test_missing_instance_is_404(client, db_session):
    _user, token = _login_user(
        client, db_session, username="editor6", groups=["t1:editor"], tenant_id="t1"
    )
    db_session.commit()

    response = client.get(
        "/v1.0/m8flow/process-instances/999999",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 404


def test_instance_from_another_tenant_is_404_not_leaked(client, db_session):
    """Tenant isolation on the detail route: an instance that exists, just
    not in the caller's tenant, must 404 like it doesn't exist at all."""
    user2, _token2 = _login_user(
        client, db_session, username="editor-other-tenant", groups=["t2:editor"], tenant_id="t2"
    )
    other_instance = _seed_instance(
        db_session,
        tenant_id="t2",
        initiator_id=user2.id,
        process_model_identifier="finance/other",
        start=int(time.time()),
    )
    db_session.commit()

    _user1, token1 = _login_user(
        client, db_session, username="editor-t1-detail", groups=["t1:editor"], tenant_id="t1"
    )
    client.set_cookie(SELECTED_TENANT_COOKIE_NAME, "t1")

    response = client.get(
        f"/v1.0/m8flow/process-instances/{other_instance.id}",
        headers={"Authorization": f"Bearer {token1}"},
    )
    assert response.status_code == 404


def _seed_other_user(db_session, *, tenant_id: str, username: str):
    """A second initiator (no login/token needed) so owner-filter/owners
    tests can span more than one started_by."""
    user = ensure_user(
        db_session,
        username=username,
        service="https://example.test/realms/m8flow",
        service_id=username,
    )
    ensure_membership(
        db_session, user, ensure_tenant(db_session, tenant_id=tenant_id, slug=tenant_id)
    )
    db_session.flush()
    return user


def test_started_by_filter(client, db_session):
    user, token = _login_user(
        client, db_session, username="alice", groups=["t1:editor"], tenant_id="t1"
    )
    bob = _seed_other_user(db_session, tenant_id="t1", username="bob")
    now = int(time.time())
    _seed_instance(
        db_session,
        tenant_id="t1",
        initiator_id=user.id,
        process_model_identifier="finance/invoice-approval",
        start=now,
    )
    _seed_instance(
        db_session,
        tenant_id="t1",
        initiator_id=bob.id,
        process_model_identifier="onboarding/new-hire",
        start=now,
    )
    db_session.commit()

    response = client.get(
        "/v1.0/m8flow/process-instances?started_by=bob",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    body = response.get_json()
    assert body["pagination"]["total"] == 1
    assert [r["started_by"] for r in body["results"]] == ["bob"]


def test_sort_oldest_and_recent_start(client, db_session):
    user, token = _login_user(
        client, db_session, username="sorter", groups=["t1:editor"], tenant_id="t1"
    )
    now = int(time.time())
    # Insert out of id/time order so sort actually reorders rows.
    first = _seed_instance(
        db_session,
        tenant_id="t1",
        initiator_id=user.id,
        process_model_identifier="finance/a",
        start=now - 100,
    )
    second = _seed_instance(
        db_session,
        tenant_id="t1",
        initiator_id=user.id,
        process_model_identifier="finance/b",
        start=now - 10,
    )
    db_session.commit()

    newest = client.get(
        "/v1.0/m8flow/process-instances",
        headers={"Authorization": f"Bearer {token}"},
    ).get_json()
    assert [r["id"] for r in newest["results"]] == [second.id, first.id]

    oldest = client.get(
        "/v1.0/m8flow/process-instances?sort=oldest",
        headers={"Authorization": f"Bearer {token}"},
    ).get_json()
    assert [r["id"] for r in oldest["results"]] == [first.id, second.id]

    recent_start = client.get(
        "/v1.0/m8flow/process-instances?sort=recent_start",
        headers={"Authorization": f"Bearer {token}"},
    ).get_json()
    assert [r["id"] for r in recent_start["results"]] == [second.id, first.id]

    # Unknown sort falls back to newest, no error.
    fallback = client.get(
        "/v1.0/m8flow/process-instances?sort=bogus",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert fallback.status_code == 200
    assert [r["id"] for r in fallback.get_json()["results"]] == [second.id, first.id]


def test_owners_route_returns_distinct_sorted_usernames(client, db_session):
    user, token = _login_user(
        client, db_session, username="Zoe", groups=["t1:editor"], tenant_id="t1"
    )
    amir = _seed_other_user(db_session, tenant_id="t1", username="amir")
    now = int(time.time())
    # Zoe initiates two, amir one -> owners is deduped + case-insensitively sorted.
    for i in range(2):
        _seed_instance(
            db_session,
            tenant_id="t1",
            initiator_id=user.id,
            process_model_identifier="finance/invoice-approval",
            start=now - i,
        )
    _seed_instance(
        db_session,
        tenant_id="t1",
        initiator_id=amir.id,
        process_model_identifier="onboarding/new-hire",
        start=now,
    )
    db_session.commit()

    response = client.get(
        "/v1.0/m8flow/process-instances/owners",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    assert response.get_json() == {"owners": ["amir", "Zoe"]}


def test_owners_route_is_tenant_scoped(client, db_session):
    user1, token1 = _login_user(
        client, db_session, username="owner-t1", groups=["t1:editor"], tenant_id="t1"
    )
    user2 = _seed_other_user(db_session, tenant_id="t2", username="owner-t2")
    now = int(time.time())
    _seed_instance(
        db_session,
        tenant_id="t1",
        initiator_id=user1.id,
        process_model_identifier="finance/a",
        start=now,
    )
    _seed_instance(
        db_session,
        tenant_id="t2",
        initiator_id=user2.id,
        process_model_identifier="finance/b",
        start=now,
    )
    db_session.commit()

    client.set_cookie(SELECTED_TENANT_COOKIE_NAME, "t1")
    response = client.get(
        "/v1.0/m8flow/process-instances/owners",
        headers={"Authorization": f"Bearer {token1}"},
    )
    assert response.status_code == 200
    assert response.get_json() == {"owners": ["owner-t1"]}


def test_owners_route_empty_for_denied_caller(client, db_session):
    _user, token = _login_user(
        client, db_session, username="reviewer-owners", groups=["t1:reviewer"], tenant_id="t1"
    )
    db_session.commit()

    response = client.get(
        "/v1.0/m8flow/process-instances/owners",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    assert response.get_json() == {"owners": []}
