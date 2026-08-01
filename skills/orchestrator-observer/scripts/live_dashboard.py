#!/usr/bin/env python3
"""Live dashboard for OpenClaw orchestrator background activity."""

from __future__ import annotations

import argparse
import os
import shutil
import sqlite3
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path


def run(cmd: list[str]) -> tuple[int, str, str]:
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True)
        return proc.returncode, (proc.stdout or "").strip(), (proc.stderr or "").strip()
    except FileNotFoundError:
        return 127, "", f"command not found: {cmd[0]}"
    except PermissionError:
        return 126, "", f"permission denied: {cmd[0]}"


def has(cmd: str) -> bool:
    return shutil.which(cmd) is not None


def timer_status() -> str:
    if not has("systemctl"):
        return "systemctl unavailable on this host"
    rc1, out1, err1 = run(["systemctl", "--user", "is-active", "openclaw-orchestrator.timer"])
    rc2, out2, err2 = run(["systemctl", "--user", "is-enabled", "openclaw-orchestrator.timer"])
    active = out1 if rc1 == 0 else (out1 or err1 or str(rc1))
    enabled = out2 if rc2 == 0 else (out2 or err2 or str(rc2))
    return f"active={active} enabled={enabled}"


def recent_journal_lines(n: int = 6) -> list[str]:
    if not has("journalctl"):
        return ["journalctl unavailable"]
    rc, out, err = run([
        "journalctl",
        "--user",
        "-u",
        "openclaw-orchestrator.service",
        "-n",
        str(n),
        "--no-pager",
        "-o",
        "short-iso",
    ])
    if rc != 0:
        return [f"journal error: {err or rc}"]
    lines = [ln for ln in out.splitlines() if ln.strip()]
    return lines[-n:] or ["(no journal lines)"]


def process_lines() -> list[str]:
    patterns = ["openclaw", "persistent_worker.py", "openclaw-orchestrator", "orchestrator_health.py"]
    rc, out, err = run(["ps", "-axo", "pid,ppid,start,etime,command"])
    if rc != 0:
        return [f"ps error: {err or rc}"]
    matched: list[str] = []
    for line in out.splitlines():
        low = line.lower()
        if any(p in low for p in patterns):
            if "grep" in low:
                continue
            matched.append(line)
    return matched[-20:] if matched else ["(no matching processes right now)"]


def db_snapshot(db_path: Path) -> list[str]:
    if not db_path.exists():
        return [f"db not found: {db_path}"]

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        lines: list[str] = []
        cur = conn.execute("SELECT status, COUNT(*) AS n FROM jobs GROUP BY status ORDER BY status")
        rows = cur.fetchall()
        if rows:
            summary = ", ".join(f"{r['status']}={r['n']}" for r in rows)
        else:
            summary = "no jobs"
        lines.append(f"jobs: {summary}")

        cur = conn.execute(
            """
            SELECT id, workflow, status, last_heartbeat_at, next_run_at
            FROM jobs
            WHERE status IN ('queued', 'running', 'retry')
            ORDER BY updated_at DESC
            LIMIT 10
            """
        )
        active = cur.fetchall()
        if not active:
            lines.append("active: (none)")
        else:
            lines.append("active jobs:")
            for row in active:
                short_id = str(row["id"])[:8]
                lines.append(
                    f"  - {short_id} {row['workflow']} status={row['status']} hb={row['last_heartbeat_at']} next={row['next_run_at']}"
                )

        cur = conn.execute(
            """
            SELECT event_type, created_at
            FROM events
            ORDER BY id DESC
            LIMIT 8
            """
        )
        evs = cur.fetchall()
        lines.append("recent events:")
        if not evs:
            lines.append("  - (none)")
        else:
            for ev in evs:
                lines.append(f"  - {ev['created_at']} {ev['event_type']}")
        return lines
    finally:
        conn.close()


def clear() -> None:
    print("\033[2J\033[H", end="")


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="Live observer dashboard for OpenClaw orchestrator")
    parser.add_argument(
        "--db",
        default=os.environ.get("ORCH_DB", os.path.expanduser("~/.local/share/openclaw-orchestrator/orchestrator.db")),
    )
    parser.add_argument("--interval", type=int, default=8)
    parser.add_argument("--once", action="store_true", help="Render one snapshot and exit")
    args = parser.parse_args(argv)

    db_path = Path(args.db).expanduser()

    while True:
        clear()
        now = datetime.now(timezone.utc).astimezone().strftime("%Y-%m-%d %H:%M:%S %Z")
        print(f"OpenClaw Orchestrator Live Dashboard   now={now}")
        print("=" * 72)
        print(f"timer: {timer_status()}")
        print("\nprocesses (matching openclaw/orchestrator):")
        for ln in process_lines():
            print(ln)
        print("\ndatabase snapshot:")
        for ln in db_snapshot(db_path):
            print(ln)
        print("\nrecent service journal:")
        for ln in recent_journal_lines():
            print(ln)
        print("\nPress Ctrl+C to exit")
        sys.stdout.flush()
        if args.once:
            return 0
        try:
            time.sleep(max(2, args.interval))
        except KeyboardInterrupt:
            return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
