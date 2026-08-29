"""Neutral, provider-agnostic domain objects for the auth seam.

The backend speaks only in these terms; a provider translates them to and from
its own vocabulary (for Keycloak: organizations, groups, realm roles, ...).

These object shapes are the contract both sides depend on: a provider must be
able to express its data in exactly these terms, and the backend never needs
to know more than this to operate on it.
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class TenantRef:
    """A tenant as a token/provider references it — never DB-canonicalized here.

    The backend resolves these raw references to the local canonical tenant row.
    """

    id: str | None = None
    alias: str | None = None
    name: str | None = None


@dataclass(frozen=True)
class Membership:
    """A user's membership in one tenant, with that tenant's neutral roles/groups.

    ``roles`` are neutral role names (see ``base.roles``); ``groups`` are neutral
    group identifiers *before* the backend applies tenant qualification.
    """

    tenant_ref: TenantRef
    roles: list[str] = field(default_factory=list)
    groups: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class VerifiedClaims:
    """The authoritative result of verifying a token.

    Everything request-time authorization needs comes from here — no per-request
    provider call. Only trustworthy because the token was cryptographically
    verified (JWKS) before this object was built.
    """

    subject: str
    issuer: str
    username: str | None = None
    email: str | None = None
    roles: list[str] = field(default_factory=list)
    memberships: list[Membership] = field(default_factory=list)
    # Verified JWT payload. Permanent bridge read directly by tenant-resolution
    # and identity-claims code alongside the typed fields above.
    jwt_claims: dict[str, object] = field(default_factory=dict, compare=False, repr=False)


@dataclass(frozen=True)
class TokenSet:
    """Tokens returned by an authorization-code exchange or refresh."""

    access_token: str
    refresh_token: str | None = None
    id_token: str | None = None
    expires_in: int | None = None
    refresh_expires_in: int | None = None


@dataclass(frozen=True)
class User:
    """A neutral directory user."""

    subject: str
    username: str | None = None
    email: str | None = None
    display_name: str | None = None


@dataclass(frozen=True)
class Tenant:
    """A neutral tenant as the provider knows it (pre DB-canonicalization)."""

    ref: TenantRef
    display_name: str | None = None


@dataclass(frozen=True)
class Role:
    """A neutral role name, optionally scoped to a tenant."""

    name: str
    tenant_ref: TenantRef | None = None


@dataclass(frozen=True)
class Group:
    """A neutral group identifier, optionally scoped to a tenant."""

    identifier: str
    tenant_ref: TenantRef | None = None
