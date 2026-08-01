#!/usr/bin/env python3
"""Health report for OpenClaw orchestrator (systemd user + SQLite)."""

from __future__ import annotations

import argparse
import json
import os
import sqlite3
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any


@dataclass
class CheckResult:
    name: str
    ok: bool
    summary: str
    details: str = ""


def run_cmd(cmd: list[str]) -> tuple[int, str, str]:
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True)
        return proc.returncode, (proc.stdout or "").strip(), (proc.stderr or "").strip()
    except FileNotFoundError:
        return 127, "", f"command not found: {cmd[0]}"


def check_timer_active() -> CheckResult:
    rc, out, err = run_cmd(["systemctl", "--user", "is-active", "openclaw-orchestrator.timer"])
    if rc == 0 and out == "active":
        return CheckResult("timer_active", True, "timer is active")
    msg = out or err or f"return code {rc}"
    return CheckResult("timer_active", False, f"timer is not active ({msg})")


def check_timer_enabled() -> CheckResult:
    rc, out, err = run_cmd(["systemctl", "--user", "is-enabled", "openclaw-orchestrator.timer"])
    if rc == 0 and out in {"enabled", "static", "indirect"}:
        return CheckResult("timer_enabled", True, f"timer is {out}")
    msg = out or err or f"return code {rc}"
    return CheckResult("timer_enabled", False, f"timer is not enabled ({msg})")


def check_recent_service_runs(min_runs: int, within_minutes: int) -> CheckResult:
    since = (datetime.now(timezone.utc) - timedelta(minutes=within_minutes)).strftime("%Y-%m-%d %H:%M:%S")
    rc, out, err = run_cmd(
        [
            "journalctl",
            "--user",
            "-u",
            "openclaw-orchestrator.service",
            "--since",
            since,
            "--no-pager",
            "-n",
            "200",
            "-o",
            "short-iso",
        ]
    )
    if rc != 0:
        return CheckResult("service_journal", False, f"journal query failed ({err or rc})")

    lines = [line for line in out.splitlines() if line.strip()]
    if len(lines) >= min_runs:
        return CheckResult(
            "service_journal",
            True,
            f"journal has {len(lines)} line(s) in last {within_minutes} min",
            details="\n".join(lines[-10:]),
        )
    return CheckResult(
        "service_journal",
        False,
        f"only {len(lines)} journal line(s) in last {within_minutes} min",
        details="\n".join(lines[-10:]),
    )


def parse_iso(ts: str) -> datetime | None:
    try:
        return datetime.fromisoformat(ts)
    except Exception:
        return None


def check_db(db_path: Path, stale_minutes: int) -> list[CheckResult]:
    if not db_path.exists():
        return [CheckResult("db_exists", False, f"db not found: {db_path}")]

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    results: list[CheckResult] = []
    try:
        cur = conn.execute("SELECT status, COUNT(*) AS n FROM jobs GROUP BY status")
        rows = cur.fetchall()
        total = sum(int(r["n"]) for r in rows)
        summary = ", ".join(f"{r['status']}={r['n']}" for r in rows) if rows else "no jobs"
        results.append(CheckResult("db_jobs", True, f"total jobs={total}; {summary}"))

        cutoff = datetime.now(timezone.utc) - timedelta(minutes=stale_minutes)
        cur = conn.execute(
            """
            SELECT id, workflow, status, last_heartbeat_at, next_run_at
            FROM jobs
            WHERE status IN ('queued', 'running', 'retry')
            ORDER BY updated_at DESC
            """
        )
        stale: list[dict[str, Any]] = []
        for row in cur.fetchall():
            hb = parse_iso(row["last_heartbeat_at"]) if row["last_heartbeat_at"] else None
            if hb is None or hb < cutoff:
                stale.append(
                    {
                        "id": row["id"],
                        "workflow": row["workflow"],
                        "status": row["status"],
                        "last_heartbeat_at": row["last_heartbeat_at"],
                        "next_run_at": row["next_run_at"],
                    }
                )

        if stale:
            details = "\n".join(json.dumps(item, ensure_ascii=True) for item in stale[:20])
            results.append(
                CheckResult(
                    "db_stale_active_jobs",
                    False,
                    f"found {len(stale)} stale active job(s) (>{stale_minutes} min heartbeat gap)",
                    details=details,
                )
            )
        else:
            results.append(CheckResult("db_stale_active_jobs", True, "no stale active jobs"))

        cur = conn.execute("SELECT COUNT(*) FROM events")
        event_count = int(cur.fetchone()[0])
        results.append(CheckResult("db_events", True, f"event rows={event_count}"))

    finally:
        conn.close()

    return results


def to_markdown(results: list[CheckResult], json_mode: bool) -> str:
    if json_mode:
        return json.dumps([r.__dict__ for r in results], ensure_ascii=True, indent=2)

    lines: list[str] = []
    overall_ok = all(r.ok for r in results)
    lines.append(f"overall: {'OK' if overall_ok else 'DEGRADED'}")
    for r in results:
        status = "OK" if r.ok else "FAIL"
        lines.append(f"- [{status}] {r.name}: {r.summary}")
        if r.details:
            lines.append("  details:")
            for line in r.details.splitlines():
                lines.append(f"  {line}")
    return "\n".join(lines)


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="Observe OpenClaw orchestrator health")
    parser.add_argument(
        "--db",
        default=os.environ.get("ORCH_DB", os.path.expanduser("~/.local/share/openclaw-orchestrator/orchestrator.db")),
    )
    parser.add_argument("--stale-minutes", type=int, default=30, help="Heartbeat gap threshold for active jobs")
    parser.add_argument("--journal-window-minutes", type=int, default=20)
    parser.add_argument("--journal-min-lines", type=int, default=1)
    parser.add_argument("--json", action="store_true", help="Emit JSON")
    parser.add_argument("--strict", action="store_true", help="Exit non-zero on any failed check")
    args = parser.parse_args(argv)

    results: list[CheckResult] = []
    results.append(check_timer_active())
    results.append(check_timer_enabled())
    results.append(check_recent_service_runs(args.journal_min_lines, args.journal_window_minutes))
    results.extend(check_db(Path(args.db).expanduser(), args.stale_minutes))

    print(to_markdown(results, json_mode=args.json))

    if args.strict and any(not r.ok for r in results):
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
