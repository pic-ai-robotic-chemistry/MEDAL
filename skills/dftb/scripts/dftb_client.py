#!/usr/bin/env python3
"""Submit/poll DFTB+ jobs via the unified HPC API."""
from __future__ import annotations

import argparse
import json
import time
import uuid
from pathlib import Path
from typing import Dict, Optional

import requests

DEFAULT_CONFIG_PATH = Path(__file__).resolve().parent / "config" / "dftb_config.json"
DEFAULT_EXAMPLE_CONFIG_PATH = Path(__file__).resolve().parent / "config" / "dftb_config.example.json"


def resolve_config_path(config_path: Optional[Path]) -> Path:
    if config_path:
        return Path(config_path)
    if DEFAULT_CONFIG_PATH.exists():
        return DEFAULT_CONFIG_PATH
    if DEFAULT_EXAMPLE_CONFIG_PATH.exists():
        return DEFAULT_EXAMPLE_CONFIG_PATH
    return DEFAULT_CONFIG_PATH


def load_config(config_path: Optional[Path]) -> Dict:
    path = resolve_config_path(config_path)
    if not path.exists():
        raise FileNotFoundError(
            f"DFTB config not found at {path}. Expected scripts/config/dftb_config.json or scripts/config/dftb_config.example.json."
        )

    with open(path, "r", encoding="utf-8") as handle:
        cfg = json.load(handle)

    required = ["api_base_url", "image"]
    for key in required:
        if not cfg.get(key):
            raise KeyError(f"Missing required '{key}' in {path}")

    return cfg


class DFTBClient:
    def __init__(self, config_path: Optional[Path] = None):
        self.cfg = load_config(config_path)
        base = self.cfg["api_base_url"].rstrip("/")
        self.submit_endpoint = self.cfg.get("submit_endpoint", f"{base}/api/jobs")
        self.status_endpoint = self.cfg.get("status_endpoint", f"{base}/api/jobs")
        self.download_endpoint = self.cfg.get("download_endpoint", f"{base}/api/tasks/download")
        self.auth_token = self.cfg.get("auth_token")
        self.image = self.cfg["image"]
        self.created_by = self.cfg.get("created_by", "openclaw")
        self.poll_interval = self.cfg.get("poll_interval_seconds", 15)
        self.max_attempts = self.cfg.get("max_poll_attempts", 720)
        self.default_software = self.cfg.get("software", "DFTB+")
        self.default_cmd = self.cfg.get("default_cmd", "srun --mpi=pmi2 dftb+ > output.out")
        self.default_mem = self.cfg.get("mem", "4GB")
        self.default_tasks_per_node = self.cfg.get("tasks_per_node", 8)
        self.default_n_nodes = self.cfg.get("n_nodes", 1)

    def submit(self, file_url: str, tasks_per_node: Optional[int] = None,
               n_nodes: Optional[int] = None, mem: Optional[str] = None,
               cmd: Optional[str] = None, parent_id: Optional[str] = None,
               task_id: Optional[str] = None, created_by: Optional[str] = None) -> Dict:
        task_uuid = task_id or str(uuid.uuid4())
        parent_uuid = parent_id or task_uuid
        rendered_cmd = cmd or self.default_cmd
        payload = {
            "params": {
                "inputfile": file_url,
                "software": self.default_software,
                "cmd": rendered_cmd,
                "n_nodes": n_nodes or self.default_n_nodes,
                "tasks_per_node": tasks_per_node or self.default_tasks_per_node,
                "mem": mem or self.default_mem,
            },
            "image": self.image,
            "parentId": parent_uuid,
            "taskId": task_uuid,
            "createdBy": created_by or self.created_by,
        }

        headers = {"Content-Type": "application/json"}
        if self.auth_token:
            headers["Authorization"] = f"Bearer {self.auth_token}"

        print(f"[SUBMIT] POST {self.submit_endpoint} (software={self.default_software}, cmd={rendered_cmd})")
        response = requests.post(self.submit_endpoint, json=payload, headers=headers)
        response.raise_for_status()
        data = response.json()
        job_id = data.get("data", {}).get("id")
        if job_id is None:
            raise RuntimeError(f"Submission succeeded but no job id found: {data}")

        result = {
            "job_id": job_id,
            "task_id": task_uuid,
            "parent_id": parent_uuid,
            "cmd": rendered_cmd,
            "payload": data,
        }
        print(f"[SUBMIT] job_id = {job_id} | task_id = {task_uuid}")
        return result

    def poll(self, job_id: int) -> Dict:
        headers = {}
        if self.auth_token:
            headers["Authorization"] = f"Bearer {self.auth_token}"

        for attempt in range(1, self.max_attempts + 1):
            response = requests.get(self.status_endpoint, params={"id": job_id}, headers=headers)
            response.raise_for_status()
            payload = response.json()
            data_field = payload.get("data", {})
            status = data_field.get("status") if isinstance(data_field, dict) else None

            if status in {"PENDING", "DISPATCHED", "RUNNING"}:
                print(f"[POLL] job_id={job_id} status={status} ({attempt}/{self.max_attempts})")
                time.sleep(self.poll_interval)
                continue

            print(f"[POLL] job_id={job_id} finished with status={status}")
            return payload

        raise TimeoutError(
            f"Task {job_id} did not finish within {self.max_attempts * self.poll_interval / 60:.1f} minutes"
        )

    def build_download_url(self, task_id: str) -> str:
        return f"{self.download_endpoint}?taskId={task_id}"


def build_cli() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Submit/poll DFTB+ jobs via the unified HPC API")
    parser.add_argument("--config", help="Path to dftb_config.json (defaults to scripts/config/dftb_config.json)")
    sub = parser.add_subparsers(dest="command", required=True)

    submit = sub.add_parser("submit", help="Submit a DFTB job")
    submit.add_argument("file_url", help="Remote ZIP URL accepted by the HPC API")
    submit.add_argument("--tasks-per-node", type=int)
    submit.add_argument("--nodes", type=int)
    submit.add_argument("--mem")
    submit.add_argument("--cmd", help="Override remote execution command")
    submit.add_argument("--parent-id")
    submit.add_argument("--task-id")
    submit.add_argument("--created-by")

    poll = sub.add_parser("poll", help="Poll an existing job ID")
    poll.add_argument("job_id", type=int, help="Integer job ID returned by the submit step")

    download = sub.add_parser("download-url", help="Construct the download URL for a taskId")
    download.add_argument("task_id", help="UUID taskId used at submit time")

    return parser


def main() -> None:
    parser = build_cli()
    args = parser.parse_args()

    client = DFTBClient(args.config)
    if args.command == "submit":
        result = client.submit(
            file_url=args.file_url,
            tasks_per_node=getattr(args, "tasks_per_node", None),
            n_nodes=getattr(args, "nodes", None),
            mem=getattr(args, "mem", None),
            cmd=getattr(args, "cmd", None),
            parent_id=getattr(args, "parent_id", None),
            task_id=getattr(args, "task_id", None),
            created_by=getattr(args, "created_by", None),
        )
        print(json.dumps(result, ensure_ascii=False))
    elif args.command == "poll":
        payload = client.poll(args.job_id)
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(client.build_download_url(args.task_id))


if __name__ == "__main__":
    main()
