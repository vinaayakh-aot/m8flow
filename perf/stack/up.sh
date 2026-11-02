#!/usr/bin/env bash
# Run the Northwind reference instance as its own compose project (m8flow-perf),
# beside the dev stack and wired into the observability stack, then seed it.
#
#   perf/stack/up.sh            # start (or update) and seed
#   perf/stack/up.sh --no-seed  # start only
#   perf/stack/up.sh down       # stop and remove containers (volumes kept)
#   perf/stack/up.sh destroy    # also delete its volumes and process models
#   perf/stack/up.sh status
#
# Ports are the dev ports +1000 (backend 7840, designer 7853, Keycloak 7842, ...).
# The env file is generated from sample.env on every run, so it never drifts
# from the repo defaults and nothing secret is checked in.

set -euo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
STACK="${REPO}/perf/stack"
ENV_FILE="${STACK}/.env.perf"
PROJECT="m8flow-perf"
OBS_NETWORK="m8flow-observability-stack_default"
COMPOSE=(docker compose -p "${PROJECT}" --env-file "${ENV_FILE}"
         -f "${REPO}/docker/m8flow-docker-compose.yml" -f "${STACK}/compose.perf.yml")

BACKEND_URL="http://localhost:7840"
DESIGNER_URL="http://localhost:7853"
KEYCLOAK_URL="http://localhost:7842"

generate_env() {
  # Shift every 68xx dev port to 78xx, switch telemetry on and tag it as perf.
  perl -pe 's/\b68(4[0-9]|5[0-3])\b/78$1/g' "${REPO}/sample.env" > "${ENV_FILE}"
  cat >> "${ENV_FILE}" <<EOF

# --- perf/stack/up.sh overrides (generated; edit up.sh, not this file) ---
OTEL_SDK_DISABLED=false
OTEL_EXPORTER_OTLP_ENDPOINT=http://m8flow-alloy:4317
OTEL_RESOURCE_ATTRIBUTES=service.namespace=${PROJECT},deployment.environment=perf
M8FLOW_FRONTEND_BACKEND_BASE_URL=${BACKEND_URL}
M8FLOW_FRONTEND_BASE_URL=${DESIGNER_URL}
M8FLOW_LOAD_SAMPLE_TEMPLATES=false
M8FLOW_BACKEND_BASE_URL=${BACKEND_URL}
M8FLOW_KEYCLOAK_URL=${KEYCLOAK_URL}
M8FLOW_COMPOSE_PROJECT=${PROJECT}
EOF
}

wait_for() {
  local name="$1" url="$2" tries="${3:-120}"
  for _ in $(seq 1 "${tries}"); do
    curl -fsS -o /dev/null "${url}" 2>/dev/null && { echo "${name} is up"; return 0; }
    sleep 3
  done
  echo "${name} did not come up at ${url}" >&2
  "${COMPOSE[@]}" ps >&2
  return 1
}

up() {
  docker network inspect "${OBS_NETWORK}" >/dev/null 2>&1 || {
    echo "observability stack is not running (network ${OBS_NETWORK} missing). Start it first:" >&2
    echo "  docker compose --env-file .env -f docker/m8flow-observability-docker-compose.yml up -d" >&2
    exit 1
  }
  generate_env
  mkdir -p "${STACK}/data/process_models" "${STACK}/data/m8flow_nats_consumer"
  "${COMPOSE[@]}" config --quiet
  echo "building the perf designer image (backend URL ${BACKEND_URL} is baked in)"
  "${COMPOSE[@]}" build m8flow-designer
  "${COMPOSE[@]}" up -d
  wait_for "backend" "${BACKEND_URL}/v1.0/status"
  wait_for "keycloak" "${KEYCLOAK_URL}/realms/m8flow/.well-known/openid-configuration"
  wait_for "designer" "${DESIGNER_URL}/"
  if [[ "${1:-}" != "--no-seed" ]]; then
    M8FLOW_BACKEND_BASE_URL="${BACKEND_URL}" M8FLOW_KEYCLOAK_URL="${KEYCLOAK_URL}" \
      python3 "${REPO}/perf/seed/seed.py" --env-file "${ENV_FILE}"
  fi
  status
}

status() {
  "${COMPOSE[@]}" ps --format 'table {{.Service}}\t{{.Status}}\t{{.Ports}}'
  cat <<EOF

Designer   ${DESIGNER_URL}
Backend    ${BACKEND_URL}
Keycloak   ${KEYCLOAK_URL}/admin
Grafana    http://localhost:6868   (filter logs by compose_project="${PROJECT}", traces/metrics by service.namespace="${PROJECT}")
EOF
}

case "${1:-}" in
  ""|--no-seed) up "${1:-}" ;;
  down) "${COMPOSE[@]}" down ;;
  destroy)
    "${COMPOSE[@]}" down -v
    rm -rf "${STACK}/data" "${ENV_FILE}"
    ;;
  status) status ;;
  *) sed -n '2,12p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'; exit 1 ;;
esac
