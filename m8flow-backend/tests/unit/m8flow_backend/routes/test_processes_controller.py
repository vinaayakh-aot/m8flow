from __future__ import annotations

import json
import time
from pathlib import Path

from m8flow_backend.auth import encode_auth_token
from m8flow_backend.identity import ensure_membership, ensure_tenant, ensure_user, sync_groups
from m8flow_backend.routes.processes_controller import process_model_identifier_from_path_param
from m8flow_backend.tenancy import SELECTED_TENANT_COOKIE_NAME

VALID_BPMN = Path(__file__).resolve().parents[3] / "fixtures" / "invoice_approval_poc.bpmn"


def test_path_param_unquotes_colon_and_double_encoding():
    assert process_model_identifier_from_path_param("finance:invoice-approval") == (
        "finance/invoice-approval"
    )
    assert process_model_identifier_from_path_param("finance%3Ainvoice-approval") == (
        "finance/invoice-approval"
    )
    assert process_model_identifier_from_path_param("finance%253Ainvoice-approval") == (
        "finance/invoice-approval"
    )


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


def _seed_catalog(tmp_path, monkeypatch, *, tenant_id: str) -> None:
    root = tmp_path / "bpmn" / tenant_id
    model_dir = root / "finance" / "invoice-approval"
    model_dir.mkdir(parents=True)
    (root / "finance" / "process_group.json").write_text(
        json.dumps({"display_name": "Finance", "description": "Finance flows"}),
        encoding="utf-8",
    )
    (model_dir / "invoice-approval.bpmn").write_text(
        '<?xml version="1.0"?><definitions xmlns="http://www.omg.org/spec/BPMN/20100524/MODEL"/>',
        encoding="utf-8",
    )
    (model_dir / "invoice-form-schema.json").write_text("{}", encoding="utf-8")
    (model_dir / "process_model.json").write_text(
        json.dumps(
            {
                "display_name": "Invoice Approval",
                "description": "Two-step",
                "primary_file_name": "invoice-approval.bpmn",
            }
        ),
        encoding="utf-8",
    )
    other = root / "onboarding" / "new-hire"
    other.mkdir(parents=True)
    (root / "onboarding" / "process_group.json").write_text(
        json.dumps({"display_name": "Onboarding"}),
        encoding="utf-8",
    )
    (other / "process_model.json").write_text(
        json.dumps({"display_name": "New Hire"}),
        encoding="utf-8",
    )
    (other / "new-hire.bpmn").write_text(
        '<?xml version="1.0"?><definitions xmlns="http://www.omg.org/spec/BPMN/20100524/MODEL"/>',
        encoding="utf-8",
    )
    empty = root / "archived"
    empty.mkdir(parents=True)
    (empty / "process_group.json").write_text(
        json.dumps({"display_name": "Archived", "description": "No models yet"}),
        encoding="utf-8",
    )
    monkeypatch.setenv("M8FLOW_BACKEND_BPMN_SPEC_ABSOLUTE_DIR", str(tmp_path / "bpmn"))


def _seed_instance(
    db_session,
    *,
    tenant_id: str,
    initiator_id: int,
    process_model_identifier: str,
    start: int | None,
    status: str = "complete",
):
    from m8flow_bpmn_core.models.process_instance import ProcessInstanceModel

    now = int(time.time())
    terminal = status in {"complete", "error", "terminated"}
    instance = ProcessInstanceModel(
        m8f_tenant_id=tenant_id,
        process_model_identifier=process_model_identifier,
        process_model_display_name=process_model_identifier.split("/")[-1],
        process_initiator_id=initiator_id,
        status=status,
        start_in_seconds=start,
        end_in_seconds=start + 60 if start is not None and terminal else None,
        created_at_in_seconds=now,
        updated_at_in_seconds=now,
    )
    db_session.add(instance)
    db_session.flush()
    return instance


def test_editor_lists_models_with_run_stats(client, db_session, tmp_path, monkeypatch):
    _seed_catalog(tmp_path, monkeypatch, tenant_id="t1")
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
    )
    _seed_instance(
        db_session,
        tenant_id="t1",
        initiator_id=user.id,
        process_model_identifier="finance/invoice-approval",
        start=now - 40 * 24 * 60 * 60,  # outside 30d window
    )
    db_session.commit()

    response = client.get(
        "/v1.0/m8flow/process-models",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    body = response.get_json()
    assert len(body) == 2
    by_id = {row["id"]: row for row in body}
    invoice = by_id["finance/invoice-approval"]
    assert invoice["display_name"] == "Invoice Approval"
    assert invoice["group_id"] == "finance"
    assert invoice["group_display_name"] == "Finance"
    assert invoice["last_run_in_seconds"] == now - 60
    assert invoice["runs_30d"] == 1
    hire = by_id["onboarding/new-hire"]
    assert hire["display_name"] == "New Hire"
    assert hire["last_run_in_seconds"] is None
    assert hire["runs_30d"] == 0


def test_group_filter_and_unknown_group(client, db_session, tmp_path, monkeypatch):
    _seed_catalog(tmp_path, monkeypatch, tenant_id="t1")
    _user, token = _login_user(
        client, db_session, username="editor2", groups=["t1:editor"], tenant_id="t1"
    )

    filtered = client.get(
        "/v1.0/m8flow/process-models?group=finance",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert filtered.status_code == 200
    rows = filtered.get_json()
    assert [row["id"] for row in rows] == ["finance/invoice-approval"]

    missing = client.get(
        "/v1.0/m8flow/process-models?group=does-not-exist",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert missing.status_code == 200
    assert missing.get_json() == []


def test_reviewer_gets_empty_list(client, db_session, tmp_path, monkeypatch):
    """reviewer lacks /process-models list grant (and editor fallback); [] not 403."""
    _seed_catalog(tmp_path, monkeypatch, tenant_id="t1")
    _user, token = _login_user(
        client, db_session, username="reviewer", groups=["t1:reviewer"], tenant_id="t1"
    )

    response = client.get(
        "/v1.0/m8flow/process-models",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    assert response.get_json() == []


def test_super_admin_requires_concrete_tenant(client, db_session, tmp_path, monkeypatch):
    _seed_catalog(tmp_path, monkeypatch, tenant_id="t1")
    _user, token = _login_user(
        client, db_session, username="super-admin", groups=["super-admin"], tenant_id="t1"
    )
    # Drop the cookie _login_user set so All Tenants has no concrete tenant.
    client.delete_cookie(SELECTED_TENANT_COOKIE_NAME)

    missing = client.get(
        "/v1.0/m8flow/process-models",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert missing.status_code == 400
    assert missing.get_json()["error_code"] == "tenant_required"

    ok = client.get(
        "/v1.0/m8flow/process-models?tenantId=t1",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert ok.status_code == 200
    assert len(ok.get_json()) == 2


def test_thin_v1_process_models_unchanged(client, db_session, tmp_path, monkeypatch):
    _seed_catalog(tmp_path, monkeypatch, tenant_id="t1")
    _user, token = _login_user(
        client, db_session, username="editor3", groups=["t1:editor"], tenant_id="t1"
    )

    response = client.get(
        "/v1.0/process-models",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    assert response.get_json() == [
        "finance/invoice-approval",
        "onboarding/new-hire",
    ]


def test_editor_lists_groups_with_empty_group_and_last_run(client, db_session, tmp_path, monkeypatch):
    _seed_catalog(tmp_path, monkeypatch, tenant_id="t1")
    user, token = _login_user(
        client, db_session, username="editor-groups", groups=["t1:editor"], tenant_id="t1"
    )
    now = int(time.time())
    _seed_instance(
        db_session,
        tenant_id="t1",
        initiator_id=user.id,
        process_model_identifier="finance/invoice-approval",
        start=now - 120,
    )
    db_session.commit()

    response = client.get(
        "/v1.0/m8flow/process-groups",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    body = response.get_json()
    by_id = {row["id"]: row for row in body}
    assert set(by_id) == {"archived", "finance", "onboarding"}
    assert by_id["finance"]["display_name"] == "Finance"
    assert by_id["finance"]["description"] == "Finance flows"
    assert by_id["finance"]["model_count"] == 1
    assert by_id["finance"]["last_run_in_seconds"] == now - 120
    assert by_id["onboarding"]["model_count"] == 1
    assert by_id["onboarding"]["last_run_in_seconds"] is None
    assert by_id["onboarding"]["description"] == ""
    assert by_id["archived"]["display_name"] == "Archived"
    assert by_id["archived"]["model_count"] == 0
    assert by_id["archived"]["last_run_in_seconds"] is None


def test_reviewer_gets_empty_groups_list(client, db_session, tmp_path, monkeypatch):
    _seed_catalog(tmp_path, monkeypatch, tenant_id="t1")
    _user, token = _login_user(
        client, db_session, username="reviewer-groups", groups=["t1:reviewer"], tenant_id="t1"
    )

    response = client.get(
        "/v1.0/m8flow/process-groups",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    assert response.get_json() == []


def test_super_admin_groups_require_concrete_tenant(client, db_session, tmp_path, monkeypatch):
    _seed_catalog(tmp_path, monkeypatch, tenant_id="t1")
    _user, token = _login_user(
        client, db_session, username="super-admin-groups", groups=["super-admin"], tenant_id="t1"
    )
    client.delete_cookie(SELECTED_TENANT_COOKIE_NAME)

    missing = client.get(
        "/v1.0/m8flow/process-groups",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert missing.status_code == 400
    assert missing.get_json()["error_code"] == "tenant_required"

    ok = client.get(
        "/v1.0/m8flow/process-groups?tenantId=t1",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert ok.status_code == 200
    assert len(ok.get_json()) == 3


def test_editor_gets_process_model_detail(client, db_session, tmp_path, monkeypatch):
    _seed_catalog(tmp_path, monkeypatch, tenant_id="t1")
    user, token = _login_user(
        client, db_session, username="editor-detail", groups=["t1:editor"], tenant_id="t1"
    )
    now = int(time.time())
    _seed_instance(
        db_session,
        tenant_id="t1",
        initiator_id=user.id,
        process_model_identifier="finance/invoice-approval",
        start=now - 90,
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
        "/v1.0/m8flow/process-models/finance:invoice-approval",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    body = response.get_json()
    assert body["id"] == "finance/invoice-approval"
    assert body["display_name"] == "Invoice Approval"
    assert body["description"] == "Two-step"
    assert body["group_id"] == "finance"
    assert body["group_display_name"] == "Finance"
    assert body["last_run_in_seconds"] == now - 30
    assert body["running_now"] == 1
    assert body["runs_30d"] == 2
    assert len(body["recent_instances"]) == 2
    assert body["recent_instances"][0]["status"] == "running"
    assert body["recent_instances"][0]["started_by"] == "editor-detail"
    assert body["recent_instances"][0]["duration_seconds"] is None
    assert body["recent_instances"][1]["duration_seconds"] == 60
    names = {f["name"]: f for f in body["files"]}
    assert "invoice-approval.bpmn" in names
    assert names["invoice-approval.bpmn"]["primary"] is True
    assert "invoice-form-schema.json" in names
    assert names["invoice-form-schema.json"]["primary"] is False
    assert "process_model.json" not in names


def test_detail_when_bpmn_filename_differs_from_model_id(client, db_session, tmp_path, monkeypatch):
    """Template-created models keep the template BPMN name, not {leaf-id}.bpmn."""
    _seed_catalog(tmp_path, monkeypatch, tenant_id="t1")
    model_dir = tmp_path / "bpmn" / "t1" / "test-process-group" / "wfh-group-4355dd7e70"
    model_dir.mkdir(parents=True)
    (tmp_path / "bpmn" / "t1" / "test-process-group" / "process_group.json").write_text(
        json.dumps({"display_name": "Test process group"}),
        encoding="utf-8",
    )
    (model_dir / "wfh-approval.bpmn").write_text(
        '<?xml version="1.0"?><definitions xmlns="http://www.omg.org/spec/BPMN/20100524/MODEL"/>',
        encoding="utf-8",
    )
    (model_dir / "process_model.json").write_text(
        json.dumps(
            {
                "display_name": "WFH approval",
                "primary_file_name": "wfh-approval.bpmn",
            }
        ),
        encoding="utf-8",
    )
    _user, token = _login_user(
        client, db_session, username="editor-wfh", groups=["t1:editor"], tenant_id="t1"
    )

    listed = client.get(
        "/v1.0/m8flow/process-models",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert listed.status_code == 200
    assert "test-process-group/wfh-group-4355dd7e70" in {
        row["id"] for row in listed.get_json()
    }

    response = client.get(
        "/v1.0/m8flow/process-models/test-process-group:wfh-group-4355dd7e70",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    body = response.get_json()
    assert body["id"] == "test-process-group/wfh-group-4355dd7e70"
    assert body["display_name"] == "WFH approval"
    names = {f["name"]: f for f in body["files"]}
    assert names["wfh-approval.bpmn"]["primary"] is True

    encoded = client.get(
        "/v1.0/m8flow/process-models/test-process-group%3Awfh-group-4355dd7e70",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert encoded.status_code == 200
    assert encoded.get_json()["id"] == "test-process-group/wfh-group-4355dd7e70"


def test_editor_saves_bpmn_file_with_a_non_leaf_name_writes_only_the_real_file(
    client, db_session, tmp_path, monkeypatch
):
    """Regression for architecture review finding W2: catalog._model_file_path
    used to hard-code {model-id-leaf}.bpmn regardless of the file actually
    being written, so every edit to a template-created model (which keeps its
    template's original filename, e.g. wfh-approval.bpmn under model id
    wfh-group-4355dd7e70) wrote the real file *and* a phantom
    wfh-group-4355dd7e70.bpmn alongside it."""
    _seed_catalog(tmp_path, monkeypatch, tenant_id="t1")
    model_dir = tmp_path / "bpmn" / "t1" / "test-process-group" / "wfh-group-4355dd7e70"
    model_dir.mkdir(parents=True)
    (tmp_path / "bpmn" / "t1" / "test-process-group" / "process_group.json").write_text(
        json.dumps({"display_name": "Test process group"}),
        encoding="utf-8",
    )
    (model_dir / "wfh-approval.bpmn").write_text(
        '<?xml version="1.0"?><definitions xmlns="http://www.omg.org/spec/BPMN/20100524/MODEL"/>',
        encoding="utf-8",
    )
    (model_dir / "process_model.json").write_text(
        json.dumps({"display_name": "WFH approval", "primary_file_name": "wfh-approval.bpmn"}),
        encoding="utf-8",
    )
    _user, token = _login_user(
        client, db_session, username="editor-wfh-save", groups=["t1:editor"], tenant_id="t1", v1_role="admin"
    )
    xml = VALID_BPMN.read_bytes()

    response = client.put(
        "/v1.0/m8flow/process-models/test-process-group:wfh-group-4355dd7e70/files/wfh-approval.bpmn",
        data=xml,
        headers={"Authorization": f"Bearer {token}"},
        content_type="application/octet-stream",
    )
    assert response.status_code == 200

    assert model_dir.joinpath("wfh-approval.bpmn").read_bytes() == xml
    phantom = model_dir / "wfh-group-4355dd7e70.bpmn"
    assert not phantom.exists(), "save() must not write a leaf-name-guessed phantom file"
    assert sorted(p.name for p in model_dir.glob("*.bpmn")) == ["wfh-approval.bpmn"]


def test_detail_missing_model_is_404(client, db_session, tmp_path, monkeypatch):
    _seed_catalog(tmp_path, monkeypatch, tenant_id="t1")
    _user, token = _login_user(
        client, db_session, username="editor-missing", groups=["t1:editor"], tenant_id="t1"
    )

    response = client.get(
        "/v1.0/m8flow/process-models/finance:does-not-exist",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 404
    assert response.get_json()["error_code"] == "not_found"


def test_reviewer_detail_is_404(client, db_session, tmp_path, monkeypatch):
    _seed_catalog(tmp_path, monkeypatch, tenant_id="t1")
    _user, token = _login_user(
        client, db_session, username="reviewer-detail", groups=["t1:reviewer"], tenant_id="t1"
    )

    response = client.get(
        "/v1.0/m8flow/process-models/finance:invoice-approval",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 404
    assert response.get_json()["error_code"] == "not_found"


def test_editor_reads_process_model_file_content(client, db_session, tmp_path, monkeypatch):
    _seed_catalog(tmp_path, monkeypatch, tenant_id="t1")
    _user, token = _login_user(
        client, db_session, username="editor-file-read", groups=["t1:editor"], tenant_id="t1"
    )

    bpmn = client.get(
        "/v1.0/m8flow/process-models/finance:invoice-approval/files/invoice-approval.bpmn",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert bpmn.status_code == 200
    assert bpmn.mimetype == "application/xml"
    assert b"<?xml" in bpmn.data

    schema = client.get(
        "/v1.0/m8flow/process-models/finance:invoice-approval/files/invoice-form-schema.json",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert schema.status_code == 200
    assert schema.mimetype == "application/json"
    assert schema.data == b"{}"


def test_read_file_missing_file_or_model_is_404(client, db_session, tmp_path, monkeypatch):
    _seed_catalog(tmp_path, monkeypatch, tenant_id="t1")
    _user, token = _login_user(
        client, db_session, username="editor-file-404", groups=["t1:editor"], tenant_id="t1"
    )

    missing_file = client.get(
        "/v1.0/m8flow/process-models/finance:invoice-approval/files/does-not-exist.bpmn",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert missing_file.status_code == 404
    assert missing_file.get_json()["error_code"] == "not_found"

    missing_model = client.get(
        "/v1.0/m8flow/process-models/finance:does-not-exist/files/whatever.bpmn",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert missing_model.status_code == 404


def test_reviewer_read_file_is_404(client, db_session, tmp_path, monkeypatch):
    """Same 404-for-denied convention as the detail endpoint, not 403."""
    _seed_catalog(tmp_path, monkeypatch, tenant_id="t1")
    _user, token = _login_user(
        client, db_session, username="reviewer-file", groups=["t1:reviewer"], tenant_id="t1"
    )

    response = client.get(
        "/v1.0/m8flow/process-models/finance:invoice-approval/files/invoice-approval.bpmn",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 404


def test_read_file_path_traversal_is_rejected(client, db_session, tmp_path, monkeypatch):
    _seed_catalog(tmp_path, monkeypatch, tenant_id="t1")
    _user, token = _login_user(
        client, db_session, username="editor-traversal", groups=["t1:editor"], tenant_id="t1"
    )

    response = client.get(
        "/v1.0/m8flow/process-models/finance:invoice-approval/files/sub/evil.txt",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 400
    assert response.get_json()["error_code"] == "invalid_file_name"


def test_editor_saves_non_bpmn_file_and_git_commits(client, db_session, tmp_path, monkeypatch):
    _seed_catalog(tmp_path, monkeypatch, tenant_id="t1")
    _user, token = _login_user(
        client, db_session, username="editor-save-json", groups=["t1:editor"], tenant_id="t1"
    )
    model_dir = tmp_path / "bpmn" / "t1" / "finance" / "invoice-approval"
    subprocess_run = __import__("subprocess").run
    subprocess_run(["git", "init"], cwd=model_dir, capture_output=True)
    subprocess_run(["git", "config", "user.email", "test@example.test"], cwd=model_dir, capture_output=True)
    subprocess_run(["git", "config", "user.name", "Test"], cwd=model_dir, capture_output=True)

    response = client.put(
        "/v1.0/m8flow/process-models/finance:invoice-approval/files/invoice-form-schema.json",
        data=b'{"updated": true}',
        headers={"Authorization": f"Bearer {token}"},
        content_type="application/octet-stream",
    )
    assert response.status_code == 200
    body = response.get_json()
    assert body["name"] == "invoice-form-schema.json"
    assert body["size_bytes"] == len(b'{"updated": true}')

    saved = (model_dir / "invoice-form-schema.json").read_text(encoding="utf-8")
    assert saved == '{"updated": true}'

    log = subprocess_run(
        ["git", "log", "--oneline"], cwd=model_dir, capture_output=True, text=True
    )
    assert "invoice-form-schema.json" in log.stdout


def test_editor_saves_bpmn_file_reimports_definition(client, db_session, tmp_path, monkeypatch):
    """Re-importing a .bpmn file goes through workflow.import_definition, which
    enforces m8flow-bpmn-core's own V1 "admin"-role command RBAC
    (process_definition.import) — a separate layer from the editor/tenant-admin
    URI-based groups this endpoint's own allow_uri() gate checks (see
    test_workflow_operations.py's _seed_actor, which grants role_name="admin"
    for the same reason). v1_role="user" (this file's default) 403s here even
    though the very same editor group succeeds for a non-bpmn file above —
    logged as a real, pre-existing gap in this ticket's answer, not fixed here.
    """
    _seed_catalog(tmp_path, monkeypatch, tenant_id="t1")
    _user, token = _login_user(
        client,
        db_session,
        username="editor-save-bpmn",
        groups=["t1:editor"],
        tenant_id="t1",
        v1_role="admin",
    )
    xml = VALID_BPMN.read_bytes()

    response = client.put(
        "/v1.0/m8flow/process-models/finance:invoice-approval/files/invoice-approval.bpmn",
        data=xml,
        headers={"Authorization": f"Bearer {token}"},
        content_type="application/octet-stream",
    )
    assert response.status_code == 200

    model_dir = tmp_path / "bpmn" / "t1" / "finance" / "invoice-approval"
    assert model_dir.joinpath("invoice-approval.bpmn").read_bytes() == xml


def test_editor_without_v1_admin_role_cannot_save_bpmn(client, db_session, tmp_path, monkeypatch):
    """Pins the gap documented on test_editor_saves_bpmn_file_reimports_definition:
    the editor group alone is not sufficient for .bpmn saves specifically —
    core's V1 "admin" role is also required. Non-bpmn saves are unaffected
    (see test_editor_saves_non_bpmn_file_and_git_commits, same group, no
    v1_role override, 200)."""
    _seed_catalog(tmp_path, monkeypatch, tenant_id="t1")
    _user, token = _login_user(
        client, db_session, username="editor-no-v1-admin", groups=["t1:editor"], tenant_id="t1"
    )

    response = client.put(
        "/v1.0/m8flow/process-models/finance:invoice-approval/files/invoice-approval.bpmn",
        data=VALID_BPMN.read_bytes(),
        headers={"Authorization": f"Bearer {token}"},
        content_type="application/octet-stream",
    )
    assert response.status_code == 403
    assert response.get_json()["error_code"] == "permission_denied"


def test_save_file_missing_model_is_404(client, db_session, tmp_path, monkeypatch):
    _seed_catalog(tmp_path, monkeypatch, tenant_id="t1")
    _user, token = _login_user(
        client, db_session, username="editor-save-404", groups=["t1:editor"], tenant_id="t1"
    )

    response = client.put(
        "/v1.0/m8flow/process-models/finance:does-not-exist/files/whatever.json",
        data=b"{}",
        headers={"Authorization": f"Bearer {token}"},
        content_type="application/octet-stream",
    )
    assert response.status_code == 404


def test_save_file_empty_body_is_400(client, db_session, tmp_path, monkeypatch):
    _seed_catalog(tmp_path, monkeypatch, tenant_id="t1")
    _user, token = _login_user(
        client, db_session, username="editor-save-empty", groups=["t1:editor"], tenant_id="t1"
    )

    response = client.put(
        "/v1.0/m8flow/process-models/finance:invoice-approval/files/invoice-form-schema.json",
        data=b"",
        headers={"Authorization": f"Bearer {token}"},
        content_type="application/octet-stream",
    )
    assert response.status_code == 400
    assert response.get_json()["error_code"] == "missing_content"


def test_save_file_path_traversal_is_rejected(client, db_session, tmp_path, monkeypatch):
    _seed_catalog(tmp_path, monkeypatch, tenant_id="t1")
    _user, token = _login_user(
        client, db_session, username="editor-save-traversal", groups=["t1:editor"], tenant_id="t1"
    )

    response = client.put(
        "/v1.0/m8flow/process-models/finance:invoice-approval/files/../evil.json",
        data=b"{}",
        headers={"Authorization": f"Bearer {token}"},
        content_type="application/octet-stream",
    )
    assert response.status_code == 400
    assert response.get_json()["error_code"] == "invalid_file_name"


def test_reviewer_save_file_is_403(client, db_session, tmp_path, monkeypatch):
    """Write op: denied is 403, unlike the read endpoints' 404-for-denied."""
    _seed_catalog(tmp_path, monkeypatch, tenant_id="t1")
    _user, token = _login_user(
        client, db_session, username="reviewer-save", groups=["t1:reviewer"], tenant_id="t1"
    )

    response = client.put(
        "/v1.0/m8flow/process-models/finance:invoice-approval/files/invoice-form-schema.json",
        data=b"{}",
        headers={"Authorization": f"Bearer {token}"},
        content_type="application/octet-stream",
    )
    assert response.status_code == 403
    assert response.get_json()["error_code"] == "permission_denied"


def _import_definition(db_session, *, tenant_id: str, user_id: int, model_id: str) -> None:
    """Import a real BPMN definition so workflow.start can resolve one."""
    from m8flow_backend import workflow

    workflow.import_definition(
        db_session,
        tenant_id=tenant_id,
        user_id=user_id,
        bpmn_identifier=model_id,
        source_bpmn_xml=VALID_BPMN.read_text(encoding="utf-8"),
        bpmn_name=f"{model_id.split('/')[-1]}.bpmn",
    )
    db_session.commit()


def test_editor_starts_process_instance(client, db_session, tmp_path, monkeypatch):
    _seed_catalog(tmp_path, monkeypatch, tenant_id="t1")
    user, token = _login_user(
        client, db_session, username="starter", groups=["t1:editor"], tenant_id="t1", v1_role="admin"
    )
    _import_definition(db_session, tenant_id="t1", user_id=user.id, model_id="finance/invoice-approval")

    response = client.post(
        "/v1.0/m8flow/process-models/finance:invoice-approval/start",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 201
    body = response.get_json()
    assert body["process_model_identifier"] == "finance/invoice-approval"
    assert isinstance(body["id"], int)

    # The instance is really persisted and tenant-scoped.
    from m8flow_bpmn_core.models.process_instance import ProcessInstanceModel

    instance = db_session.get(ProcessInstanceModel, body["id"])
    assert instance is not None
    assert instance.m8f_tenant_id == "t1"
    assert instance.process_model_identifier == "finance/invoice-approval"


def test_start_missing_model_is_404(client, db_session, tmp_path, monkeypatch):
    _seed_catalog(tmp_path, monkeypatch, tenant_id="t1")
    _user, token = _login_user(
        client, db_session, username="starter2", groups=["t1:editor"], tenant_id="t1"
    )
    response = client.post(
        "/v1.0/m8flow/process-models/finance:does-not-exist/start",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 404


def test_reviewer_cannot_start_process_instance(client, db_session, tmp_path, monkeypatch):
    _seed_catalog(tmp_path, monkeypatch, tenant_id="t1")
    _user, token = _login_user(
        client, db_session, username="reviewer-start", groups=["t1:reviewer"], tenant_id="t1"
    )
    response = client.post(
        "/v1.0/m8flow/process-models/finance:invoice-approval/start",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 403


def test_editor_deletes_process_model(client, db_session, tmp_path, monkeypatch):
    _seed_catalog(tmp_path, monkeypatch, tenant_id="t1")
    _user, token = _login_user(
        client, db_session, username="deleter", groups=["t1:editor"], tenant_id="t1"
    )
    model_dir = tmp_path / "bpmn" / "t1" / "finance" / "invoice-approval"
    assert model_dir.is_dir()

    response = client.delete(
        "/v1.0/m8flow/process-models/finance:invoice-approval",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    assert response.get_json() == {"deleted": True, "id": "finance/invoice-approval"}
    assert not model_dir.exists()


def test_delete_blocked_when_instances_exist(client, db_session, tmp_path, monkeypatch):
    _seed_catalog(tmp_path, monkeypatch, tenant_id="t1")
    user, token = _login_user(
        client, db_session, username="deleter2", groups=["t1:editor"], tenant_id="t1"
    )
    _seed_instance(
        db_session,
        tenant_id="t1",
        initiator_id=user.id,
        process_model_identifier="finance/invoice-approval",
        start=int(time.time()),
    )
    db_session.commit()

    response = client.delete(
        "/v1.0/m8flow/process-models/finance:invoice-approval",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 409
    assert response.get_json()["error_code"] == "process_model_has_instances"
    # Model is untouched on disk.
    assert (tmp_path / "bpmn" / "t1" / "finance" / "invoice-approval").is_dir()


def test_delete_missing_model_is_404(client, db_session, tmp_path, monkeypatch):
    _seed_catalog(tmp_path, monkeypatch, tenant_id="t1")
    _user, token = _login_user(
        client, db_session, username="deleter3", groups=["t1:editor"], tenant_id="t1"
    )
    response = client.delete(
        "/v1.0/m8flow/process-models/finance:nope",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 404


def test_reviewer_cannot_delete_process_model(client, db_session, tmp_path, monkeypatch):
    _seed_catalog(tmp_path, monkeypatch, tenant_id="t1")
    _user, token = _login_user(
        client, db_session, username="reviewer-del", groups=["t1:reviewer"], tenant_id="t1"
    )
    response = client.delete(
        "/v1.0/m8flow/process-models/finance:invoice-approval",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 403
    assert (tmp_path / "bpmn" / "t1" / "finance" / "invoice-approval").is_dir()


# Minimal BPMN that imports fine but has no start event, so starting it raises
# SpiffWorkflow's ValidationException("No start event found.") — which the host
# must surface as a clean 422, not a 500.
_NO_START_EVENT_BPMN = (
    '<?xml version="1.0" encoding="UTF-8"?>'
    '<bpmn:definitions xmlns:bpmn="http://www.omg.org/spec/BPMN/20100524/MODEL" '
    'id="Defs_nostart" targetNamespace="http://bpmn.io/schema/bpmn">'
    '<bpmn:process id="finance/invoice-approval" isExecutable="true">'
    '<bpmn:task id="Task_1" name="Orphan task" />'
    '</bpmn:process>'
    '</bpmn:definitions>'
)


def test_start_unstartable_model_maps_to_422(client, db_session, tmp_path, monkeypatch):
    _seed_catalog(tmp_path, monkeypatch, tenant_id="t1")
    from m8flow_backend import workflow

    user, token = _login_user(
        client, db_session, username="starter-nostart", groups=["t1:editor"], tenant_id="t1", v1_role="admin"
    )
    workflow.import_definition(
        db_session,
        tenant_id="t1",
        user_id=user.id,
        bpmn_identifier="finance/invoice-approval",
        source_bpmn_xml=_NO_START_EVENT_BPMN,
        bpmn_name="invoice-approval.bpmn",
    )
    db_session.commit()

    response = client.post(
        "/v1.0/m8flow/process-models/finance:invoice-approval/start",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 422
    assert response.get_json()["error_code"] == "invalid_process_model"
