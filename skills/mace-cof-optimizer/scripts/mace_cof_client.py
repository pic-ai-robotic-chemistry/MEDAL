#!/usr/bin/env python3
"""Client utilities for submitting/polling MACE COF optimizations via the remote scorer API."""
from __future__ import annotations

import argparse
import json
import os
import time
from pathlib import Path
from typing import Dict, List, Optional

import requests

JSON_GET_HEADERS = {"Content-Type": "application/json", "Accept": "application/json"}

DEFAULT_CONFIG_PATH = Path(__file__).resolve().parent / "config" / "mace_optimizer_config.json"


# ---------------------------------------------------------------------------
# Helper functions provided by the user (kept verbatim where possible)
# ---------------------------------------------------------------------------
def cifs_from_folder(folder_path: Path) -> Dict[str, str]:
    """Read all .cif files in a folder and return a filename->content mapping."""
    cifs: Dict[str, str] = {}
    for name in sorted(os.listdir(folder_path)):
        if not name.lower().endswith(".cif"):
            continue
        path = folder_path / name
        if not path.is_file():
            continue
        cifs[name] = path.read_text()
    return cifs


def get_opt_only_input_json(folder_path: Path, name: str) -> Dict:
    cifs = cifs_from_folder(folder_path)
    return {
        "name": name,
        "job": ["optimization"],
        "ignore_exist": True,
        "cifs": cifs,
        "optimization_conf": {
            "optimizer": "maceoff",
            "gpu_offset": 2,
            "gpu_cnt": 6,
            "jobs_per_gpu": 12,
            "press_first": False,
        },
    }


# ---------------------------------------------------------------------------
# Client wrapper
# ---------------------------------------------------------------------------
class MACEOptimizerClient:
    def __init__(self, config_path: Optional[Path] = None):
        self.cfg = self._load_config(config_path)
        base = self.cfg["scorer_url"].rstrip("/")
        self.submit_url = self.cfg.get("submit_url", f"{base}/submit")
        self.poll_url = self.cfg.get("poll_url", f"{base}/status")
        self.result_url = self.cfg.get("result_url", f"{base}/result")
        self.result_cifs_url = self.cfg.get("result_cifs_url", f"{base}/result_cifs")
        self.poll_interval = self.cfg.get("poll_interval_seconds", 100)
        self.poll_timeout = self.cfg.get("poll_timeout_seconds", 3600)
        self.request_timeout = self.cfg.get("request_timeout_seconds", 120)

    @staticmethod
    def _load_config(config_path: Optional[Path]) -> Dict:
        path = Path(config_path or DEFAULT_CONFIG_PATH)
        if not path.exists():
            raise FileNotFoundError(
                f"Config not found at {path}. Copy scripts/config/mace_optimizer_config.example.json and fill it in."
            )
        with open(path, "r", encoding="utf-8") as handle:
            cfg = json.load(handle)
        if "scorer_url" not in cfg or not cfg["scorer_url"]:
            raise KeyError("Config must contain 'scorer_url'.")
        return cfg

    # --------------------------- Submission ---------------------------------
    def submit_folder(self, folder: Path, job_name: str) -> Dict:
        payload = get_opt_only_input_json(folder, job_name)
        print(f"[SUBMIT] -> {self.submit_url} (job={job_name}, cif_count={len(payload['cifs'])}, cif_names={list(payload['cifs'].keys())})")
        resp = requests.post(self.submit_url, json=payload, timeout=(30, 600))
        resp.raise_for_status()
        data = resp.json()
        job_id = data.get("job_id")
        if not job_id:
            raise RuntimeError(f"Submit response missing job_id: {data}")
        print(f"[SUBMIT] job_id={job_id}")
        return data

    # ----------------------------- Polling ----------------------------------
    def poll(self, job_id: str) -> Dict:
        start = time.time()
        while True:
            try:
                resp = requests.get(f"{self.poll_url}/{job_id}", timeout=self.request_timeout)
                resp.raise_for_status()
                payload = resp.json()
            except requests.exceptions.RequestException as exc:
                elapsed = int(time.time() - start)
                print(f"[POLL] request error: {exc} (elapsed={elapsed}s) -> retrying")
                time.sleep(self.poll_interval)
                continue

            status = payload.get("status")
            if status == "finished":
                print(f"[POLL] job_id={job_id} finished")
                return payload

            elapsed = time.time() - start
            if elapsed > self.poll_timeout:
                raise TimeoutError(
                    f"Polling timed out after {self.poll_timeout} seconds (last status={status})."
                )

            print(f"[POLL] status={status}, elapsed={int(elapsed)}s")
            time.sleep(self.poll_interval)

    # --------------------------- Result fetchers ----------------------------
    def get_result(self, job_id: Optional[str] = None, job_name: Optional[str] = None) -> Dict:
        params = self._build_query(job_id, job_name)
        resp = requests.get(
            self.result_url,
            params=params,
            headers=JSON_GET_HEADERS,
            timeout=self.request_timeout,
        )
        self._raise_for_status_with_body(resp)
        return resp.json()

    def get_result_cifs(
        self,
        job_id: Optional[str] = None,
        job_name: Optional[str] = None,
        save_dir: Optional[Path] = None,
    ) -> Dict:
        payload = self._build_result_cifs_payload(job_id, job_name)
        resp = requests.request(
            "GET",
            self.result_cifs_url,
            json=payload,
            headers=JSON_GET_HEADERS,
            timeout=self.request_timeout,
        )
        self._raise_for_status_with_body(resp)
        data = resp.json()

        if save_dir:
            self._write_cifs(data, save_dir)
        return data

    @staticmethod
    def _build_query(job_id: Optional[str], job_name: Optional[str]) -> Dict:
        if not job_id and not job_name:
            raise ValueError("Provide job_id or job_name when fetching results.")
        params = {}
        if job_id:
            params["job_id"] = job_id
        if job_name:
            params["job_name"] = job_name
        return params

    @staticmethod
    def _build_result_cifs_payload(job_id: Optional[str], job_name: Optional[str]) -> Dict:
        if not job_id and not job_name:
            raise ValueError("Provide job_id or job_name when fetching CIF results.")
        payload = {}
        if job_id:
            payload["job_id"] = job_id
        if job_name:
            payload["name"] = job_name
        return payload

    @staticmethod
    def _raise_for_status_with_body(resp: requests.Response) -> None:
        try:
            resp.raise_for_status()
        except requests.exceptions.HTTPError as exc:
            body = (resp.text or "")[:1000]
            raise requests.exceptions.HTTPError(
                f"{exc} | response_body={body}",
                response=resp,
                request=resp.request,
            ) from exc

    @staticmethod
    def _write_cifs(data: Dict, target_dir: Path) -> None:
        target_dir.mkdir(parents=True, exist_ok=True)
        cifs = data.get("cifs") or data.get("result_cifs") or []

        if isinstance(cifs, dict):
            items = list(cifs.items())
        elif isinstance(cifs, list):
            items = [(f"structure_{idx:03d}.cif", cif_text) for idx, cif_text in enumerate(cifs, start=1)]
        else:
            raise RuntimeError("Unexpected CIF payload (expected dict or list).")

        for idx, (filename, cif_text) in enumerate(items, start=1):
            safe_name = Path(filename).name if filename else f"structure_{idx:03d}.cif"
            path = target_dir / safe_name
            path.write_text(str(cif_text).strip() + "\n")
        print(f"[RESULT] wrote {len(items)} CIFs to {target_dir}")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def build_cli() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Submit and monitor MACE COF optimizations")
    parser.add_argument(
        "--config",
        help="Path to mace_optimizer_config.json (defaults to scripts/config/mace_optimizer_config.json)",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    submit = sub.add_parser("submit", help="Submit all CIFs in a folder")
    submit.add_argument("folder", help="Folder containing CIF files")
    submit.add_argument("name", help="Job name")

    poll = sub.add_parser("poll", help="Poll until the job finishes")
    poll.add_argument("job_id", help="Job ID returned by submit")

    result = sub.add_parser("result", help="Fetch job metadata/status once finished")
    result.add_argument("--job-id", dest="job_id")
    result.add_argument("--job-name", dest="job_name")

    cifs = sub.add_parser("cifs", help="Fetch optimized CIFs and optionally dump them to disk")
    cifs.add_argument("--job-id", dest="job_id")
    cifs.add_argument("--job-name", dest="job_name")
    cifs.add_argument("--out", dest="output", help="Directory to save CIF files")

    return parser


def main() -> None:
    parser = build_cli()
    args = parser.parse_args()
    client = MACEOptimizerClient(args.config)

    if args.command == "submit":
        folder = Path(args.folder).expanduser().resolve()
        resp = client.submit_folder(folder, args.name)
        print(json.dumps(resp, ensure_ascii=False, indent=2))
    elif args.command == "poll":
        payload = client.poll(args.job_id)
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    elif args.command == "result":
        payload = client.get_result(job_id=args.job_id, job_name=args.job_name)
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        payload = client.get_result_cifs(
            job_id=args.job_id,
            job_name=args.job_name,
            save_dir=Path(args.output).expanduser().resolve() if args.output else None,
        )
        print(json.dumps(payload, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
