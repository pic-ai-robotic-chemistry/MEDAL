#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DASHBOARD_PY="${SCRIPT_DIR}/live_dashboard.py"
DB_PATH="${1:-$HOME/.local/share/openclaw-orchestrator/orchestrator.db}"
INTERVAL="${2:-8}"

CMD="python3 \"${DASHBOARD_PY}\" --db \"${DB_PATH}\" --interval ${INTERVAL}"

open_macos_terminal() {
  if command -v open >/dev/null 2>&1; then
    local launcher
    launcher="${TMPDIR:-/tmp}/openclaw-dashboard-${USER:-user}.command"
    cat > "${launcher}" <<EOF
#!/usr/bin/env bash
${CMD}
EOF
    chmod +x "${launcher}"
    open -a Terminal "${launcher}" >/dev/null 2>&1
    return 0
  fi
  return 1
}

open_linux_terminal() {
  if command -v x-terminal-emulator >/dev/null 2>&1; then
    x-terminal-emulator -e bash -lc "${CMD}" >/dev/null 2>&1 &
    return 0
  fi
  if command -v gnome-terminal >/dev/null 2>&1; then
    gnome-terminal -- bash -lc "${CMD}" >/dev/null 2>&1 &
    return 0
  fi
  if command -v xterm >/dev/null 2>&1; then
    xterm -e bash -lc "${CMD}" >/dev/null 2>&1 &
    return 0
  fi
  return 1
}

uname_s="$(uname -s | tr '[:upper:]' '[:lower:]')"
if [[ "${uname_s}" == "darwin" ]]; then
  if open_macos_terminal; then
    echo "Opened dashboard in a new Terminal window."
    exit 0
  fi
elif [[ "${uname_s}" == "linux" ]]; then
  if open_linux_terminal; then
    echo "Opened dashboard in a new terminal window."
    exit 0
  fi
fi

echo "Could not auto-open a new terminal window. Run this manually:" >&2
echo "  ${CMD}" >&2
exit 1
