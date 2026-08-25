# m8flow-node-wire-proxy

FastAPI host that will drop-in-replace `m8flow-connector-proxy` for **HTTP V2 Service Tasks**, backed by sibling-built **node-wire** wheels (`runtime` + `http_generic`). No `spiffworkflow-proxy`, no Spiff connector packages.

## Status (POC)

- `/liveness` → `{"ok": true}` (compose healthcheck shape)
- `GET /v1/commands` — HTTP V2 catalog (`http/*RequestV2`)
- `POST /v1/do/{connector}/{command}` — maps to `http_generic.request` (HEAD via adapter httpx)

## Setup (local)

```bash
# 1. Stage wheels from sibling node-wire (if not already present)
m8flow-node-wire-proxy/bin/stage-node-wire-wheels.sh

# 2. Create a venv and install host + matching platform wheels
cd m8flow-node-wire-proxy
python3 -m venv .venv && source .venv/bin/activate
./bin/install_local_deps

# 3. Run
./bin/run_server_locally
# or: CONNECTOR_PROXY_PORT=6844 ./bin/run_server_locally
curl -fsS http://127.0.0.1:7004/liveness
```

Env:

| Variable | Default | Purpose |
|---|---|---|
| `NW_ALLOWED_CONNECTORS` | `http_generic` | node-wire fail-closed allowlist |
| `CONNECTOR_PROXY_PORT` | `7004` (local) / compose uses `6844` | listen port |

## Docker

Build from the **repo root** (wheels must include the image’s linux tag — `linux_aarch64` on Apple Silicon):

```bash
# Stage linux wheels first if needed:
m8flow-node-wire-proxy/bin/stage-node-wire-wheels.sh
docker build -f m8flow-node-wire-proxy/Dockerfile -t m8flow/m8flow-node-wire-proxy .
```

Compose (`docker/m8flow-docker-compose.yml`) starts **`m8flow-node-wire-proxy`** on `${CONNECTOR_PROXY_PORT:-6844}` by default and points `M8FLOW_BACKEND_CONNECTOR_PROXY_URL` at it. The old `m8flow-connector-proxy` remains under profile `legacy-connector-proxy` (port `6845` when enabled).

## Dependencies

- PyPI: FastAPI, uvicorn, `PyJWT[crypto]` (required to import `node_wire_runtime`)
- Vendor wheels only for `node-wire-runtime` / `node-wire-http-generic` — see `vendor/wheels/README.md`
