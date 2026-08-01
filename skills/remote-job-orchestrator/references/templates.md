# Remote Job Orchestrator Templates (SQLite + cross-platform scheduler)

## 1. Submission Payload (map to `submit` CLI)
Use one record per remote task.

```yaml
workflow: gaussian16-opt
remote_job_id: "123456"
poll_command: "python3 tools/check_gaussian_status.py --job 123456"
fetch_command: "python3 tools/fetch_gaussian_outputs.py --job 123456"
continue_command: "python3 tools/run_post_analysis.py --job 123456"
callback_command: "python3 tools/on_state_change.py"
check_every: 300
poll_timeout: 120
max_retries: 80
context:
  done_regex: "FINISHED|NORMAL TERMINATION"
  failed_regex: "FAILED|ERROR|CANCELLED"
  running_regex: "RUNNING|QUEUED|PENDING"
```

## 2. Callback Contract
`callback_command` receives environment variables:

- `ORCH_JOB_ID`
- `ORCH_WORKFLOW`
- `ORCH_REMOTE_JOB_ID`
- `ORCH_OLD_STATUS`
- `ORCH_NEW_STATUS`
- `ORCH_NOTE`

Recommended callback behavior:
1. Write state change to your own event bus/chat notifier.
2. If `ORCH_NEW_STATUS=completed`, enqueue dependent step instead of assuming original TUI session exists.
3. Never block longer than 60s.

## 3. Poll Script Output Contract
Your poll script should print one of these words (or your own regex targets):

- Complete: `FINISHED`, `DONE`, `SUCCESS`
- Failed: `FAILED`, `ERROR`, `CANCELLED`
- Running: `RUNNING`, `PENDING`, `QUEUED`

If output is ambiguous:
- Return code `0` means running.
- Nonzero/timeout means retry.

## 4. Health Check Commands
### Linux / generic
```bash
python3 scripts/persistent_worker.py --db "$HOME/.local/share/openclaw-orchestrator/orchestrator.db" list --limit 20
python3 scripts/persistent_worker.py --db "$HOME/.local/share/openclaw-orchestrator/orchestrator.db" show <job_id> --events 50
```

### Linux systemd
```bash
systemctl --user status openclaw-orchestrator.timer
systemctl --user start openclaw-orchestrator.service
```

### macOS launchd
```bash
launchctl list | grep openclaw
launchctl kickstart -k gui/$(id -u)/ai.openclaw.orchestrator
```

### Windows Task Scheduler
```powershell
schtasks /Query /TN OpenClawOrchestrator
schtasks /Run /TN OpenClawOrchestrator
```

## 5. Minimal Failure Playbook
1. Scheduler inactive:
   - Linux: rerun `bootstrap_systemd_user.sh`
   - macOS/Windows: rerun `bootstrap_cross_platform.py` and load/register the emitted artifact
2. Job stuck in retry: inspect `show <job_id>`, fix `poll_command`/regex, then resubmit.
3. Callback fails: callback errors are in the `events` table (`event_type=callback_error`).
4. No native scheduler available: run `tick` from cron or another scheduler.
