---
name: remote-job-orchestrator
description: "Durable scheduler template for long-running remote computations. Use when a workflow submits Gaussian16/DFTB+/MACE jobs and must survive TUI/session interruption via cross-platform scheduling (Linux/macOS/Windows) plus SQLite state."
---

# Remote Job Orchestrator (cross-platform scheduler + SQLite)

Use this skill when remote jobs can run for hours/days and polling must continue even if the current OpenClaw session ends.

## What This Skill Provides
- SQLite state store for jobs + state-change events.
- Idempotent `submit -> poll -> fetch -> continue` worker loop.
- Cross-platform scheduling bootstrap:
  - Linux: `systemd --user`
  - macOS: `launchd` LaunchAgent
  - Windows: Task Scheduler XML bootstrap
  - Fallback: plain `cron` / external scheduler
- Callback hook for notifying another process when state changes.

## Files
- Worker CLI: `scripts/persistent_worker.py`
- Linux bootstrap helper: `scripts/bootstrap_systemd_user.sh`
- Cross-platform bootstrap helper: `scripts/bootstrap_cross_platform.py`
- systemd templates: `references/systemd-user/openclaw-orchestrator.service.tpl`, `references/systemd-user/openclaw-orchestrator.timer.tpl`
- Usage templates: `references/templates.md`

## Bootstrap (One-Time)
### Linux with systemd user
From this skill directory:

```bash
bash scripts/bootstrap_systemd_user.sh "$PWD" "$HOME/.local/share/openclaw-orchestrator" 60 32 600
```

### macOS / Windows / fallback-aware bootstrap
From this skill directory:

```bash
python3 scripts/bootstrap_cross_platform.py "$PWD" "$HOME/.local/share/openclaw-orchestrator" 60 32 600
```

Args (optional):
1. `workdir`
2. `state_dir`
3. `timer_interval_seconds`
4. `jobs_per_tick_limit`
5. `lock_seconds`

Sanity checks:
- Linux/systemd:
  ```bash
  systemctl --user status openclaw-orchestrator.timer
  systemctl --user list-timers | grep openclaw-orchestrator
  ```
- macOS/launchd:
  ```bash
  launchctl list | grep openclaw
  ls ~/Library/LaunchAgents/ai.openclaw.orchestrator.plist
  ```
- Windows Task Scheduler:
  ```powershell
  schtasks /Query /TN OpenClawOrchestrator
  ```
- Generic:
  ```bash
  python3 scripts/persistent_worker.py --db "$HOME/.local/share/openclaw-orchestrator/orchestrator.db" list --limit 20
  ```

## Submit a Long Job
After remote submit returns `remote_job_id`, enqueue poll/fetch/continue pipeline:

```bash
python3 scripts/persistent_worker.py --db "$HOME/.local/share/openclaw-orchestrator/orchestrator.db" submit \
  --workflow "gaussian16-opt" \
  --remote-job-id "123456" \
  --poll-command "python3 tools/check_gaussian_status.py --job 123456" \
  --fetch-command "python3 tools/fetch_gaussian_outputs.py --job 123456" \
  --continue-command "python3 tools/run_post_analysis.py --job 123456" \
  --callback-command "python3 tools/on_state_change.py" \
  --check-every 300 \
  --poll-timeout 120 \
  --max-retries 80 \
  --context done_regex='FINISHED|NORMAL TERMINATION' failed_regex='FAILED|ERROR|CANCELLED'
```

## Polling Contract (Important)
`poll_command` must be cheap + idempotent. It should print status text that matches regexes:
- `done_regex` -> mark `completed`
- `failed_regex` -> mark `failed`
- `running_regex` (optional) -> mark `running`

If nothing matches:
- exit code `0` => `running`
- nonzero / timeout => `retry` with exponential backoff

## Observe / Recover
```bash
python3 scripts/persistent_worker.py --db "$HOME/.local/share/openclaw-orchestrator/orchestrator.db" list --limit 50
python3 scripts/persistent_worker.py --db "$HOME/.local/share/openclaw-orchestrator/orchestrator.db" show <job_id> --events 30
python3 scripts/persistent_worker.py --db "$HOME/.local/share/openclaw-orchestrator/orchestrator.db" cancel <job_id>
```

## Integration Pattern for Other Skills
1. Existing compute skill submits remote job as usual.
2. Immediately call orchestrator `submit` with poll/fetch/continue commands.
3. Main skill returns quickly: “job delegated; continue asynchronously”.
4. Downstream continuation is executed by `continue_command` (not by a fragile TUI session).

## Operational Notes
- This skill does not rely on a persistent agent session.
- “Push back to main process” is implemented via `events` table + optional `callback_command`.
- If `systemd --user` is unavailable, use `bootstrap_cross_platform.py` or schedule `tick` with cron/launchd/Task Scheduler.
