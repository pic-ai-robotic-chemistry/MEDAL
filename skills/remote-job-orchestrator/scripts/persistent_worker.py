#!/usr/bin/env python3
"""SQLite-backed remote job orchestrator worker.

Designed for OpenClaw skills that submit long-running remote jobs and need
session-independent polling + resume.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
import sqlite3
import subprocess
import sys
import textwrap
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any


DEFAULT_DONE_REGEX = r"\b(COMPLETED|DONE|FINISHED|SUCCESS)\b"
DEFAULT_FAILED_REGEX = r"\b(FAILED|ERROR|CANCELLED|TIMEOUT)\b"
DEFAULT_RUNNING_REGEX = r"\b(RUNNING|PENDING|QUEUED|WAITING)\b"
DEFAULT_POLL_TIMEOUT = 120
DEFAULT_INTERVAL = 300
DEFAULT_MAX_RETRIES = 50
DEFAULT_BACKOFF_MAX = 3600

FINAL_STATES = ("completed", "failed", "cancelled")


def utc_now() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


def iso_now() -> str:
    return utc_now().isoformat()


def iso_after(seconds: int) -> str:
    return (utc_now() + dt.timedelta(seconds=seconds)).isoformat()


def ensure_parent(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS jobs (
    id TEXT PRIMARY KEY,
    workflow TEXT NOT NULL,
    status TEXT NOT NULL,
    remote_job_id TEXT,
    poll_command TEXT NOT NULL,
    fetch_command TEXT,
    continue_command TEXT,
    callback_command TEXT,
    check_every_seconds INTEGER NOT NULL,
    poll_timeout_seconds INTEGER NOT NULL,
    max_retries INTEGER NOT NULL,
    retry_count INTEGER NOT NULL DEFAULT 0,
    next_run_at TEXT NOT NULL,
    locked_until TEXT,
    last_heartbeat_at TEXT,
    last_poll_at TEXT,
    last_error TEXT,
    context_json TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    completed_at TEXT
);

CREATE TABLE IF NOT EXISTS events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id TEXT NOT NULL,
    event_type TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    created_at TEXT NOT NULL,
    FOREIGN KEY(job_id) REFERENCES jobs(id)
);

CREATE INDEX IF NOT EXISTS idx_jobs_next_run
ON jobs(status, next_run_at);

CREATE INDEX IF NOT EXISTS idx_events_job
ON events(job_id, created_at);
"""


@dataclass
class CmdResult:
    returncode: int
    stdout: str
    stderr: str
    timed_out: bool


class Orchestrator:
    def __init__(self, db_path: Path):
        self.db_path = db_path
        ensure_parent(db_path)
        self.conn = sqlite3.connect(db_path)
        self.conn.row_factory = sqlite3.Row

    def close(self) -> None:
        self.conn.close()

    def init_db(self) -> None:
        self.conn.executescript(SCHEMA_SQL)
        self.conn.commit()

    def emit_event(self, job_id: str, event_type: str, payload: dict[str, Any]) -> None:
        self.conn.execute(
            """
            INSERT INTO events(job_id, event_type, payload_json, created_at)
            VALUES(?, ?, ?, ?)
            """,
            (job_id, event_type, json.dumps(payload, ensure_ascii=True), iso_now()),
        )

    def submit_job(
        self,
        workflow: str,
        poll_command: str,
        remote_job_id: str | None,
        fetch_command: str | None,
        continue_command: str | None,
        callback_command: str | None,
        check_every_seconds: int,
        poll_timeout_seconds: int,
        max_retries: int,
        context: dict[str, Any],
        job_id: str | None = None,
    ) -> str:
        job_id = job_id or str(uuid.uuid4())
        now = iso_now()
        self.conn.execute(
            """
            INSERT INTO jobs(
                id, workflow, status, remote_job_id, poll_command, fetch_command,
                continue_command, callback_command, check_every_seconds,
                poll_timeout_seconds, max_retries, retry_count, next_run_at,
                locked_until, last_heartbeat_at, last_poll_at, last_error,
                context_json, created_at, updated_at, completed_at
            ) VALUES(?, ?, 'queued', ?, ?, ?, ?, ?, ?, ?, ?, 0, ?, NULL, NULL, NULL, NULL, ?, ?, ?, NULL)
            """,
            (
                job_id,
                workflow,
                remote_job_id,
                poll_command,
                fetch_command,
                continue_command,
                callback_command,
                check_every_seconds,
                poll_timeout_seconds,
                max_retries,
                now,
                json.dumps(context, ensure_ascii=True),
                now,
                now,
            ),
        )
        payload = {
            "workflow": workflow,
            "remote_job_id": remote_job_id,
            "check_every_seconds": check_every_seconds,
        }
        self.emit_event(job_id, "submitted", payload)
        self.conn.commit()
        return job_id

    def get_job(self, job_id: str) -> sqlite3.Row | None:
        cur = self.conn.execute("SELECT * FROM jobs WHERE id = ?", (job_id,))
        return cur.fetchone()

    def list_jobs(self, state: str | None, limit: int) -> list[sqlite3.Row]:
        params: list[Any] = []
        sql = "SELECT * FROM jobs"
        if state:
            sql += " WHERE status = ?"
            params.append(state)
        sql += " ORDER BY created_at DESC LIMIT ?"
        params.append(limit)
        cur = self.conn.execute(sql, params)
        return cur.fetchall()

    def due_jobs(self, limit: int, lock_seconds: int) -> list[sqlite3.Row]:
        now = iso_now()
        lock_until = iso_after(lock_seconds)
        cur = self.conn.execute(
            """
            SELECT id FROM jobs
            WHERE status IN ('queued', 'running', 'retry')
              AND next_run_at <= ?
              AND (locked_until IS NULL OR locked_until <= ?)
            ORDER BY next_run_at ASC
            LIMIT ?
            """,
            (now, now, limit),
        )
        ids = [row[0] for row in cur.fetchall()]
        if not ids:
            return []

        # Lightweight lock to avoid duplicate processing when timer overlaps.
        self.conn.executemany(
            "UPDATE jobs SET locked_until = ?, updated_at = ? WHERE id = ?",
            [(lock_until, now, job_id) for job_id in ids],
        )
        self.conn.commit()
        placeholders = ",".join(["?"] * len(ids))
        cur = self.conn.execute(
            f"SELECT * FROM jobs WHERE id IN ({placeholders}) ORDER BY next_run_at ASC", ids
        )
        return cur.fetchall()

    def update_job(self, job_id: str, **fields: Any) -> None:
        if not fields:
            return
        fields["updated_at"] = iso_now()
        columns = ", ".join(f"{key} = ?" for key in fields.keys())
        values = list(fields.values()) + [job_id]
        self.conn.execute(f"UPDATE jobs SET {columns} WHERE id = ?", values)

    def run_command(self, command: str, timeout_seconds: int, env: dict[str, str]) -> CmdResult:
        try:
            proc = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=timeout_seconds,
                env=env,
            )
            return CmdResult(
                returncode=proc.returncode,
                stdout=proc.stdout.strip(),
                stderr=proc.stderr.strip(),
                timed_out=False,
            )
        except subprocess.TimeoutExpired as exc:
            stdout = (exc.stdout or "").strip() if isinstance(exc.stdout, str) else ""
            stderr = (exc.stderr or "").strip() if isinstance(exc.stderr, str) else ""
            return CmdResult(returncode=124, stdout=stdout, stderr=stderr, timed_out=True)

    @staticmethod
    def _detect_state(context: dict[str, Any], output: str, rc: int, timed_out: bool) -> str:
        if timed_out:
            return "retry"

        done_regex = context.get("done_regex", DEFAULT_DONE_REGEX)
        failed_regex = context.get("failed_regex", DEFAULT_FAILED_REGEX)
        running_regex = context.get("running_regex", DEFAULT_RUNNING_REGEX)

        combined = output.upper()
        if re.search(done_regex, combined, flags=re.IGNORECASE):
            return "completed"
        if re.search(failed_regex, combined, flags=re.IGNORECASE):
            return "failed"
        if re.search(running_regex, combined, flags=re.IGNORECASE):
            return "running"

        if rc == 0:
            return "running"
        return "retry"

    @staticmethod
    def _backoff_seconds(job: sqlite3.Row) -> int:
        interval = max(1, int(job["check_every_seconds"]))
        retry_count = max(1, int(job["retry_count"]))
        backoff_max = DEFAULT_BACKOFF_MAX
        return min(backoff_max, interval * (2 ** min(6, retry_count)))

    def _state_env(self, job: sqlite3.Row, new_state: str) -> dict[str, str]:
        env = os.environ.copy()
        env["ORCH_JOB_ID"] = str(job["id"])
        env["ORCH_WORKFLOW"] = str(job["workflow"])
        env["ORCH_REMOTE_JOB_ID"] = str(job["remote_job_id"] or "")
        env["ORCH_OLD_STATUS"] = str(job["status"])
        env["ORCH_NEW_STATUS"] = new_state
        return env

    def _invoke_callback(self, job: sqlite3.Row, new_state: str, note: str) -> None:
        callback = job["callback_command"]
        if not callback:
            return
        env = self._state_env(job, new_state)
        env["ORCH_NOTE"] = note
        result = self.run_command(str(callback), timeout_seconds=60, env=env)
        payload = {
            "callback_command": callback,
            "returncode": result.returncode,
            "stdout": result.stdout,
            "stderr": result.stderr,
            "timed_out": result.timed_out,
        }
        event_type = "callback_ok" if result.returncode == 0 else "callback_error"
        self.emit_event(str(job["id"]), event_type, payload)

    def process_one(self, job: sqlite3.Row) -> None:
        job_id = str(job["id"])
        context = json.loads(str(job["context_json"]))
        poll_env = self._state_env(job, str(job["status"]))

        poll_result = self.run_command(
            str(job["poll_command"]),
            timeout_seconds=int(job["poll_timeout_seconds"]),
            env=poll_env,
        )
        combined_output = "\n".join([poll_result.stdout, poll_result.stderr]).strip()
        detected = self._detect_state(context, combined_output, poll_result.returncode, poll_result.timed_out)

        now = iso_now()
        payload = {
            "state_detected": detected,
            "returncode": poll_result.returncode,
            "timed_out": poll_result.timed_out,
            "stdout": poll_result.stdout,
            "stderr": poll_result.stderr,
        }
        self.emit_event(job_id, "poll", payload)

        base_fields: dict[str, Any] = {
            "last_heartbeat_at": now,
            "last_poll_at": now,
            "locked_until": None,
        }

        if detected == "completed":
            # Optional fetch for artifacts.
            if job["fetch_command"]:
                fetch_result = self.run_command(str(job["fetch_command"]), timeout_seconds=300, env=poll_env)
                self.emit_event(
                    job_id,
                    "fetch",
                    {
                        "returncode": fetch_result.returncode,
                        "stdout": fetch_result.stdout,
                        "stderr": fetch_result.stderr,
                        "timed_out": fetch_result.timed_out,
                    },
                )
                if fetch_result.returncode != 0:
                    detected = "retry"
                    base_fields["last_error"] = f"fetch failed rc={fetch_result.returncode}"

            if detected == "completed" and job["continue_command"]:
                next_result = self.run_command(str(job["continue_command"]), timeout_seconds=300, env=poll_env)
                self.emit_event(
                    job_id,
                    "continue",
                    {
                        "returncode": next_result.returncode,
                        "stdout": next_result.stdout,
                        "stderr": next_result.stderr,
                        "timed_out": next_result.timed_out,
                    },
                )
                if next_result.returncode != 0:
                    detected = "retry"
                    base_fields["last_error"] = f"continue failed rc={next_result.returncode}"

        if detected in ("running", "queued"):
            self.update_job(
                job_id,
                **base_fields,
                status="running",
                next_run_at=iso_after(int(job["check_every_seconds"])),
                last_error=None,
            )
            self.emit_event(job_id, "state_change", {"from": job["status"], "to": "running"})
            if job["status"] != "running":
                self._invoke_callback(job, "running", "Remote job now running.")
        elif detected == "completed":
            self.update_job(
                job_id,
                **base_fields,
                status="completed",
                next_run_at=iso_after(10 * 365 * 24 * 3600),
                completed_at=iso_now(),
                last_error=None,
            )
            self.emit_event(job_id, "state_change", {"from": job["status"], "to": "completed"})
            self._invoke_callback(job, "completed", "Job completed and handoff executed.")
        elif detected == "failed":
            self.update_job(
                job_id,
                **base_fields,
                status="failed",
                next_run_at=iso_after(10 * 365 * 24 * 3600),
                completed_at=iso_now(),
                last_error="poll output matched failed_regex",
            )
            self.emit_event(job_id, "state_change", {"from": job["status"], "to": "failed"})
            self._invoke_callback(job, "failed", "Job marked failed by poll output.")
        else:
            retry_count = int(job["retry_count"]) + 1
            if retry_count >= int(job["max_retries"]):
                self.update_job(
                    job_id,
                    **base_fields,
                    status="failed",
                    retry_count=retry_count,
                    next_run_at=iso_after(10 * 365 * 24 * 3600),
                    completed_at=iso_now(),
                    last_error=textwrap.shorten(combined_output or "retry limit reached", width=500),
                )
                self.emit_event(
                    job_id,
                    "state_change",
                    {
                        "from": job["status"],
                        "to": "failed",
                        "reason": "retry limit reached",
                    },
                )
                self._invoke_callback(job, "failed", "Retry limit reached.")
            else:
                delay = self._backoff_seconds(job)
                self.update_job(
                    job_id,
                    **base_fields,
                    status="retry",
                    retry_count=retry_count,
                    next_run_at=iso_after(delay),
                    last_error=textwrap.shorten(combined_output or "retry scheduled", width=500),
                )
                self.emit_event(
                    job_id,
                    "state_change",
                    {
                        "from": job["status"],
                        "to": "retry",
                        "retry_count": retry_count,
                        "next_delay_seconds": delay,
                    },
                )
                if job["status"] != "retry":
                    self._invoke_callback(job, "retry", f"Transient issue, retry in {delay}s")

        self.conn.commit()

    def tick(self, limit: int, lock_seconds: int, verbose: bool) -> int:
        jobs = self.due_jobs(limit=limit, lock_seconds=lock_seconds)
        processed = 0
        for job in jobs:
            processed += 1
            try:
                self.process_one(job)
                if verbose:
                    print(f"processed job={job['id']} status={job['status']}")
            except Exception as exc:  # noqa: BLE001
                self.update_job(
                    str(job["id"]),
                    status="retry",
                    retry_count=int(job["retry_count"]) + 1,
                    next_run_at=iso_after(max(60, int(job["check_every_seconds"]))),
                    locked_until=None,
                    last_error=textwrap.shorten(f"worker exception: {exc}", width=500),
                )
                self.emit_event(
                    str(job["id"]),
                    "worker_exception",
                    {"error": str(exc)},
                )
                self.conn.commit()
        return processed


def parse_key_value(items: list[str]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for item in items:
        if "=" not in item:
            raise ValueError(f"invalid key=value pair: {item}")
        key, value = item.split("=", 1)
        key = key.strip()
        value = value.strip()
        # Auto-cast booleans and ints for convenience.
        if value.isdigit():
            out[key] = int(value)
        elif value.lower() in ("true", "false"):
            out[key] = value.lower() == "true"
        else:
            out[key] = value
    return out


def print_job_row(row: sqlite3.Row) -> None:
    base = {
        "id": row["id"],
        "workflow": row["workflow"],
        "status": row["status"],
        "remote_job_id": row["remote_job_id"],
        "next_run_at": row["next_run_at"],
        "retry_count": row["retry_count"],
        "last_error": row["last_error"],
    }
    print(json.dumps(base, ensure_ascii=True))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Persistent remote job orchestrator")
    parser.add_argument(
        "--db",
        default=os.environ.get("ORCH_DB", os.path.expanduser("~/.local/share/openclaw-orchestrator/orchestrator.db")),
        help="SQLite database path",
    )

    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("init-db", help="Initialize SQLite schema")

    submit = sub.add_parser("submit", help="Create a new long-running job")
    submit.add_argument("--job-id", default=None, help="Optional explicit job id")
    submit.add_argument("--workflow", required=True, help="Workflow/group name")
    submit.add_argument("--remote-job-id", default=None, help="Remote scheduler job id")
    submit.add_argument("--poll-command", required=True, help="Command that checks remote status")
    submit.add_argument("--fetch-command", default=None, help="Command to download artifacts after completion")
    submit.add_argument("--continue-command", default=None, help="Command to launch downstream analysis")
    submit.add_argument("--callback-command", default=None, help="Command called on state changes")
    submit.add_argument("--check-every", type=int, default=DEFAULT_INTERVAL, help="Polling interval seconds")
    submit.add_argument("--poll-timeout", type=int, default=DEFAULT_POLL_TIMEOUT, help="Timeout for poll command")
    submit.add_argument("--max-retries", type=int, default=DEFAULT_MAX_RETRIES, help="Retry budget before failure")
    submit.add_argument(
        "--context",
        nargs="*",
        default=[],
        metavar="KEY=VALUE",
        help="Extra context values. Supports done_regex/failed_regex/running_regex.",
    )

    tick = sub.add_parser("tick", help="Run one scheduler tick")
    tick.add_argument("--limit", type=int, default=32, help="Max due jobs to process")
    tick.add_argument("--lock-seconds", type=int, default=600, help="Temporary processing lock")
    tick.add_argument("--verbose", action="store_true", help="Print per-job processing info")

    list_jobs = sub.add_parser("list", help="List jobs")
    list_jobs.add_argument("--state", default=None, help="Filter by state")
    list_jobs.add_argument("--limit", type=int, default=50)

    show = sub.add_parser("show", help="Show a job with recent events")
    show.add_argument("job_id", help="Job id")
    show.add_argument("--events", type=int, default=20, help="How many recent events to print")

    cancel = sub.add_parser("cancel", help="Cancel an active job")
    cancel.add_argument("job_id", help="Job id")

    return parser


def main(argv: list[str]) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    db_path = Path(args.db).expanduser()
    orch = Orchestrator(db_path)

    try:
        if args.command == "init-db":
            orch.init_db()
            print(f"initialized db at {db_path}")
            return 0

        orch.init_db()

        if args.command == "submit":
            context = parse_key_value(args.context)
            job_id = orch.submit_job(
                workflow=args.workflow,
                poll_command=args.poll_command,
                remote_job_id=args.remote_job_id,
                fetch_command=args.fetch_command,
                continue_command=args.continue_command,
                callback_command=args.callback_command,
                check_every_seconds=args.check_every,
                poll_timeout_seconds=args.poll_timeout,
                max_retries=args.max_retries,
                context=context,
                job_id=args.job_id,
            )
            print(job_id)
            return 0

        if args.command == "tick":
            processed = orch.tick(limit=args.limit, lock_seconds=args.lock_seconds, verbose=args.verbose)
            print(processed)
            return 0

        if args.command == "list":
            rows = orch.list_jobs(state=args.state, limit=args.limit)
            for row in rows:
                print_job_row(row)
            return 0

        if args.command == "show":
            row = orch.get_job(args.job_id)
            if not row:
                print(f"job not found: {args.job_id}", file=sys.stderr)
                return 2
            print(json.dumps({key: row[key] for key in row.keys()}, ensure_ascii=True, indent=2))
            cur = orch.conn.execute(
                """
                SELECT event_type, payload_json, created_at
                FROM events WHERE job_id = ?
                ORDER BY id DESC LIMIT ?
                """,
                (args.job_id, args.events),
            )
            print("recent_events:")
            for ev in cur.fetchall():
                print(
                    json.dumps(
                        {
                            "event_type": ev["event_type"],
                            "created_at": ev["created_at"],
                            "payload": json.loads(ev["payload_json"]),
                        },
                        ensure_ascii=True,
                    )
                )
            return 0

        if args.command == "cancel":
            row = orch.get_job(args.job_id)
            if not row:
                print(f"job not found: {args.job_id}", file=sys.stderr)
                return 2
            if row["status"] in FINAL_STATES:
                print(f"job already final: {row['status']}")
                return 0
            orch.update_job(
                args.job_id,
                status="cancelled",
                next_run_at=iso_after(10 * 365 * 24 * 3600),
                locked_until=None,
                completed_at=iso_now(),
                last_error="cancelled by operator",
            )
            orch.emit_event(args.job_id, "state_change", {"from": row["status"], "to": "cancelled"})
            orch.conn.commit()
            print(f"cancelled {args.job_id}")
            return 0

        parser.error(f"unknown command: {args.command}")
        return 2
    finally:
        orch.close()


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
