"""Seed a running m8flow stack with the Northwind Traders perf tenant.

    python3 perf/seed/seed.py [--scale N] [--env-file .env]

Idempotent: every step checks before it writes, so re-running repairs a
partial seed instead of duplicating it. Uses only the standard library and
public APIs (Keycloak admin REST for users, the backend API for everything
else), never the databases directly.

Steps: tenant organization -> Keycloak users -> org membership + groups ->
group role grants ->
first sign-in per user ->
connector profile -> process groups -> template import -> process models
from templates -> stand-alone connector models -> publish.

Configuration (env vars, falling back to --env-file, then local defaults):
  M8FLOW_BACKEND_BASE_URL                 http://localhost:6840
  M8FLOW_KEYCLOAK_URL                     http://localhost:6842
  M8FLOW_KEYCLOAK_SHARED_REALM            m8flow
  M8FLOW_KEYCLOAK_SPOKE_CLIENT_ID         m8flow-backend
  M8FLOW_KEYCLOAK_MASTER_CLIENT_SECRET    (required; read from .env)
  KEYCLOAK_ADMIN / KEYCLOAK_ADMIN_PASSWORD           admin / admin
  KEYCLOAK_SUPER_ADMIN_USER / _PASSWORD              super-admin / super-admin
  PERF_SEED_PASSWORD                      password for seeded users (default: the username)
  PERF_SEED_PG_DSN                        postgres_v2 profile DSN (default: m8flow-db from POSTGRES_* in .env)
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent
GENERATED = HERE / "generated"

sys.path.insert(0, str(HERE))
from templates import all_templates


# --------------------------------------------------------------------------- config
def load_env_file(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.is_file():
        return values
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


class Config:
    def __init__(self, env_file: Path) -> None:
        file_env = load_env_file(env_file)

        def get(key: str, default: str | None = None) -> str | None:
            return os.environ.get(key) or file_env.get(key) or default

        self.backend = get("M8FLOW_BACKEND_BASE_URL", "http://localhost:6840").rstrip("/")
        self.keycloak = get("M8FLOW_KEYCLOAK_URL", "http://localhost:6842").rstrip("/")
        self.realm = get("M8FLOW_KEYCLOAK_SHARED_REALM", "m8flow")
        self.client_id = get("M8FLOW_KEYCLOAK_SPOKE_CLIENT_ID", "m8flow-backend")
        self.client_secret = get("M8FLOW_KEYCLOAK_SPOKE_CLIENT_SECRET") or get("M8FLOW_KEYCLOAK_MASTER_CLIENT_SECRET")
        self.kc_admin = get("KEYCLOAK_ADMIN", "admin")
        self.kc_admin_password = get("KEYCLOAK_ADMIN_PASSWORD", "admin")
        self.super_admin = get("KEYCLOAK_SUPER_ADMIN_USER", "super-admin")
        self.super_admin_password = get("KEYCLOAK_SUPER_ADMIN_PASSWORD", "super-admin")
        self.user_password = get("PERF_SEED_PASSWORD")
        self.get = get
        if not self.client_secret:
            raise SystemExit(f"M8FLOW_KEYCLOAK_MASTER_CLIENT_SECRET is not set (env or {env_file}).")


# --------------------------------------------------------------------------- http
class HttpError(Exception):
    def __init__(self, status: int, body: str, url: str) -> None:
        super().__init__(f"{status} {url}: {body[:400]}")
        self.status = status
        self.body = body


def request(method: str, url: str, *, token: str | None = None, json_body=None, form=None, data: bytes | None = None,
            headers: dict[str, str] | None = None, cookie: str | None = None, timeout: float = 60):
    hdrs = dict(headers or {})
    if token:
        hdrs["Authorization"] = f"Bearer {token}"
    if cookie:
        hdrs["Cookie"] = cookie
    if json_body is not None:
        data = json.dumps(json_body).encode()
        hdrs["Content-Type"] = "application/json"
    elif form is not None:
        data = urllib.parse.urlencode(form).encode()
        hdrs["Content-Type"] = "application/x-www-form-urlencoded"
    req = urllib.request.Request(url, data=data, method=method, headers=hdrs)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read()
            if not raw:
                return None
            try:
                return json.loads(raw)
            except ValueError:
                return raw.decode(errors="replace")
    except urllib.error.HTTPError as exc:
        raise HttpError(exc.code, exc.read().decode(errors="replace"), url) from None


def password_token(cfg: Config, realm: str, username: str, password: str, *, client_id: str | None = None,
                   secret: str | None = None, scope: str = "openid") -> str:
    form = {"grant_type": "password", "client_id": client_id or cfg.client_id, "username": username,
            "password": password, "scope": scope}
    if secret:
        form["client_secret"] = secret
    payload = request("POST", f"{cfg.keycloak}/realms/{realm}/protocol/openid-connect/token", form=form)
    return payload["access_token"]


class Backend:
    """Backend API client bound to one user and the active-tenant cookie."""

    def __init__(self, cfg: Config, token: str, tenant_slug: str | None) -> None:
        self.cfg, self.token = cfg, token
        self.cookie = f"m8flow_selected_tenant={tenant_slug}" if tenant_slug else None

    def __call__(self, method: str, path: str, **kw):
        url = path if path.startswith("http") else f"{self.cfg.backend}{path}"
        return request(method, url, token=self.token, cookie=self.cookie, **kw)


def log(step: str, message: str) -> None:
    print(f"[{step}] {message}", flush=True)


# --------------------------------------------------------------------------- steps
def wait_for_stack(cfg: Config, timeout: float = 180) -> None:
    deadline = time.time() + timeout
    while True:
        try:
            request("GET", f"{cfg.backend}/v1.0/status", timeout=5)
            request("GET", f"{cfg.keycloak}/realms/{cfg.realm}/.well-known/openid-configuration", timeout=5)
            return
        except Exception as exc:  # noqa: BLE001
            if time.time() > deadline:
                raise SystemExit(f"stack not reachable: {exc}") from None
            time.sleep(3)


def ensure_tenant(cfg: Config, tenant: dict) -> tuple[str, str]:
    """Create the Keycloak organization + tenant row through the backend (super-admin).

    Returns (tenant id, super-admin access token)."""
    token = password_token(cfg, "master", cfg.super_admin, cfg.super_admin_password,
                           client_id=cfg.get("PERF_SEED_SUPER_ADMIN_CLIENT_ID", cfg.client_id), secret=cfg.client_secret)
    api = Backend(cfg, token, None)
    try:
        created = api("POST", "/v1.0/m8flow/tenant-realms", json_body={"slug": tenant["slug"], "name": tenant["name"]})
        log("tenant", f"created organization {tenant['slug']} ({created.get('id')})")
    except HttpError as exc:
        if exc.status != 409:
            raise
        log("tenant", f"organization {tenant['slug']} already exists")
    found = api("GET", f"/v1.0/m8flow/tenants/slug/{tenant['slug']}")
    tenant_id = (found or {}).get("id") or tenant["slug"]
    log("tenant", f"tenant id {tenant_id}")
    return tenant_id, token


def expand_users(scenario: dict, scale: int) -> list[dict]:
    users = []
    for spec in scenario["users"]:
        count = spec["count"] * (scale if spec["count"] > 1 else 1)
        for i in range(1, count + 1):
            username = spec["prefix"] if spec["count"] == 1 else f"{spec['prefix']}-{i:02d}"
            users.append({"username": username, "groups": spec["groups"],
                          "first_name": spec["first_name"], "last_name": f"{spec['last_name']} {i}" if count > 1 else spec["last_name"],
                          "email": f"{username}@{scenario['email_domain']}"})
    return users


def ensure_keycloak_users(cfg: Config, users: list[dict]) -> None:
    admin = password_token(cfg, "master", cfg.kc_admin, cfg.kc_admin_password, client_id="admin-cli")
    base = f"{cfg.keycloak}/admin/realms/{cfg.realm}/users"
    created = 0
    for user in users:
        body = {
            "username": user["username"], "email": user["email"], "firstName": user["first_name"],
            "lastName": user["last_name"], "enabled": True, "emailVerified": True,
            "credentials": [{"type": "password", "value": cfg.user_password or user["username"], "temporary": False}],
        }
        try:
            request("POST", base, token=admin, json_body=body)
            created += 1
        except HttpError as exc:
            if exc.status != 409:
                raise
    log("users", f"{created} created, {len(users) - created} already present")


def ensure_memberships(api: Backend, tenant_id: str, users: list[dict]) -> None:
    """The members route is idempotent: it adds the org membership and groups that are
    missing and syncs the local user + roles immediately (no first login needed)."""
    for user in users:
        api("POST", f"/v1.0/m8flow/tenants/{tenant_id}/members",
            json_body={"username": user["username"], "group_names": user["groups"]})
    log("members", f"{len(users)} users ensured in {tenant_id} with their groups")


def ensure_group_roles(api: Backend, tenant_id: str, grants: list[dict]) -> None:
    """Extra tenant roles for org groups (PUT is idempotent and mirrors to every member)."""
    for grant in grants:
        api("PUT", f"/v1.0/m8flow/tenants/{tenant_id}/groups/{grant['group']}/roles/{grant['role']}")
        log("roles", f"{grant['group']} also has role {grant['role']}")


def warm_sessions(cfg: Config, slug: str, users: list[dict]) -> None:
    """Sign every user in once, as a browser login would.

    The members route syncs groups and roles, but the user's binding to the
    tenant is only finalized on their first authenticated request (until then,
    starting an instance is refused with "does not belong to tenant"). The two
    routes are the non-admin regression minimum, so this doubles as a check.
    """
    failures = []
    for user in users:
        token = password_token(cfg, cfg.realm, user["username"], cfg.user_password or user["username"],
                               secret=cfg.client_secret, scope="openid organization")
        api = Backend(cfg, token, slug)
        for path in ("/v1.0/onboarding", "/v1.0/tasks"):
            try:
                api("GET", path)
            except HttpError as exc:
                failures.append(f"{user['username']} {path}: {exc.status}")
    if failures:
        raise SystemExit("session warm-up failed:\n  " + "\n  ".join(failures))
    log("sessions", f"{len(users)} users signed in (GET /v1.0/onboarding and /v1.0/tasks ok)")


def default_profile_value(cfg: Config, connector_type: str, field: str) -> str:
    """Connector profile defaults derived from the stack's own .env (nothing stored in the repo)."""
    if (connector_type, field) == ("postgres_v2", "database_connection_str"):
        user, password = cfg.get("POSTGRES_USER", "postgres"), cfg.get("POSTGRES_PASSWORD", "postgres")
        return f"host=m8flow-db port=5432 dbname={cfg.get('POSTGRES_DB', 'postgres')} user={user} password={password}"
    raise SystemExit(f"no default for {connector_type}.{field}; set its env var")


def ensure_connector_profiles(api: Backend, cfg: Config, profiles: list[dict]) -> None:
    for spec in profiles:
        existing = api("GET", f"/v1.0/m8flow/connector-profiles?connector_type={spec['connector_type']}")
        rows = existing.get("results", existing) if isinstance(existing, dict) else existing or []
        if any(r.get("profile_name") == spec["profile_name"] for r in rows):
            log("profiles", f"{spec['connector_type']}/{spec['profile_name']} already exists")
            continue
        config = {k: cfg.get(env) or default_profile_value(cfg, spec["connector_type"], k)
                  for k, env in spec["config_env"].items()}
        api("POST", "/v1.0/m8flow/connector-profiles", json_body={
            "connector_type": spec["connector_type"], "profile_name": spec["profile_name"],
            "display_name": spec["display_name"], "description": spec["description"], "config": config,
        })
        log("profiles", f"created {spec['connector_type']}/{spec['profile_name']}")


def ensure_process_groups(api: Backend, groups: list[dict]) -> None:
    for group in groups:
        try:
            api("POST", "/v1.0/m8flow/process-groups", json_body=group)
            log("groups", f"created {group['id']}")
        except HttpError as exc:
            if exc.status != 409:
                raise
            log("groups", f"{group['id']} already exists")


def ensure_templates(api: Backend, refresh: bool = False) -> dict[str, int]:
    """Import each template once. With refresh, import the current build as a new version."""
    ids: dict[str, int] = {}
    for template in all_templates():
        found = api("GET", f"/v1.0/m8flow/templates?template_key={urllib.parse.quote(template.key)}")
        rows = [r for r in found.get("results", []) if r.get("templateKey") == template.key]
        zip_bytes = (GENERATED / "templates" / f"{template.key}.zip").read_bytes()
        build_tag = "build-" + hashlib.sha256(zip_bytes).hexdigest()[:12]
        if rows:
            latest = max(rows, key=lambda r: r["id"])
            if not refresh or build_tag in (latest.get("tags") or []):
                ids[template.key] = latest["id"]
                log("templates", f"{template.key} already imported (id {latest['id']})")
                continue
        created = api("POST", "/v1.0/m8flow/templates/import", data=zip_bytes, headers={
            "Content-Type": "application/zip",
            "X-Template-Key": template.key,
            "X-Template-Name": template.name,
            "X-Template-Visibility": "TENANT",
            "X-Template-Is-Published": "true",
            "X-Template-Category": template.category,
            "X-Template-Tags": json.dumps([*template.tags, build_tag]),
        })
        ids[template.key] = created["id"]
        log("templates", f"imported {template.key} (id {created['id']})")
    return ids


def model_exists(api: Backend, route_id: str) -> bool:
    try:
        api("GET", f"/v1.0/m8flow/process-models/{route_id}")
        return True
    except HttpError as exc:
        if exc.status == 404:
            return False
        raise


def publish(api: Backend, route_id: str) -> None:
    api("PUT", f"/v1.0/m8flow/process-models/{route_id}", json_body={"status": "published"})


def upload_template_files(api: Backend, route_id: str, template_key: str) -> None:
    """Overwrite an existing model's files with the current template build.

    create-process-model gave the model its own process id; keep it, or the
    model's primary_process_id would no longer match its BPMN.
    """
    template = next(t for t in all_templates() if t.key == template_key)
    current = api("GET", f"/v1.0/m8flow/process-models/{route_id}/files/{template.bpmn_file}")
    current = current if isinstance(current, str) else json.dumps(current)
    match = re.search(r'<bpmn:process id="([^"]+)"[^>]*isExecutable="true"', current)
    if not match:
        raise SystemExit(f"cannot refresh {route_id}: no executable process in its {template.bpmn_file}")
    process_id = match.group(1)
    for path in sorted((GENERATED / "templates" / template_key).iterdir()):
        body = path.read_bytes()
        if path.suffix == ".bpmn":
            body = body.replace(template.diagram.process_id.encode(), process_id.encode())
        api("PUT", f"/v1.0/m8flow/process-models/{route_id}/files/{urllib.parse.quote(path.name)}",
            data=body, headers={"Content-Type": "application/octet-stream"})


def ensure_template_models(api: Backend, template_ids: dict[str, int], models: list[dict], refresh: bool = False) -> None:
    for model in models:
        route_id = f"{model['group']}:{model['id']}"
        if model_exists(api, route_id):
            if refresh:
                upload_template_files(api, route_id, model["template"])
                log("models", f"{route_id} refreshed from the current {model['template']} build")
            else:
                log("models", f"{route_id} already exists")
        else:
            api("POST", f"/v1.0/m8flow/templates/{template_ids[model['template']]}/create-process-model", json_body={
                "process_group_id": model["group"], "process_model_id": model["id"],
                "display_name": model["display_name"],
                "description": f"Northwind {model['display_name'].lower()} (from the {model['template']} template)",
            })
            log("models", f"created {route_id} from {model['template']}")
        publish(api, route_id)


def ensure_connector_models(api: Backend, models: list[dict]) -> None:
    from connectors import all_connector_models

    by_id = {m.model_id: m for m in all_connector_models()}
    for spec in models:
        source = by_id[spec["source"]]
        route_id = f"{spec['group']}:{source.model_id}"
        if not model_exists(api, route_id):
            api("POST", "/v1.0/m8flow/process-models", json_body={
                "group_id": spec["group"], "id": source.model_id, "display_name": source.name,
                "description": source.description,
            })
            log("models", f"created {route_id}")
        else:
            log("models", f"{route_id} already exists")
        # The default <id>.bpmn is overwritten in place, so primary_file/process id stay aligned.
        for path in sorted((GENERATED / "connectors" / source.model_id).iterdir()):
            api("PUT", f"/v1.0/m8flow/process-models/{route_id}/files/{urllib.parse.quote(path.name)}",
                data=path.read_bytes(), headers={"Content-Type": "application/octet-stream"})
        if source.publish:
            publish(api, route_id)
        else:
            log("models", f"{route_id} left in draft (publish it to start its timer)")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--env-file", type=Path, default=REPO / ".env")
    ap.add_argument("--scenario", type=Path, default=HERE / "scenario.json")
    ap.add_argument("--scale", type=int, default=1, help="multiply the per-group user counts (load spreading)")
    ap.add_argument("--refresh", action="store_true",
                    help="push the current template build into an existing seed (a new template version when the "
                         "build changed, model files overwritten); without it existing objects are left untouched")
    args = ap.parse_args()

    cfg = Config(args.env_file)
    scenario = json.loads(args.scenario.read_text())
    slug = scenario["tenant"]["slug"]
    if not (GENERATED / "templates").is_dir():
        raise SystemExit("perf/seed/generated is missing: run python3 perf/seed/build.py")

    wait_for_stack(cfg)
    tenant_id, super_token = ensure_tenant(cfg, scenario["tenant"])
    users = expand_users(scenario, args.scale)
    ensure_keycloak_users(cfg, users)
    ensure_memberships(Backend(cfg, super_token, slug), tenant_id, users)
    ensure_group_roles(Backend(cfg, super_token, slug), tenant_id, scenario.get("group_roles", []))
    warm_sessions(cfg, slug, users)

    admin_user = next(u for u in users if "Administrators" in u["groups"])
    admin_token = password_token(cfg, cfg.realm, admin_user["username"], cfg.user_password or admin_user["username"],
                                 secret=cfg.client_secret, scope="openid organization")
    api = Backend(cfg, admin_token, slug)
    ensure_connector_profiles(api, cfg, scenario["connector_profiles"])
    ensure_process_groups(api, scenario["process_groups"])
    template_ids = ensure_templates(api, args.refresh)
    ensure_template_models(api, template_ids, scenario["template_models"], args.refresh)
    ensure_connector_models(api, scenario["connector_models"])

    total = len(scenario["template_models"]) + len(scenario["connector_models"])
    log("done", f"tenant {slug}: {len(users)} users, {len(template_ids)} templates, {total} process models")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
