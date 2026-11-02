#!/usr/bin/env bash
# Save or restore the complete state of a local m8flow stack, so a seeded perf
# scenario can be recreated in seconds instead of re-running the seed.
#
#   perf/snapshot.sh save <name>
#   perf/snapshot.sh restore <name> --yes
#   perf/snapshot.sh list
#
# A snapshot (perf/snapshots/<name>/) holds:
#   m8flow.dump      pg_dump -Fc of the m8flow database (includes the perf_* ledger tables)
#   keycloak.dump    pg_dump -Fc of the Keycloak database (realms, users, organizations)
#   process_models.tgz   data/process_models (BPMN/DMN/forms for every tenant)
#   templates.tgz    the backend's template storage (/app/data/templates)
#
# restore REPLACES all four for every tenant on the stack, not just the perf
# tenant, hence --yes. Run from any directory; uses docker compose with the
# repo's .env and docker/m8flow-docker-compose.yml (override with M8FLOW_ENV_FILE).

set -euo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="${M8FLOW_ENV_FILE:-${REPO}/.env}"
SNAPSHOTS="${REPO}/perf/snapshots"
COMPOSE=(docker compose --env-file "${ENV_FILE}" -f "${REPO}/docker/m8flow-docker-compose.yml")
# Services holding database connections; stopped during a restore.
APP_SERVICES=(m8flow-backend m8flow-celery-worker m8flow-celery-flower m8flow-notification-worker keycloak)

env_value() {
  local value
  value="$(grep -E "^$1=" "${ENV_FILE}" 2>/dev/null | tail -1 | cut -d= -f2- || true)"
  echo "${value:-$2}"
}

PG_USER="$(env_value POSTGRES_USER postgres)"
PG_DB="$(env_value POSTGRES_DB postgres)"
KC_USER="$(env_value KEYCLOAK_DB_USER keycloak)"
KC_DB="$(env_value KEYCLOAK_DB_NAME keycloak)"

usage() {
  sed -n '2,8p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'
  exit 1
}

wait_for_backend() {
  local url="${M8FLOW_BACKEND_BASE_URL:-http://localhost:6840}/v1.0/status"
  for _ in $(seq 1 90); do
    curl -fsS "${url}" >/dev/null 2>&1 && return 0
    sleep 2
  done
  echo "backend did not become healthy at ${url}" >&2
  return 1
}

save() {
  local dir="${SNAPSHOTS}/$1"
  [[ -e "${dir}" ]] && { echo "snapshot $1 already exists: ${dir}" >&2; exit 1; }
  mkdir -p "${dir}"
  echo "saving m8flow database (${PG_DB})"
  "${COMPOSE[@]}" exec -T m8flow-db pg_dump -U "${PG_USER}" -Fc "${PG_DB}" > "${dir}/m8flow.dump"
  echo "saving keycloak database (${KC_DB})"
  "${COMPOSE[@]}" exec -T keycloak-db pg_dump -U "${KC_USER}" -Fc "${KC_DB}" > "${dir}/keycloak.dump"
  echo "saving data/process_models"
  tar -C "${REPO}/data" -czf "${dir}/process_models.tgz" process_models
  echo "saving template storage"
  "${COMPOSE[@]}" exec -T m8flow-backend tar -C /app/data -czf - templates > "${dir}/templates.tgz"
  date -u +%Y-%m-%dT%H:%M:%SZ > "${dir}/created_at"
  du -sh "${dir}"
}

restore_db() {
  local service="$1" user="$2" db="$3" dump="$4"
  echo "restoring ${service}/${db}"
  "${COMPOSE[@]}" exec -T "${service}" psql -U "${user}" -d template1 -v ON_ERROR_STOP=1 -q \
    -c "DROP DATABASE IF EXISTS \"${db}\" WITH (FORCE)" -c "CREATE DATABASE \"${db}\" OWNER \"${user}\""
  "${COMPOSE[@]}" exec -T "${service}" pg_restore -U "${user}" -d "${db}" --no-owner --exit-on-error < "${dump}"
}

restore() {
  local dir="${SNAPSHOTS}/$1"
  [[ -d "${dir}" ]] || { echo "no snapshot $1 in ${SNAPSHOTS}" >&2; exit 1; }
  [[ "${2:-}" == "--yes" ]] || { echo "restore replaces ALL tenants' data on this stack; re-run with --yes" >&2; exit 1; }

  echo "stopping ${APP_SERVICES[*]}"
  "${COMPOSE[@]}" stop "${APP_SERVICES[@]}"
  restore_db m8flow-db "${PG_USER}" "${PG_DB}" "${dir}/m8flow.dump"
  restore_db keycloak-db "${KC_USER}" "${KC_DB}" "${dir}/keycloak.dump"

  echo "restoring data/process_models"
  rm -rf "${REPO}/data/process_models"
  tar -C "${REPO}/data" -xzf "${dir}/process_models.tgz"

  echo "flushing redis (cached sessions and task state)"
  "${COMPOSE[@]}" exec -T redis redis-cli FLUSHALL >/dev/null

  echo "starting ${APP_SERVICES[*]}"
  "${COMPOSE[@]}" start "${APP_SERVICES[@]}"
  wait_for_backend

  echo "restoring template storage"
  "${COMPOSE[@]}" exec -T m8flow-backend sh -c 'rm -rf /app/data/templates && tar -C /app/data -xzf -' \
    < "${dir}/templates.tgz"
  echo "restored snapshot $1 ($(cat "${dir}/created_at" 2>/dev/null || echo 'unknown date'))"
}

case "${1:-}" in
  save) [[ -n "${2:-}" ]] || usage; save "$2" ;;
  restore) [[ -n "${2:-}" ]] || usage; restore "$2" "${3:-}" ;;
  list) ls -1 "${SNAPSHOTS}" 2>/dev/null || true ;;
  *) usage ;;
esac
