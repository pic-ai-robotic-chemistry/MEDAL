[Unit]
Description=OpenClaw Remote Job Orchestrator Tick
After=default.target

[Service]
Type=oneshot
WorkingDirectory=__WORKDIR__
Environment=ORCH_DB=__DB_PATH__
ExecStart=/usr/bin/env python3 __WORKER_PY__ --db __DB_PATH__ tick --limit __LIMIT__ --lock-seconds __LOCK_SECONDS__

[Install]
WantedBy=default.target
