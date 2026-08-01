# Orchestrator Observer Runbook

## Healthy Example
```text
overall: OK
- [OK] timer_active: timer is active
- [OK] timer_enabled: timer is enabled
- [OK] service_journal: journal has 12 line(s) in last 20 min
- [OK] db_jobs: total jobs=16; completed=9, running=4, retry=3
- [OK] db_stale_active_jobs: no stale active jobs
- [OK] db_events: event rows=342
```

## Degraded Example
```text
overall: DEGRADED
- [FAIL] timer_active: timer is not active (inactive)
- [OK] timer_enabled: timer is enabled
- [FAIL] service_journal: only 0 journal line(s) in last 20 min
- [OK] db_jobs: total jobs=16; completed=9, running=7
- [FAIL] db_stale_active_jobs: found 5 stale active job(s) (>30 min heartbeat gap)
- [OK] db_events: event rows=342
```

## Fast Recovery Commands
```bash
systemctl --user daemon-reload
systemctl --user enable --now openclaw-orchestrator.timer
systemctl --user start openclaw-orchestrator.service
journalctl --user -u openclaw-orchestrator.service -n 50 --no-pager
```

## Live Window
```bash
bash /Users/zikaixie/PycharmProjects/skills/orchestrator-observer/scripts/open_dashboard_window.sh \
  "$HOME/.local/share/openclaw-orchestrator/orchestrator.db" 8
```

## Operator Rule of Thumb
- If timer is inactive: fix timer first.
- If timer is active but stale jobs keep increasing: inspect poll/fetch/continue commands for hangs and return codes.
- If callback errors appear in events: fix callback, but do not block polling.
- In oneshot mode, process list may be empty between ticks; trust timer + journal + DB heartbeat first.
