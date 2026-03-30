# m8flow-core

Core domain models, services, multi-tenancy logic, and pluggable authentication for m8flow.

**Version:** 0.1.0
**License:** Apache-2.0
**Python:** >=3.11, <3.13

---

## Overview

`m8flow-core` is a standalone Python library extracted from the `extensions/m8flow-backend` adapter. It contains all logic that is **not** specific to spiff-arena, making it reusable in standalone deployments, alternative BPMN engines, and future integrations.

The library provides:

- **Multi-tenancy** — per-request tenant context via `ContextVar`, tenant-scoped SQLAlchemy models, Row-Level Security migrations
- **Template management** — full CRUD with versioning, visibility tiers, file storage, ZIP export/import
- **Pluggable authentication** — protocol-based `IdentityProvider` with a Keycloak adapter and an Auth0 stub
- **Pluggable adapters** — swap error factories and authorization adapters between standalone and spiff-arena modes
- **Alembic migrations** — owns the `m8flow_*` table schema independently of spiffworkflow migrations
- **ASGI middleware** — `AsgiTenantContextMiddleware` for automatic per-request tenant injection

---

## Why It Was Extracted

Previously all of this code lived inside `extensions/m8flow-backend`, which is tightly coupled to `spiffworkflow-backend`. Extracting it to `m8flow-core` enables:

1. **Reuse without spiff-arena** — deploy a lightweight standalone server using only SQLAlchemy and Flask
2. **Independent versioning** — publish and pin `m8flow-core` separately from the spiff-arena extension
3. **Cleaner separation of concerns** — domain logic lives in the library; spiff-arena orchestration lives in the adapter

---

## What Was Moved Into m8flow-core

The following files were **moved** from `extensions/m8flow-backend/src/m8flow_backend/` into `m8flow-core/src/m8flow_core/`:

| Original location | m8flow-core location | Key exports |
|---|---|---|
| `models/audit_mixin.py` | `models/audit_mixin.py` | `AuditDateTimeMixin` |
| `models/m8flow_tenant.py` | `models/tenant.py` | `M8flowTenantModel`, `TenantStatus` |
| `models/tenant_scoped.py` | `models/tenant_scoped.py` | `TenantScoped`, `M8fTenantScopedMixin` |
| `models/template.py` | `models/template.py` | `TemplateModel`, `TemplateVisibility` |
| `models/process_model_template.py` | `models/process_model_template.py` | `ProcessModelTemplateModel` |
| `models/nats_token.py` | `models/nats_token.py` | `NatsTokenModel` |
| `tenancy.py` | `tenancy.py` | All tenant context functions |
| `config.py` (Keycloak section) | `auth/adapters/keycloak_config.py` | `keycloak_url()`, `realm_template_path()`, etc. |
| `services/keycloak_service.py` (core) | `auth/adapters/keycloak.py` | `KeycloakIdentityProvider` |
| `services/tenant_service.py` | `services/tenant_service.py` | `TenantService` |
| `services/template_service.py` (base logic) | `services/template_service.py` | `TemplateService` (base class) |
| `services/template_authorization_service.py` | `services/template_authorization_service.py` | `TemplateAuthorizationService` |
| `services/template_storage_service.py` | `services/template_storage_service.py` | `FilesystemTemplateStorageService` |
| `services/asgi_tenant_context_middleware.py` | `middleware/asgi.py` | `AsgiTenantContextMiddleware` |
| `services/tenant_scoping_patch.py` (logic) | `patches/registry.py` | `PatchSpec`, `apply_patch_specs` |

### New modules added in m8flow-core

These abstractions did not exist before the extraction; they were introduced to make the library pluggable:

| Module | Purpose |
|---|---|
| `db/registry.py` | Lazy `_DbProxy` — late-binds the real SQLAlchemy `db` instance |
| `auth/base.py` | `TenantProvisioner`, `TokenManager`, `IdentityProvider` protocols |
| `auth/models.py` | `TenantRealm`, `AuthUser`, `AuthToken`, `AuthConfig` dataclasses |
| `auth/registry.py` | `get_provider()` / `_set_provider()` singleton |
| `auth/adapters/auth0.py` | Auth0 placeholder (raises `NotImplementedError`) |
| `adapters/base.py` | `ApiErrorFactory`, `AuthorizationAdapter` protocols |
| `adapters/standalone.py` | `M8flowApiError`, `StandaloneErrorFactory`, `StandaloneAuthzAdapter` |
| `adapters/spiff_arena.py` | `SpiffArenaErrorFactory`, `SpiffArenaAuthzAdapter` |
| `config/env_mapper.py` | `M8FLOW_TO_SPIFF` dict, `apply_m8flow_env_mapping()` |
| `models/base_enum.py` | `M8flowEnum` with `.list()` classmethod |

### What stayed in m8flow-backend

The following remain in `extensions/m8flow-backend` because they depend on spiff-arena internals:

- `services/template_service.py` — subclass of core `TemplateService` that adds `create_process_model_from_template()` (uses `ProcessModelService`, `SpecFileService`, git commit)
- All 40+ process/task/BPMN models that wrap spiffworkflow tables
- All spiffworkflow service patches (auth, authorization, file system, CORS, etc.)
- Route controllers (templates, tenants, NATS tokens, Keycloak)
- Celery worker configuration

### Backward-compatibility stubs

The following files in `m8flow-backend` are kept as thin re-export stubs so that existing call sites continue to work without import changes:

```
m8flow_backend/tenancy.py                          → re-exports from m8flow_core.tenancy
m8flow_backend/config.py                           → re-exports from m8flow_core.auth.adapters.keycloak_config
m8flow_backend/services/tenant_service.py          → re-exports TenantService
m8flow_backend/services/template_storage_service.py → re-exports storage classes
m8flow_backend/services/template_authorization_service.py → re-exports TemplateAuthorizationService
```

---

## Package Structure

```
m8flow-core/
├── pyproject.toml
├── migrations/                         # Alembic migrations (12 versions)
│   ├── env.py
│   ├── migrate.py
│   ├── script.py.mako
│   └── versions/
└── src/m8flow_core/
    ├── __init__.py                     # configure_db(), configure_adapters(), configure_auth_provider()
    ├── tenancy.py                      # Tenant ContextVar, path filtering, health check
    ├── config/
    │   └── env_mapper.py              # M8FLOW_* → SPIFFWORKFLOW_* env var mapping
    ├── db/
    │   └── registry.py               # Lazy db proxy, configure_db()
    ├── models/
    │   ├── audit_mixin.py            # AuditDateTimeMixin (created/updated timestamps)
    │   ├── base_enum.py              # M8flowEnum base class
    │   ├── tenant.py                 # M8flowTenantModel, TenantStatus
    │   ├── tenant_scoped.py          # TenantScoped marker, M8fTenantScopedMixin
    │   ├── template.py               # TemplateModel, TemplateVisibility
    │   ├── process_model_template.py # ProcessModelTemplateModel
    │   └── nats_token.py             # NatsTokenModel
    ├── auth/
    │   ├── base.py                   # TenantProvisioner, TokenManager, IdentityProvider protocols
    │   ├── models.py                 # TenantRealm, AuthUser, AuthToken, AuthConfig
    │   ├── registry.py               # get_provider(), _set_provider()
    │   └── adapters/
    │       ├── keycloak.py           # KeycloakIdentityProvider
    │       ├── keycloak_config.py    # keycloak_url(), realm_template_path(), etc.
    │       └── auth0.py              # Auth0 stub (not yet implemented)
    ├── adapters/
    │   ├── base.py                   # ApiErrorFactory, AuthorizationAdapter protocols
    │   ├── standalone.py             # M8flowApiError, Standalone factories
    │   └── spiff_arena.py            # SpiffArena factories (delegates to spiffworkflow)
    ├── middleware/
    │   └── asgi.py                   # AsgiTenantContextMiddleware
    ├── patches/
    │   ├── boot_phase.py             # BootPhase enum, require_at_least()
    │   └── registry.py               # PatchSpec dataclass, apply_patch_specs()
    └── services/
        ├── tenant_service.py         # TenantService
        ├── template_service.py       # TemplateService base class (~700 lines)
        ├── template_authorization_service.py
        └── template_storage_service.py
```

---

## Installation

**Standalone (no spiff-arena dependency):**
```bash
pip install m8flow-core
```

**With spiff-arena integration (adds `spiffworkflow-backend` as a dependency):**
```bash
pip install "m8flow-core[spiff-arena]"
```

**Local development (editable install):**
```bash
pip install -e ./m8flow-core
# or with spiff extras:
pip install -e "./m8flow-core[spiff-arena]"
```

---

## Initialization

m8flow-core uses a lazy initialization pattern. Three configuration calls must be made **before** any model or service is used, typically during the application boot sequence.

### With spiff-arena

```python
import m8flow_core
from spiffworkflow_backend.models.db import db, SpiffworkflowBaseDBModel
from m8flow_core.adapters.spiff_arena import SpiffArenaErrorFactory, SpiffArenaAuthzAdapter
from m8flow_core.auth.adapters.keycloak import KeycloakIdentityProvider

# 1. Bind SQLAlchemy db instance and base model class
m8flow_core.configure_db(db, SpiffworkflowBaseDBModel)

# 2. Register error factory and authorization adapter
m8flow_core.configure_adapters(SpiffArenaErrorFactory(), SpiffArenaAuthzAdapter())

# 3. Register the identity/auth provider
m8flow_core.configure_auth_provider(KeycloakIdentityProvider.from_env())
```

These three calls must happen after spiffworkflow-backend imports are safe but before `create_app()`. In this repo that happens in `extensions/startup/sequence.py:_prepare_pre_app_boot()`.

### Standalone (without spiff-arena)

```python
import m8flow_core
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase
from m8flow_core.adapters.standalone import StandaloneErrorFactory, StandaloneAuthzAdapter

class Base(DeclarativeBase):
    pass

engine = create_engine("postgresql+psycopg2://user:pass@host/dbname")

# Provide a Flask-SQLAlchemy-compatible db object and your base model
m8flow_core.configure_db(your_db_instance, Base)
m8flow_core.configure_adapters(StandaloneErrorFactory(), StandaloneAuthzAdapter())
# configure_auth_provider() optional in standalone mode
```

---

## Database Migrations

m8flow-core owns an independent Alembic migration tree. The following tables are managed:

| Table | Description |
|---|---|
| `m8flow_tenant` | Tenant registry — id, name, slug, status, audit timestamps |
| `m8flow_templates` | Template library — key, version, name, tags, category, visibility, files (JSON), soft-delete |
| `m8flow_process_model_template` | Provenance — tracks which template each spiff process model was created from |
| `m8flow_nats_tokens` | Per-tenant NATS authentication tokens |

Migration history (chronological):

1. `1518b05122bc` — create `m8flow_tenant` table
2. `2cfce680c743` — update tenant table columns
3. `ce8f052197c2` — add tenant scoping
4. `b1c2d3e4f5a6` — add template files JSON column
5. `22aaaa61d8f6` — add `m8flow_templates` table
6. `c3d4e5f6a7b8` — add `m8flow_process_model_template` table
7. `b8837274af96` — add `m8flow_nats_tokens` table
8. `d2b8f0d1a4c5` — seed default tenant row
9. `f6a7b8c9d0e1` — add tenant scoping to additional tables
10. `a750bbb5c234` — add PostgreSQL Row-Level Security policies
11. `9f2d0e4c8abc` — unify tenant/template timestamps to epoch seconds

### Running migrations

The `extensions/startup/migrations.py` loader prefers `m8flow-core/migrations/` and falls back to `extensions/m8flow-backend/migrations/` for backward compatibility. Migrations run automatically at startup when `M8FLOW_RUN_MIGRATIONS=true`.

To run migrations manually:
```bash
cd m8flow-core
python migrations/migrate.py upgrade head
```

---

## Multi-Tenancy

### Tenant context

The active tenant for each request is stored in a `ContextVar` and does not cross async task boundaries:

```python
from m8flow_core.tenancy import (
    get_tenant_id,
    set_context_tenant_id,
    get_context_tenant_id,
    create_tenant_if_not_exists,
    ensure_tenant_exists,
)

# Set and read the current request's tenant
set_context_tenant_id("acme-corp")
tenant_id = get_tenant_id()      # "acme-corp"
                                 # falls back to DEFAULT_TENANT_ID if not set

# Ensure a tenant row exists (creates it if missing)
create_tenant_if_not_exists("acme-corp", name="Acme Corp", slug="acme-corp")
```

### Tenant-scoped models

Any SQLAlchemy model that inherits `M8fTenantScopedMixin` automatically gets an `m8f_tenant_id` column with a foreign key to `m8flow_tenant`:

```python
from m8flow_core.models.tenant_scoped import M8fTenantScopedMixin, TenantScoped
from spiffworkflow_backend.models.db import SpiffworkflowBaseDBModel

class MyModel(M8fTenantScopedMixin, TenantScoped, SpiffworkflowBaseDBModel):
    __tablename__ = "my_table"
    id: int = db.Column(db.Integer, primary_key=True)
    # m8f_tenant_id is injected by M8fTenantScopedMixin
```

All ~40 spiffworkflow process/task/BPMN models in `m8flow-backend` use this pattern, so every spiff table is automatically tenant-scoped.

### ASGI middleware

`AsgiTenantContextMiddleware` (in `m8flow_core.middleware.asgi`) wraps the ASGI app and sets the tenant context on every request by extracting the tenant claim from the JWT Bearer token or session cookie. It is installed in `extensions/startup/sequence.py:_wrap_asgi_if_needed()`.

### Path exemptions

Paths under `/.well-known`, `/v1.0/login`, `/health`, etc. are exempt from tenant context requirements. The full list is configurable via `TENANT_CONTEXT_EXEMPT_PATH_PREFIXES` in `m8flow_core/tenancy.py`.

---

## Template Management

`TemplateService` (in `m8flow_core.services.template_service`) manages the full template lifecycle:

| Operation | Method |
|---|---|
| Create | `TemplateService.create_template()` / `create_template_with_files()` |
| Read | `get_template()`, `get_template_by_id()` |
| List | `list_templates()` — paginated, supports filter by category, tag, visibility, search |
| Update | `update_template()`, `update_template_by_id()` |
| Delete | `delete_template_by_id()` — soft delete via `is_deleted` flag |
| Files | `get_file_content()`, `update_file_content()`, `delete_file_from_template()` |
| Export | `export_template_zip()` |
| Import | `import_template_from_zip()` |

**Visibility tiers** (`TemplateVisibility`):

- `PRIVATE` — visible only to the creating user and tenant admins
- `TENANT` — visible to all users within the same tenant
- `PUBLIC` — visible to all users across all tenants

**Versioning:** Templates are versioned with a `V`-prefixed scheme (`V1`, `V2`, …). A new version is created automatically on update rather than mutating the existing record.

**File storage** is handled by `FilesystemTemplateStorageService`, which stores files at:
```
{M8FLOW_TEMPLATES_STORAGE_DIR}/{tenant_id}/{template_key}/{version}/{file_name}
```

### spiff-arena extension

`m8flow_backend.services.template_service.TemplateService` subclasses the core and adds `create_process_model_from_template()`. This method:

1. Retrieves the template and validates visibility
2. Creates a spiff-arena `ProcessModelInfo` via `ProcessModelService`
3. Copies all template files via `SpecFileService`, transforming BPMN/DMN IDs to match the new process model identifier
4. Records provenance in `ProcessModelTemplateModel`
5. Commits and pushes to git via `_commit_and_push_to_git`

---

## Authentication

m8flow-core defines a protocol-based `IdentityProvider` interface in `m8flow_core.auth.base`:

```python
class IdentityProvider(TenantProvisioner, TokenManager, Protocol):
    pass
```

### Keycloak (default)

`KeycloakIdentityProvider.from_env()` reads configuration from environment variables and provides:

- `provision_tenant(tenant)` — creates a Keycloak realm for the tenant
- `deprovision_tenant(tenant_id)` — removes the realm
- `create_user(tenant_id, user)` — creates a user in the tenant's realm
- `get_login_url(tenant_id, redirect_uri)` — returns the OIDC authorization URL
- `validate_token(token, tenant_id)` — validates a JWT against the tenant's realm

### Auth0

`Auth0IdentityProvider` is a placeholder that raises `NotImplementedError`. It is reserved for a future implementation.

### Custom providers

Implement the `IdentityProvider` protocol and register it:

```python
from m8flow_core.auth.registry import _set_provider

_set_provider(MyCustomIdentityProvider())
```

---

## Integration with SpiffWorkflow / Spiff Arena

### Architecture

```
┌──────────────────────────────────────────────────────────┐
│                  m8flow  (Application)                   │
├──────────────────────────────────────────────────────────┤
│          extensions/m8flow-backend  (Adapter)            │
│   - Patches spiffworkflow_backend services               │
│   - Subclasses TemplateService for process model ops     │
│   - Route controllers (templates, tenants, NATS, KC)     │
├────────────────────────┬─────────────────────────────────┤
│  m8flow-core           │  spiffworkflow-backend           │
│  (domain + infra)      │  (BPMN engine + REST API)        │
│  - Tenant models       │  - ProcessInstanceModel          │
│  - Template CRUD       │  - TaskModel, HumanTask, etc.    │
│  - Auth providers      │  - SpecFileService               │
│  - NATS tokens         │  - ProcessModelService           │
│  - Migrations          │  - AuthorizationService          │
└────────────────────────┴─────────────────────────────────┘
```

### Integration points

**1. Shared SQLAlchemy instance**

`m8flow_core.configure_db(db, SpiffworkflowBaseDBModel)` binds m8flow-core to the exact same `db` session that spiffworkflow-backend uses. All `m8flow_*` tables join the same metadata object, so they participate in the same transactions.

**2. Tenant scoping on spiff models**

Every spiffworkflow model in `m8flow-backend` inherits `M8fTenantScopedMixin` from m8flow-core, adding `m8f_tenant_id` as a regular column. The tenant scoping patch (`tenant_scoping_patch.py`) automatically injects the current tenant ID into queries.

**3. TemplateService subclassing**

```python
# m8flow_backend/services/template_service.py
from m8flow_core.services.template_service import TemplateService as _CoreTemplateService

class TemplateService(_CoreTemplateService):
    @classmethod
    def create_process_model_from_template(cls, template_id, process_group_id, ...):
        # spiff-arena-specific: uses ProcessModelService, SpecFileService, git commit
        ...
```

**4. Authorization delegation**

`SpiffArenaAuthzAdapter.user_has_permission(user, permission, resource)` delegates directly to `spiffworkflow_backend.services.authorization_service.AuthorizationService`, so m8flow-core respects the same permissions model as spiff-arena.

**5. Error type delegation**

`SpiffArenaErrorFactory` wraps `spiffworkflow_backend.exceptions.api_error.ApiError`, so HTTP errors raised inside m8flow-core services are the correct type for the connexion/Flask error handler when running inside spiff-arena.

**6. Environment variable mapping**

`apply_m8flow_env_mapping()` translates `M8FLOW_*` variables to their `SPIFFWORKFLOW_*` equivalents at startup. This lets operators configure everything with the `M8FLOW_` prefix regardless of which layer actually reads the variable.

**7. Boot sequence**

`extensions/startup/sequence.py` orchestrates startup in strict order:

```
harden_logging()
apply_m8flow_env_mapping()
bootstrap()                       # model overrides, pre-app patches
configure_db(db, Base)            # bind m8flow-core to spiff db
configure_adapters(...)           # spiff-arena error factory + authz
configure_auth_provider(...)      # Keycloak
load_migration_runner()           # load m8flow-core/migrations
assert_model_identity()           # fail-fast identity check
create_spiff_app()                # spiffworkflow create_app()
bootstrap_after_app(flask_app)    # post-app patches
run_migrations_if_enabled(...)    # upgrade m8flow_* tables
configure_permissions_yml(...)
configure_templates_dir(...)
register_tenant_resolution(...)
load_sample_templates(...)
wrap AsgiTenantContextMiddleware
```

---

## Environment Variables

| Variable | Default | Purpose |
|---|---|---|
| `M8FLOW_DEFAULT_TENANT_ID` | `"default"` | Fallback tenant when no tenant context is set |
| `M8FLOW_TENANT_CLAIM` | `"m8flow_tenant_id"` | JWT claim name that carries the tenant ID |
| `M8FLOW_TEMPLATES_STORAGE_DIR` | *(uses spiff BPMN dir)* | Filesystem root for template file storage |
| `M8FLOW_KEYCLOAK_SERVER_URL` | — | Keycloak base URL (e.g. `https://auth.example.com`) |
| `M8FLOW_KEYCLOAK_ADMIN_USER` | — | Keycloak master realm admin username |
| `M8FLOW_KEYCLOAK_ADMIN_PASSWORD` | — | Keycloak master realm admin password |
| `M8FLOW_KEYCLOAK_REALM_TEMPLATE_PATH` | — | Path to realm JSON template for tenant provisioning |
| `M8FLOW_KEYCLOAK_SPOKE_CLIENT_ID` | — | Client ID for spoke realm JWT assertions |
| `M8FLOW_KEYCLOAK_SPOKE_CLIENT_SECRET` | — | Client secret for spoke realm JWT assertions |
| `M8FLOW_NATS_TOKEN_SALT` | — | Salt used when generating per-tenant NATS tokens |
| `M8FLOW_RUN_MIGRATIONS` | `"false"` | Set to `"true"` to auto-run migrations at startup |

All `M8FLOW_*` variables that have `SPIFFWORKFLOW_*` equivalents are mapped automatically by `apply_m8flow_env_mapping()`.

---

## Testing

```bash
# Unit tests for m8flow-core in isolation
cd m8flow-core
pip install -e ".[test]"
pytest

# Unit tests for m8flow-backend (exercises m8flow-core integration)
cd extensions/m8flow-backend
pytest tests/unit/
```
