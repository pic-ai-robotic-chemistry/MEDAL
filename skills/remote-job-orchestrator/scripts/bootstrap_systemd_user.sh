#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SKILL_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

WORKDIR="${1:-$PWD}"
STATE_DIR="${2:-$HOME/.local/share/openclaw-orchestrator}"
INTERVAL_SECONDS="${3:-60}"
LIMIT="${4:-32}"
LOCK_SECONDS="${5:-600}"

WORKER_PY="${SKILL_ROOT}/scripts/persistent_worker.py"
DB_PATH="${STATE_DIR}/orchestrator.db"
SYSTEMD_DIR="${HOME}/.config/systemd/user"
SERVICE_PATH="${SYSTEMD_DIR}/openclaw-orchestrator.service"
TIMER_PATH="${SYSTEMD_DIR}/openclaw-orchestrator.timer"

mkdir -p "${STATE_DIR}" "${SYSTEMD_DIR}"

python3 "${WORKER_PY}" --db "${DB_PATH}" init-db

render_tpl() {
  local input="$1"
  local output="$2"

  sed \
    -e "s|__WORKDIR__|${WORKDIR}|g" \
    -e "s|__DB_PATH__|${DB_PATH}|g" \
    -e "s|__WORKER_PY__|${WORKER_PY}|g" \
    -e "s|__INTERVAL_SECONDS__|${INTERVAL_SECONDS}|g" \
    -e "s|__LIMIT__|${LIMIT}|g" \
    -e "s|__LOCK_SECONDS__|${LOCK_SECONDS}|g" \
    "${input}" > "${output}"
}

render_tpl "${SKILL_ROOT}/references/systemd-user/openclaw-orchestrator.service.tpl" "${SERVICE_PATH}"
render_tpl "${SKILL_ROOT}/references/systemd-user/openclaw-orchestrator.timer.tpl" "${TIMER_PATH}"

systemctl --user daemon-reload
systemctl --user enable --now openclaw-orchestrator.timer

cat <<MSG
Installed user-level orchestrator.

DB: ${DB_PATH}
Service: ${SERVICE_PATH}
Timer: ${TIMER_PATH}

Quick checks:
  systemctl --user status openclaw-orchestrator.timer
  systemctl --user list-timers | grep openclaw-orchestrator
  python3 ${WORKER_PY} --db ${DB_PATH} list --limit 20
MSG
