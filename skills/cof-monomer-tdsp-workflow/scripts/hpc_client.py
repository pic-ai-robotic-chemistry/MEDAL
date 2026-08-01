import json
import shutil
import subprocess
import sys
import time
import uuid
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional, Tuple

import requests


class SupercomputerClient:
    """HTTP client for the unified HPC API used by the COF monomer workflow."""

    def _debug(self, message: str):
        stamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        line = f"[{stamp}] {message}"
        print(line, flush=True)
        if self.debug_log_path:
            try:
                with open(self.debug_log_path, "a", encoding="utf-8") as handle:
                    handle.write(line + "\n")
            except Exception:
                pass

    def __init__(self, config_path: str):
        self.config_path = Path(config_path)
        if not self.config_path.exists():
            raise FileNotFoundError(f"Supercomputer config not found: {config_path}")

        with open(self.config_path, "r", encoding="utf-8") as f:
            cfg = json.load(f)

        self.upload_endpoint = cfg["upload_endpoint"].rstrip("/")
        self.file_upload_token = cfg.get("file_upload_token")
        self.file_upload_header = cfg.get("file_upload_header", "FILE_UPLOAD_IDENTIFIES")
        self.api_base_url = cfg["api_base_url"].rstrip("/")
        self.submit_endpoint = cfg.get("submit_endpoint", f"{self.api_base_url}/api/jobs")
        self.status_endpoint = cfg.get("status_endpoint", f"{self.api_base_url}/api/jobs")
        self.download_endpoint = cfg.get("download_endpoint", f"{self.api_base_url}/api/tasks/download")
        self.auth_token = cfg.get("auth_token")
        self.image = cfg["image"]
        self.created_by = cfg.get("created_by", "openclaw")
        self.poll_interval = cfg.get("poll_interval_seconds", 120)
        self.max_poll_attempts = cfg.get("max_poll_attempts", 2880)
        self.tasks_per_node = cfg.get("tasks_per_node", 64)
        self.n_nodes = cfg.get("n_nodes", 1)
        self.mem = cfg.get("mem", "32GB")
        self.software = cfg.get("software", "GAUSSIAN")
        self.default_cmd = cfg.get("default_cmd", "g16 {input_gjf} && formchk {input_chk}")
        self.default_objective = cfg.get("objective", "计算")
        self.objective_map = cfg.get("objective_map", {})
        self.download_headers = cfg.get("download_headers", {
            "User-Agent": "Mozilla/5.0",
            "Connection": "keep-alive"
        })
        self.upload_timeout = tuple(cfg.get("upload_timeout_seconds", [15, 120]))
        self.submit_timeout = tuple(cfg.get("submit_timeout_seconds", [15, 120]))
        self.status_timeout = tuple(cfg.get("status_timeout_seconds", [15, 60]))
        self.debug_log_path = cfg.get("debug_log_path")
        self.upload_max_retries = cfg.get("upload_max_retries", 6)
        self.submit_max_retries = cfg.get("submit_max_retries", 4)
        self.poll_error_max_retries = cfg.get("poll_error_max_retries", 6)
        self.retry_delay_seconds = cfg.get("retry_delay_seconds", 15)

    @staticmethod
    def _build_gjf_zip(gjf_path: Path) -> Path:
        zip_path = gjf_path.with_suffix(".zip")
        with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zip_ref:
            zip_ref.write(gjf_path, arcname=gjf_path.name)
        return zip_path

    @staticmethod
    def _render_cmd(gjf_name: str, cmd_template: str) -> str:
        stem = Path(gjf_name).stem
        return cmd_template.format(input_gjf=gjf_name, input_chk=f"{stem}.chk")

    def submit_gaussian_job(self, gjf_path: Path, job_type: Optional[str] = None) -> Dict:
        gjf_path = Path(gjf_path)
        if not gjf_path.exists():
            raise FileNotFoundError(f"GJF file not found: {gjf_path}")

        zip_path = self._build_gjf_zip(gjf_path)
        file_url, _ = self._upload_file(zip_path)
        objective = self.objective_map.get(job_type, self.default_objective)
        cmd = self._render_cmd(gjf_path.name, self.default_cmd)
        return self._submit_task(file_url=file_url, cmd=cmd, objective=objective)

    def wait_for_completion(self, job_id: int) -> Dict:
        attempts = 0
        poll_errors = 0
        while attempts < self.max_poll_attempts:
            try:
                payload = self._poll_result(job_id)
                poll_errors = 0
            except Exception as exc:
                poll_errors += 1
                self._debug(f"[POLL] Error for job {job_id}: {exc} ({poll_errors}/{self.poll_error_max_retries})")
                if poll_errors >= self.poll_error_max_retries:
                    raise RuntimeError(f"Polling failed repeatedly for job {job_id}: {exc}")
                time.sleep(self.retry_delay_seconds)
                continue

            data = payload.get("data", {})
            status = data.get("status") if isinstance(data, dict) else None
            if status in {"PENDING", "DISPATCHED", "RUNNING"}:
                self._debug(f"[HPC] Job {job_id} running with status={status}... ({attempts + 1}/{self.max_poll_attempts})")
                attempts += 1
                time.sleep(self.poll_interval)
                continue

            self._debug(f"[HPC] Job {job_id} finished with status={status}.")
            return payload

        raise TimeoutError(
            f"Job {job_id} did not finish within {self.max_poll_attempts * self.poll_interval / 60:.1f} minutes"
        )

    def download_results(self, task_id: str, target_dir: Path, job_name: str) -> Dict[str, Path]:
        result_url = f"{self.download_endpoint}?taskId={task_id}"

        target_dir = Path(target_dir)
        target_dir.mkdir(parents=True, exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        job_output_root = target_dir / f"{job_name}_remote_{timestamp}"
        job_output_root.mkdir(parents=True, exist_ok=True)

        zip_filename = f"{task_id}.zip"
        zip_path = job_output_root / zip_filename
        self._download_file(result_url, zip_path)

        extract_dir = job_output_root / task_id
        extract_dir.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(zip_path, "r") as zip_ref:
            zip_ref.extractall(extract_dir)

        log_src = self._find_log_artifact(extract_dir, job_name)
        fchk_src = self._find_artifact(extract_dir, job_name, suffix=".fchk")
        chk_src = self._find_artifact(extract_dir, job_name, suffix=".chk")

        if not fchk_src and chk_src:
            generated_fchk = extract_dir / f"{job_name}.fchk"
            fchk_src = self._generate_fchk_from_chk(chk_src, generated_fchk)

        if not log_src or not fchk_src:
            search_hint = " | ".join(str(p) for p in extract_dir.rglob("*"))
            raise FileNotFoundError(
                f"Unable to locate usable .log/.fchk in extracted results for {job_name}. Contents: {search_hint}"
            )

        log_dst = target_dir / f"{job_name}.log"
        fchk_dst = target_dir / f"{job_name}.fchk"
        shutil.copy2(log_src, log_dst)
        shutil.copy2(fchk_src, fchk_dst)

        return {
            "log": log_dst,
            "fchk": fchk_dst,
            "extract_dir": extract_dir,
            "zip_path": zip_path
        }

    def _upload_file(self, file_path: Path) -> Tuple[str, Dict]:
        headers = {}
        if self.file_upload_token:
            headers[self.file_upload_header] = self.file_upload_token

        last_error = None
        for attempt in range(1, self.upload_max_retries + 1):
            self._debug(f"[UPLOAD] Attempt {attempt}/{self.upload_max_retries} uploading {file_path} -> {self.upload_endpoint} | timeout={self.upload_timeout}")
            try:
                with open(file_path, "rb") as handle:
                    files = {"file": (file_path.name, handle)}
                    response = requests.post(self.upload_endpoint, headers=headers, files=files, timeout=self.upload_timeout)
                self._debug(f"[UPLOAD] Response status={response.status_code}")
                response.raise_for_status()
                data = response.json()
                url = None
                if isinstance(data, dict):
                    if isinstance(data.get("data"), str):
                        url = data.get("data")
                    elif isinstance(data.get("path"), str):
                        url = data.get("path")
                    elif isinstance(data.get("result"), dict):
                        result = data.get("result") or {}
                        if isinstance(result.get("data"), str):
                            url = result.get("data")
                        elif isinstance(result.get("path"), str):
                            url = result.get("path")
                if url:
                    self._debug(f"[UPLOAD] Success. Remote URL: {url}")
                    return url, data
                last_error = RuntimeError(f"Upload response missing remote path field: {data}")
                self._debug(f"[UPLOAD] Attempt {attempt} returned unusable payload: {data}")
            except Exception as exc:
                last_error = exc
                self._debug(f"[UPLOAD] Attempt {attempt} failed: {exc}")

            if attempt < self.upload_max_retries:
                time.sleep(self.retry_delay_seconds)

        raise RuntimeError(f"Upload failed after {self.upload_max_retries} attempts: {last_error}")

    def _submit_task(self, file_url: str, cmd: str, objective: str) -> Dict:
        headers = {"Content-Type": "application/json"}
        if self.auth_token:
            headers["Authorization"] = f"Bearer {self.auth_token}"

        last_error = None
        for attempt in range(1, self.submit_max_retries + 1):
            task_uuid = str(uuid.uuid4())
            payload = {
                "params": {
                    "inputfile": file_url,
                    "software": self.software,
                    "cmd": cmd,
                    "n_nodes": self.n_nodes,
                    "tasks_per_node": self.tasks_per_node,
                    "mem": self.mem,
                    "objective": objective,
                },
                "image": self.image,
                "parentId": task_uuid,
                "taskId": task_uuid,
                "createdBy": self.created_by,
            }
            try:
                self._debug(f"[SUBMIT] Attempt {attempt}/{self.submit_max_retries} POST {self.submit_endpoint} | software={self.software} | cmd={cmd} | timeout={self.submit_timeout}")
                response = requests.post(self.submit_endpoint, json=payload, headers=headers, timeout=self.submit_timeout)
                self._debug(f"[SUBMIT] Response status={response.status_code}")
                response.raise_for_status()
                result = response.json()
                job_id = result.get("data", {}).get("id")
                if job_id is None:
                    raise RuntimeError(f"Submission response missing data.id: {result}")
                self._debug(f"[SUBMIT] Submission accepted. Job ID: {job_id} | taskId: {task_uuid}")
                return {"job_id": job_id, "task_id": task_uuid, "payload": result}
            except Exception as exc:
                last_error = exc
                self._debug(f"[SUBMIT] Attempt {attempt} failed: {exc}")
                if attempt < self.submit_max_retries:
                    time.sleep(self.retry_delay_seconds)

        raise RuntimeError(f"Submission failed after {self.submit_max_retries} attempts: {last_error}")

    def _poll_result(self, job_id: int) -> Dict:
        headers = {}
        if self.auth_token:
            headers["Authorization"] = f"Bearer {self.auth_token}"
        self._debug(f"[POLL] GET {self.status_endpoint}?id={job_id} | timeout={self.status_timeout}")
        response = requests.get(self.status_endpoint, params={"id": job_id}, headers=headers, timeout=self.status_timeout)
        self._debug(f"[POLL] Response status={response.status_code}")
        response.raise_for_status()
        payload = response.json()
        self._debug(f"[POLL] Payload excerpt: {json.dumps(payload, ensure_ascii=False)[:500]}")
        return payload

    def _download_file(self, url: str, dest: Path):
        self._debug(f"[DOWNLOAD] Fetching {url} via curl -C - ...")
        if dest.exists() and dest.is_dir():
            raise IsADirectoryError(f"Download destination is a directory: {dest}")
        dest.parent.mkdir(parents=True, exist_ok=True)
        tmp_dest = dest.with_name(dest.name + '.part')
        if tmp_dest.exists() and tmp_dest.is_dir():
            raise IsADirectoryError(f"Temporary download destination is a directory: {tmp_dest}")
        cmd = [
            "curl", "--fail", "--location", "--retry", "100", "--retry-delay", "10",
            "--retry-all-errors", "--connect-timeout", "30", "--speed-time", "600",
            "--speed-limit", "1024", "-C", "-", "-o", str(tmp_dest), url,
        ]
        for key, value in self.download_headers.items():
            cmd.extend(["-H", f"{key}: {value}"])

        result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        if result.returncode != 0:
            self._debug(f"[DOWNLOAD] curl failed with rc={result.returncode}: {result.stdout[-4000:]}")
            raise RuntimeError(f"curl resume download failed for {url}")

        tmp_dest.replace(dest)
        self._debug(f"[DOWNLOAD] Saved to {dest}")

    @staticmethod
    def _find_artifact(extract_dir: Path, job_name: str, suffix: str) -> Optional[Path]:
        preferred = list(extract_dir.rglob(f"{job_name}{suffix}"))
        if preferred:
            return preferred[0]
        generic = list(extract_dir.rglob(f"*{suffix}"))
        return generic[0] if generic else None

    @staticmethod
    def _find_log_artifact(extract_dir: Path, job_name: str) -> Optional[Path]:
        preferred_names = [f"{job_name}.log", f"job_gaussian_{job_name}.log", "input.log", "g16.out.log"]
        for name in preferred_names:
            matches = list(extract_dir.rglob(name))
            if matches:
                return matches[0]
        gaussian_logs = sorted(extract_dir.rglob("job_gaussian*.log"))
        if gaussian_logs:
            return gaussian_logs[0]
        return SupercomputerClient._find_artifact(extract_dir, job_name, suffix=".log")

    @staticmethod
    def _generate_fchk_from_chk(chk_path: Path, output_fchk: Path) -> Optional[Path]:
        try:
            result = subprocess.run(
                ["formchk", str(chk_path), str(output_fchk)],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=180,
                check=False,
            )
            if result.returncode == 0 and output_fchk.exists():
                return output_fchk
            sys.stderr.write(f"[WARN] formchk failed for {chk_path}: rc={result.returncode}\n{result.stderr}\n")
        except Exception as exc:
            sys.stderr.write(f"[WARN] formchk exception for {chk_path}: {exc}\n")
        return None
