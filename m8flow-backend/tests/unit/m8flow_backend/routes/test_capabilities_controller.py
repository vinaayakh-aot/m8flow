from __future__ import annotations

from m8flow_backend.auth import encode_auth_token
from m8flow_backend.identity import ensure_membership, ensure_tenant, ensure_user, sync_groups
from m8flow_backend.tenancy import SELECTED_TENANT_COOKIE_NAME


def _login_user(client, db_session, *, username, groups, tenant_id="t1"):
    from m8flow_bpmn_core.services.authorization import ensure_v1_role

    ensure_tenant(db_session, tenant_id=tenant_id, slug=tenant_id)
    user = ensure_user(
        db_session, username=username, service="https://example.test/realms/m8flow", service_id=username
    )
    ensure_membership(db_session, user, ensure_tenant(db_session, tenant_id=tenant_id, slug=tenant_id))
    sync_groups(db_session, user=user, group_identifiers=groups, tenant_id=tenant_id)
    ensure_v1_role(db_session, tenant_id=tenant_id, role_name="user", user_ids=(user.id,))
    db_session.commit()
    token = encode_auth_token(user=user)
    client.set_cookie(SELECTED_TENANT_COOKIE_NAME, tenant_id)
    return user, token


def test_editor_can_manage_processes(client, db_session):
    _user, token = _login_user(client, db_session, username="cap-editor", groups=["t1:editor"])
    resp = client.get("/v1.0/m8flow/capabilities", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["can_manage_processes"] is True
    assert body["can_read_authentications"] is False
    assert body["can_manage_authentications"] is False


def test_viewer_cannot_manage_processes(client, db_session):
    _user, token = _login_user(client, db_session, username="cap-viewer", groups=["t1:viewer"])
    resp = client.get("/v1.0/m8flow/capabilities", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["can_manage_processes"] is False
    assert body["can_read_authentications"] is True
    assert body["can_manage_authentications"] is False


def test_integrator_can_manage_authentications(client, db_session):
    _user, token = _login_user(client, db_session, username="cap-integrator", groups=["t1:integrator"])
    resp = client.get("/v1.0/m8flow/capabilities", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["can_read_authentications"] is True
    assert body["can_manage_authentications"] is True


def test_capabilities_requires_auth(client, db_session):
    resp = client.get("/v1.0/m8flow/capabilities")
    assert resp.status_code == 401
