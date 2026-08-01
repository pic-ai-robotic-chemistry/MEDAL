[Unit]
Description=Schedule OpenClaw orchestrator tick

[Timer]
OnBootSec=45s
OnUnitActiveSec=__INTERVAL_SECONDS__s
Unit=openclaw-orchestrator.service
AccuracySec=1s
Persistent=true

[Install]
WantedBy=timers.target
