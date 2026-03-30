"""
Pure dataclasses for the pluggable auth system.

These are provider-agnostic and shared across all auth adapters.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class TenantRealm:
    """Identity provider realm/tenant configuration."""
    tenant_id: str
    tenant_name: str
    slug: str
    frontend_redirect_uri: str | None = None
    backend_redirect_uri: str | None = None
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass
class AuthUser:
    """Minimal user representation for identity provider operations."""
    username: str
    email: str | None = None
    first_name: str | None = None
    last_name: str | None = None
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass
class AuthToken:
    """Decoded token claims."""
    sub: str
    tenant_id: str | None = None
    username: str | None = None
    email: str | None = None
    roles: list[str] = field(default_factory=list)
    raw_claims: dict[str, Any] = field(default_factory=dict)


@dataclass
class AuthConfig:
    """Auth provider configuration (populated from environment or DB)."""
    issuer_url: str
    client_id: str
    client_secret: str | None = None
    discovery_url: str | None = None
    extra: dict[str, Any] = field(default_factory=dict)
