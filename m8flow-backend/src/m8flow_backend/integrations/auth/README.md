# Auth provider seam

This package is the **provider-agnostic auth seam**. The rest of the backend
authenticates users, verifies tokens, and reads/writes the identity directory
*only* through the neutral interface defined here — it never sees a vendor
vocabulary (Keycloak organizations, realm roles, groups, ...) directly.

```
integrations/auth/
├── base/            # the neutral contract (interface + domain objects)
│   ├── provider.py      # AuthProvider (the interface concrete providers implement)
│   ├── models.py        # neutral domain objects the seam speaks in
│   ├── capabilities.py  # optional capability protocols
│   ├── roles.py         # canonical neutral role vocabulary
│   └── errors.py        # neutral error hierarchy raised across the seam
├── factory.py       # register_auth_provider / get_auth_provider
└── keycloak/        # the reference implementation (KeycloakAuthProvider)
```

Call sites resolve the active provider with `get_auth_provider()` and speak only
in `base` terms:

```python
from m8flow_backend.integrations.auth import get_auth_provider

claims = get_auth_provider().verify_token(access_token)
```

## The contract (`base/`)

### `AuthProvider` (`base/provider.py`)

Abstract base whose methods default to `raise NotImplementedError`; a concrete
provider overrides every method with a real implementation. Three groups:

- **Session / OIDC:** `build_login_url`, `exchange_code`, `refresh`,
  `build_logout_url`
- **Token + directory read:** `verify_token → VerifiedClaims`, `get_user`,
  `search_users`, `list_memberships`
- **Optional capability accessors (properties):** `directory_admin` and
  `provisioning`. Each raises `CapabilityNotSupported` by default, so callers use
  the typed accessors rather than sniffing with `hasattr`.

### Neutral domain objects (`base/models.py`)

Frozen dataclasses that form the contract both sides depend on. A provider must
be able to express its data in exactly these terms, and the backend never needs
to know more than this:

| Object | Purpose |
|--------|---------|
| `TenantRef` | A tenant as a token/provider references it (`id` / `alias` / `name`) — **never** DB-canonicalized here; the backend resolves it to the local canonical row. |
| `Membership` | A user's membership in one tenant, with that tenant's neutral `roles` and `groups`. |
| `VerifiedClaims` | Authoritative result of verifying a token. Everything request-time authz needs — no per-request provider call. Includes the verified `jwt_claims` payload. |
| `TokenSet` | Tokens from an authorization-code exchange or refresh. |
| `User` | A neutral directory user. |
| `Tenant` | A neutral tenant as the provider knows it (pre DB-canonicalization). |
| `Role` / `Group` | Neutral role/group identifiers, optionally tenant-scoped. |

### Optional capabilities (`base/capabilities.py`)

Two `Protocol`s a provider may support:

- **`SupportsDirectoryAdmin`** — mutating directory operations (create/delete
  users, add/remove members, assign roles, tenant + group CRUD).
- **`SupportsProvisioning`** — tenant-realm and client provisioning
  (Keycloak-heavy; optional on the seam).

Expose them from the `directory_admin` / `provisioning` properties on your
provider. Callers reach them through those accessors, which raise
`CapabilityNotSupported` when a provider does not implement them.

### Roles (`base/roles.py`)

m8flow's own provider-independent role vocabulary. A provider translates between
these names and its realization of them.

- `VALID_TENANT_ROLE_NAMES`: `tenant-admin`, `editor`, `integrator`, `reviewer`,
  `submitter`, `viewer`
- `SUPER_ADMIN_ROLE`: `super-admin` (global, non-tenant-scoped)
- Helpers: `normalize_tenant_role_name`, `normalize_tenant_role_names`

### Errors (`base/errors.py`)

Providers raise only these; no HTTP status codes or provider-native payloads
leak past the seam. The backend maps them to its own `ApiError` responses.

`AuthProviderError` (base) → `TokenInvalid`, `UserNotFound`, `TenantNotFound`,
`CapabilityNotSupported`, `ProviderUnavailable`.

## Selecting a provider (`factory.py`)

The process holds one provider instance (lazy singleton).

- Selection key: **`M8FLOW_AUTH_PROVIDER`** env var (default `keycloak`).
- `register_auth_provider(name, factory)` registers (or replaces) a provider
  factory under `name`.
- `get_auth_provider()` returns the process-wide active provider.
- `reset_auth_provider()` drops the cached instance (used by tests).

Keycloak is auto-registered as a builtin in `factory._ensure_builtins`.

## Authoring a new provider

Use `keycloak/` as the worked reference: `KeycloakAuthProvider` subclasses
`AuthProvider` and delegates each method to focused helper modules (`oidc`,
`directory`, `groups`, `tenants`, `jwks`, `provisioning`, ...), keeping the
provider class a thin translation layer.

1. **Subclass `AuthProvider`** and implement the session/verify/directory-read
   methods. Accept and return only `base.models` objects, and raise only
   `base.errors`. Keep vendor vocabulary inside your provider package.
2. **Optional capabilities:** if your provider mutates the directory or
   provisions tenants, implement the `SupportsDirectoryAdmin` /
   `SupportsProvisioning` protocols and return them from the `directory_admin` /
   `provisioning` properties.
3. **Register a factory:**

   ```python
   from m8flow_backend.integrations.auth import register_auth_provider
   from myorg.auth import MyAuthProvider

   register_auth_provider("myprovider", MyAuthProvider)
   ```

4. **Select it** at runtime with `M8FLOW_AUTH_PROVIDER=myprovider`. All call
   sites continue to use `get_auth_provider()` unchanged.

### Rules to preserve

- The backend depends on the neutral contract, not your vendor. Do not leak
  vendor types, HTTP status codes, or native payloads past the seam.
- `TenantRef` is a raw reference — resolving it to the local canonical tenant row
  is the backend's job, not the provider's.
- `VerifiedClaims` must be built only from a cryptographically verified token; it
  is treated as authoritative for request-time authorization.
- Callers must not `hasattr`-sniff capabilities — always go through the typed
  accessors.
