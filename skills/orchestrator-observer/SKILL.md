---
name: orchestrator-observer
description: "Operational observer for openclaw remote-job-orchestrator. Use to verify background polling is really running, inspect stale jobs, and produce a health report."
---

# Orchestrator Observer

Use this skill to confirm that long-running remote workflows are still progressing when no TUI session is open.

## What It Checks
- `systemd --user` timer status (`active` and `enabled`).
- Recent service journal activity.
- SQLite job table summary.
- Stale active jobs (heartbeat gap threshold).
- Event table size.

## Files
- Health reporter: `scripts/orchestrator_health.py`
- Live dashboard: `scripts/live_dashboard.py`
- New-window launcher: `scripts/open_dashboard_window.sh`
- Example output and runbook: `references/observer-runbook.md`

## Quick Usage
```bash
python3 scripts/orchestrator_health.py
```

Open a dedicated new terminal window with a live dashboard:
```bash
bash scripts/open_dashboard_window.sh "$HOME/.local/share/openclaw-orchestrator/orchestrator.db" 8
```

Run dashboard in the current terminal:
```bash
python3 scripts/live_dashboard.py --db "$HOME/.local/share/openclaw-orchestrator/orchestrator.db" --interval 8
```

Strict mode (non-zero exit on failures):
```bash
python3 scripts/orchestrator_health.py --strict
```

JSON mode (for downstream automation):
```bash
python3 scripts/orchestrator_health.py --json
```

Custom DB and thresholds:
```bash
python3 scripts/orchestrator_health.py \
  --db "$HOME/.local/share/openclaw-orchestrator/orchestrator.db" \
  --stale-minutes 45 \
  --journal-window-minutes 30
```

## Interpreting Results
- `overall: OK` means all checks passed.
- `overall: DEGRADED` means at least one check failed.
- `db_stale_active_jobs: FAIL` usually means timer/service stopped, poll command hangs, or callback chain broke.
- Note: in `systemd timer + oneshot` mode, worker process is short-lived. “No long-lived process” can still be healthy if journal/events are advancing.

## Recommended Integration
When a compute-heavy skill delegates a remote job, suggest running this observer every 30-60 minutes (or via automation) and alert only on `DEGRADED`.
