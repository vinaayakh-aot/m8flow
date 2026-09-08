"""F-05: the bootstrap group-identifier fallback must stay narrow.

Before F-05, `_group_identifier_fallback` granted any `:editor`/`:tenant-admin`
group access to every path and method, with no tenant-prefix check. It is now
scoped to read-only onboarding/tasks and to groups whose tenant prefix matches
the request's active tenant. These tests exercise the fallback directly (no DB
grants), so they prove the fallback boundary itself, not m8flow.yml.
"""

from __future__ import annotations

from types import SimpleNamespace

from flask import g

from m8flow_backend.authorization import _group_identifier_fallback
from m8flow_backend.identity import ensure_tenant


def _user(*identifiers: str) -> SimpleNamespace:
    return SimpleNamespace(groups=[SimpleNamespace(identifier=i) for i in identifiers])


def _bind(app, db_session, tenant_id: str):
    ensure_tenant(db_session, tenant_id=tenant_id, slug=tenant_id)
    db_session.commit()
    ctx = app.test_request_context(f"/v1.0/{tenant_id}")
    ctx.push()
    g.db_session = db_session
    g.m8flow_tenant_id = tenant_id
    return ctx


def test_grants_onboarding_read_for_active_tenant_member(app, db_session):
    ctx = _bind(app, db_session, "t1")
    try:
        assert _group_identifier_fallback(_user("t1:editor"), "/onboarding", "read") is True
        assert _group_identifier_fallback(_user("t1:reviewer"), "/tasks", "read") is True
    finally:
        ctx.pop()


def test_denies_non_read_even_on_tasks(app, db_session):
    ctx = _bind(app, db_session, "t1")
    try:
        assert _group_identifier_fallback(_user("t1:editor"), "/tasks/1/claim", "update") is False
        assert _group_identifier_fallback(_user("t1:editor"), "/tasks/1/complete", "create") is False
    finally:
        ctx.pop()


def test_denies_paths_outside_onboarding_and_tasks(app, db_session):
    ctx = _bind(app, db_session, "t1")
    try:
        assert _group_identifier_fallback(_user("t1:editor"), "/process-instances", "read") is False
        assert _group_identifier_fallback(_user("t1:tenant-admin"), "/secrets", "read") is False
    finally:
        ctx.pop()


def test_denies_group_from_a_different_tenant(app, db_session):
    ctx = _bind(app, db_session, "t1")
    try:
        # A group scoped to another tenant must not authorize the active tenant.
        assert _group_identifier_fallback(_user("t2:editor"), "/onboarding", "read") is False
    finally:
        ctx.pop()


def test_denies_when_no_active_tenant_bound(app, db_session):
    ctx = app.test_request_context("/v1.0/onboarding")
    ctx.push()
    try:
        g.db_session = db_session
        # No g.m8flow_tenant_id bound -> cannot scope -> deny.
        assert _group_identifier_fallback(_user("t1:editor"), "/onboarding", "read") is False
    finally:
        ctx.pop()
