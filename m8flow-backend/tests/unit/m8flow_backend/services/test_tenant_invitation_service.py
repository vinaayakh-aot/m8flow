"""Regression coverage for architecture review finding S2: create_invitation
and resend_invitation committed the invitation row (or the invitation's
rotated token) *before* attempting to send the email. email_service.send_email
raises on a genuine configured-SMTP failure (it only returns False, no raise,
in dev mode when SMTP isn't configured at all) -- so a transient SMTP outage
left a dangling, un-retryable invitation row behind (create), or silently
invalidated the invitation's still-usable existing link while never
delivering the new one (resend). Both now send before persisting.
"""

from __future__ import annotations

import time

import pytest
from flask import g

from m8flow_backend.integrations.auth.base.errors import UserNotFound
from m8flow_backend.models.m8flow_tenant import M8flowTenantModel, TenantStatus
from m8flow_backend.models.tenant_invitation import M8flowTenantInvitationModel, TenantInvitationStatus
from m8flow_backend.services import tenant_invitation_service


@pytest.fixture(autouse=True)
def _bind_request_scoped_session(app, db_session):
    with app.test_request_context("/"):
        g.db_session = db_session
        yield


@pytest.fixture(autouse=True)
def _fake_auth_provider(monkeypatch):
    """create_invitation/resend_invitation both check the shared-realm
    directory for an existing user with this email; a not-found result is
    the only path these tests need."""

    class _FakeProvider:
        def get_user(self, **_kwargs):
            raise UserNotFound("no such user")

    monkeypatch.setattr(tenant_invitation_service, "get_auth_provider", lambda: _FakeProvider())


def _seed_tenant(db_session, *, tenant_id: str = "t1") -> M8flowTenantModel:
    now = int(time.time())
    tenant = M8flowTenantModel(
        id=tenant_id,
        slug=tenant_id,
        name="Tenant One",
        status=TenantStatus.ACTIVE.value,
        created_at_in_seconds=now,
        updated_at_in_seconds=now,
    )
    db_session.add(tenant)
    db_session.commit()
    return tenant


def test_create_invitation_sends_before_persisting_the_row(db_session, monkeypatch):
    _seed_tenant(db_session)
    monkeypatch.setattr(tenant_invitation_service, "send_email", lambda *a, **k: True)

    result = tenant_invitation_service.create_invitation(
        "t1", "invitee@example.com", ["editor"], None, "admin"
    )

    assert result["status"] == "PENDING"
    row = db_session.query(M8flowTenantInvitationModel).filter_by(email="invitee@example.com").first()
    assert row is not None
    assert row.status == TenantInvitationStatus.PENDING


def test_create_invitation_does_not_persist_a_dangling_row_on_smtp_failure(db_session, monkeypatch):
    def _raise(*_a, **_k):
        raise ConnectionRefusedError("smtp down")

    monkeypatch.setattr(tenant_invitation_service, "send_email", _raise)
    _seed_tenant(db_session)

    with pytest.raises(ConnectionRefusedError):
        tenant_invitation_service.create_invitation(
            "t1", "invitee@example.com", ["editor"], None, "admin"
        )

    assert db_session.query(M8flowTenantInvitationModel).filter_by(email="invitee@example.com").count() == 0


def test_resend_invitation_does_not_rotate_the_token_on_smtp_failure(db_session, monkeypatch):
    tenant = _seed_tenant(db_session)
    monkeypatch.setattr(tenant_invitation_service, "send_email", lambda *a, **k: True)
    created = tenant_invitation_service.create_invitation(
        "t1", "invitee@example.com", ["editor"], None, "admin"
    )
    row = db_session.query(M8flowTenantInvitationModel).filter_by(id=created["id"]).one()
    original_token_hash = row.token_hash

    def _raise(*_a, **_k):
        raise ConnectionRefusedError("smtp down")

    monkeypatch.setattr(tenant_invitation_service, "send_email", _raise)

    with pytest.raises(ConnectionRefusedError):
        tenant_invitation_service.resend_invitation(tenant.id, row.id, "admin")

    db_session.expire_all()
    unchanged = db_session.query(M8flowTenantInvitationModel).filter_by(id=row.id).one()
    assert unchanged.token_hash == original_token_hash
    assert unchanged.status == TenantInvitationStatus.PENDING


def test_create_invitation_email_and_dev_link_use_designer_accept_url(db_session, monkeypatch):
    captured: dict[str, str] = {}

    def _capture(_email, _subject, html_body, text_body=None):
        captured["html"] = html_body
        captured["text"] = text_body or ""
        return False

    monkeypatch.setattr(tenant_invitation_service, "send_email", _capture)
    monkeypatch.delenv("M8FLOW_FRONTEND_BASE_URL", raising=False)
    monkeypatch.delenv("M8FLOW_APP_PUBLIC_BASE_URL", raising=False)
    monkeypatch.setenv("KEYCLOAK_HOSTNAME", "http://localhost:6842")
    _seed_tenant(db_session)

    result = tenant_invitation_service.create_invitation(
        "t1", "invitee@example.com", ["editor"], None, "admin"
    )

    link = result["invitation_link"]
    assert link.startswith("http://localhost:6853/accept-invitation?token=")
    assert link in captured["html"]
    assert link in captured["text"]
    assert "http://localhost:6841" not in captured["html"]
    assert "http://localhost:6842" not in captured["html"]
