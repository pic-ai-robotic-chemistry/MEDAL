#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import platform
import shutil
import subprocess
from pathlib import Path

SKILL_ROOT = Path(__file__).resolve().parent.parent
WORKER_PY = SKILL_ROOT / 'scripts' / 'persistent_worker.py'

LAUNCHD_TEMPLATE = '''<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key><string>{label}</string>
  <key>ProgramArguments</key>
  <array>
    <string>{python}</string>
    <string>{worker}</string>
    <string>--db</string><string>{db}</string>
    <string>tick</string>
    <string>--limit</string><string>{limit}</string>
    <string>--lock-seconds</string><string>{lock_seconds}</string>
  </array>
  <key>StartInterval</key><integer>{interval}</integer>
  <key>WorkingDirectory</key><string>{workdir}</string>
  <key>StandardOutPath</key><string>{stdout}</string>
  <key>StandardErrorPath</key><string>{stderr}</string>
  <key>RunAtLoad</key><true/>
</dict>
</plist>
'''

WINDOWS_XML_TEMPLATE = '''<?xml version="1.0" encoding="UTF-16"?>
<Task version="1.2" xmlns="http://schemas.microsoft.com/windows/2004/02/mit/task">
  <Triggers>
    <TimeTrigger>
      <Repetition><Interval>PT{interval_seconds}S</Interval><StopAtDurationEnd>false</StopAtDurationEnd></Repetition>
      <StartBoundary>2026-01-01T00:00:00</StartBoundary>
      <Enabled>true</Enabled>
    </TimeTrigger>
  </Triggers>
  <Principals><Principal id="Author"><RunLevel>LeastPrivilege</RunLevel></Principal></Principals>
  <Settings><MultipleInstancesPolicy>IgnoreNew</MultipleInstancesPolicy><DisallowStartIfOnBatteries>false</DisallowStartIfOnBatteries><StopIfGoingOnBatteries>false</StopIfGoingOnBatteries><ExecutionTimeLimit>PT15M</ExecutionTimeLimit></Settings>
  <Actions Context="Author">
    <Exec>
      <Command>{python}</Command>
      <Arguments>{args}</Arguments>
      <WorkingDirectory>{workdir}</WorkingDirectory>
    </Exec>
  </Actions>
</Task>
'''


def main() -> None:
    ap = argparse.ArgumentParser(description='Cross-platform bootstrap for remote-job-orchestrator')
    ap.add_argument('workdir')
    ap.add_argument('state_dir')
    ap.add_argument('interval_seconds', type=int, nargs='?', default=60)
    ap.add_argument('limit', type=int, nargs='?', default=32)
    ap.add_argument('lock_seconds', type=int, nargs='?', default=600)
    args = ap.parse_args()

    workdir = Path(args.workdir).expanduser().resolve()
    state_dir = Path(args.state_dir).expanduser().resolve()
    state_dir.mkdir(parents=True, exist_ok=True)
    db_path = state_dir / 'orchestrator.db'
    log_dir = state_dir / 'logs'
    log_dir.mkdir(parents=True, exist_ok=True)
    python = shutil.which('python3') or shutil.which('python')
    if not python:
        raise RuntimeError('python/python3 not found in PATH')

    subprocess.run([python, str(WORKER_PY), '--db', str(db_path), 'init-db'], check=True)

    system = platform.system().lower()
    if system == 'darwin':
        agents = Path.home() / 'Library' / 'LaunchAgents'
        agents.mkdir(parents=True, exist_ok=True)
        label = 'ai.openclaw.orchestrator'
        plist = agents / f'{label}.plist'
        plist.write_text(LAUNCHD_TEMPLATE.format(
            label=label,
            python=python,
            worker=WORKER_PY,
            db=db_path,
            limit=args.limit,
            lock_seconds=args.lock_seconds,
            interval=args.interval_seconds,
            workdir=workdir,
            stdout=log_dir / 'launchd.out.log',
            stderr=log_dir / 'launchd.err.log',
        ))
        print(f'launchd plist written: {plist}')
        print(f'to load: launchctl unload {plist} 2>/dev/null || true && launchctl load {plist}')
        return

    if system == 'windows':
        task_xml = state_dir / 'openclaw-orchestrator-task.xml'
        args_str = f'"{WORKER_PY}" --db "{db_path}" tick --limit {args.limit} --lock-seconds {args.lock_seconds}'
        task_xml.write_text(WINDOWS_XML_TEMPLATE.format(
            interval_seconds=args.interval_seconds,
            python=python,
            args=args_str,
            workdir=workdir,
        ), encoding='utf-16')
        print(f'windows task xml written: {task_xml}')
        print(f'to register: schtasks /Create /TN OpenClawOrchestrator /XML "{task_xml}" /F')
        return

    if shutil.which('systemctl'):
        print('Linux/systemd detected; use bootstrap_systemd_user.sh for native user timer setup.')
        return

    print('No native scheduler auto-installed. Fallback: run this periodically via cron or another scheduler:')
    print(f'{python} {WORKER_PY} --db "{db_path}" tick --limit {args.limit} --lock-seconds {args.lock_seconds}')


if __name__ == '__main__':
    main()
