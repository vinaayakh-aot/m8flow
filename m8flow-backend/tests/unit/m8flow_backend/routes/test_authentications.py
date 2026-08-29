from __future__ import annotations

from m8flow_backend.auth import encode_auth_token
from m8flow_backend.identity import ensure_membership, ensure_tenant, ensure_user, import_yaml, sync_groups
from m8flow_backend.tenancy import SELECTED_TENANT_COOKIE_NAME


def _login_user(client, db_session, *, username: str, groups: list[str], tenant_id: str):
    from m8flow_bpmn_core.services.authorization import ensure_v1_role

    tenant = ensure_tenant(db_session, tenant_id=tenant_id, slug=tenant_id)
    user = ensure_user(
        db_session,
        username=username,
        service="https://example.test/realms/m8flow",
        service_id=username,
    )
    ensure_membership(db_session, user, tenant)
    sync_groups(db_session, user=user, group_identifiers=groups, tenant_id=tenant_id)
    import_yaml(db_session, tenant_id=tenant_id)
    ensure_v1_role(db_session, tenant_id=tenant_id, role_name="user", user_ids=(user.id,))
    db_session.commit()
    token = encode_auth_token(user=user)
    client.set_cookie(SELECTED_TENANT_COOKIE_NAME, tenant_id)
    return user, token


def _auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def test_integrator_creates_lists_and_revokes_service_account(client, db_session):
    _user, token = _login_user(
        client, db_session, username="integrator", groups=["t1:integrator"], tenant_id="t1"
    )
    headers = _auth_headers(token)
    created = client.post("/v1.0/authentications", json={"name": "ci-bot"}, headers=headers)
    assert created.status_code == 201
    body = created.get_json()
    assert body["name"] == "ci-bot"
    assert body["client_id"]
    api_key = body["api_key"]
    assert api_key.startswith("m8sa_")
    assert "secret_hash" not in body

    listed = client.get("/v1.0/authentications", headers=headers)
    assert listed.status_code == 200
    rows = listed.get_json()
    assert len(rows) == 1
    assert rows[0]["id"] == body["id"]
    assert "api_key" not in rows[0]

    fetched = client.get(f"/v1.0/authentications/{body['id']}", headers=headers)
    assert fetched.status_code == 200
    assert fetched.get_json()["client_id"] == body["client_id"]
    singular = client.get(f"/v1.0/authentication/{body['id']}", headers=headers)
    assert singular.status_code == 200

    as_key = client.get("/v1.0/authentications", headers=_auth_headers(api_key))
    assert as_key.status_code == 200
    assert [row["id"] for row in as_key.get_json()] == [body["id"]]
    secrets = client.get("/v1.0/secrets", headers=_auth_headers(api_key))
    assert secrets.status_code == 200

    revoked = client.delete(f"/v1.0/authentications/{body['id']}", headers=headers)
    assert revoked.status_code == 200
    after = client.get("/v1.0/authentications", headers=headers)
    assert after.get_json() == []
    dead = client.get("/v1.0/authentications", headers=_auth_headers(api_key))
    assert dead.status_code == 401


def test_tenant_admin_can_mint_service_account(client, db_session):
    _user, token = _login_user(
        client, db_session, username="tenant-admin", groups=["t1:tenant-admin"], tenant_id="t1"
    )
    created = client.post(
        "/v1.0/authentications", json={"name": "ops"}, headers=_auth_headers(token)
    )
    assert created.status_code == 201


def test_viewer_can_read_but_not_create_service_accounts(client, db_session):
    _user, token = _login_user(
        client, db_session, username="viewer", groups=["t1:viewer"], tenant_id="t1"
    )
    headers = _auth_headers(token)
    listed = client.get("/v1.0/authentications", headers=headers)
    assert listed.status_code == 200
    created = client.post("/v1.0/authentications", json={"name": "nope"}, headers=headers)
    assert created.status_code == 403


def test_reviewer_cannot_manage_service_accounts(client, db_session):
    _user, token = _login_user(
        client, db_session, username="reviewer", groups=["t1:reviewer"], tenant_id="t1"
    )
    headers = _auth_headers(token)
    listed = client.get("/v1.0/authentications", headers=headers)
    assert listed.status_code == 200
    assert listed.get_json() == []
    created = client.post("/v1.0/authentications", json={"name": "nope"}, headers=headers)
    assert created.status_code == 403


def test_service_accounts_are_isolated_across_tenants(client, db_session):
    _user_a, token_a = _login_user(
        client, db_session, username="integrator-a", groups=["t1:integrator"], tenant_id="t1"
    )
    created = client.post(
        "/v1.0/authentications", json={"name": "t1-bot"}, headers=_auth_headers(token_a)
    )
    assert created.status_code == 201
    t1_id = created.get_json()["id"]
    t1_key = created.get_json()["api_key"]

    _user_b, token_b = _login_user(
        client, db_session, username="integrator-b", groups=["t2:integrator"], tenant_id="t2"
    )
    listed_b = client.get("/v1.0/authentications", headers=_auth_headers(token_b))
    assert listed_b.status_code == 200
    assert listed_b.get_json() == []
    missing = client.get(f"/v1.0/authentications/{t1_id}", headers=_auth_headers(token_b))
    assert missing.status_code == 404
    denied = client.delete(f"/v1.0/authentications/{t1_id}", headers=_auth_headers(token_b))
    assert denied.status_code in {403, 404}

    created_b = client.post(
        "/v1.0/authentications", json={"name": "t2-bot"}, headers=_auth_headers(token_b)
    )
    assert created_b.status_code == 201
    t2_id = created_b.get_json()["id"]

    from_key = client.get("/v1.0/authentications", headers=_auth_headers(t1_key))
    assert from_key.status_code == 200
    ids = [row["id"] for row in from_key.get_json()]
    assert ids == [t1_id]
    assert t2_id not in ids


def test_service_account_key_ignores_foreign_tenant_cookie(client, db_session):
    _user, token = _login_user(
        client, db_session, username="integrator", groups=["t1:integrator"], tenant_id="t1"
    )
    created = client.post(
        "/v1.0/authentications", json={"name": "ci-bot"}, headers=_auth_headers(token)
    )
    api_key = created.get_json()["api_key"]
    account_id = created.get_json()["id"]

    client.set_cookie(SELECTED_TENANT_COOKIE_NAME, "t2")
    listed = client.get("/v1.0/authentications", headers=_auth_headers(api_key))
    assert listed.status_code == 200
    assert [row["id"] for row in listed.get_json()] == [account_id]


def test_blank_name_is_rejected(client, db_session):
    _user, token = _login_user(
        client, db_session, username="integrator", groups=["t1:integrator"], tenant_id="t1"
    )
    created = client.post(
        "/v1.0/authentications", json={"name": "  "}, headers=_auth_headers(token)
    )
    assert created.status_code == 400
