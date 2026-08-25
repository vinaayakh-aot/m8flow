"""Abstract ``AuthProvider``: session/verify + directory read, plus typed capability accessors.

Method bodies raise ``NotImplementedError`` until later tickets fill them in.
Signatures may still be refined as each operation cluster moves (tickets 03–07).
"""
from __future__ import annotations

from abc import ABC

from m8flow_backend.integrations.auth.base.capabilities import SupportsDirectoryAdmin, SupportsProvisioning
from m8flow_backend.integrations.auth.base.errors import CapabilityNotSupported
from m8flow_backend.integrations.auth.base.models import Membership, TokenSet, User, VerifiedClaims


class AuthProvider(ABC):
    """Provider-agnostic auth seam. The backend never sees a vendor vocabulary here."""

    def build_login_url(
        self,
        *,
        redirect_uri: str,
        state: str,
        authentication_identifier: str,
        nonce: str | None = None,
        prompt: str | None = None,
    ) -> str:
        raise NotImplementedError

    def exchange_code(
        self,
        *,
        code: str,
        redirect_uri: str,
        authentication_identifier: str,
    ) -> TokenSet:
        raise NotImplementedError

    def refresh(self, *, refresh_token: str, authentication_identifier: str) -> TokenSet:
        raise NotImplementedError

    def build_logout_url(
        self,
        *,
        authentication_identifier: str,
        redirect_uri: str | None = None,
        id_token_hint: str | None = None,
    ) -> str:
        raise NotImplementedError

    def verify_token(self, token: str) -> VerifiedClaims:
        raise NotImplementedError

    def get_user(self, *, username: str, authentication_identifier: str) -> User:
        raise NotImplementedError

    def search_users(
        self,
        *,
        query: str,
        authentication_identifier: str,
        limit: int = 50,
    ) -> list[User]:
        raise NotImplementedError

    def list_memberships(self, *, username: str) -> list[Membership]:
        raise NotImplementedError

    @property
    def directory_admin(self) -> SupportsDirectoryAdmin:
        raise CapabilityNotSupported("directory_admin")

    @property
    def provisioning(self) -> SupportsProvisioning:
        raise CapabilityNotSupported("provisioning")
