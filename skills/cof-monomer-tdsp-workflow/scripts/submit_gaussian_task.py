#!/usr/bin/env python3
"""Legacy helper retained as a minimal unified-HPC Gaussian example."""

import json
import os
import subprocess
import time
import uuid
import zipfile
from pathlib import Path

import requests

API_BASE = "https://your-own-hpc-api.example.com"
SUBMIT_ENDPOINT = f"{API_BASE}/api/jobs"
STATUS_ENDPOINT = f"{API_BASE}/api/jobs"
DOWNLOAD_ENDPOINT = f"{API_BASE}/api/tasks/download"
UPLOAD_ENDPOINT = "https://your-own-upload-api.example.com/api/file/upload"
UPLOAD_TOKEN = "PLEASE_SET_YOUR_OWN_UPLOAD_TOKEN"
UPLOAD_HEADER = "YOUR_UPLOAD_AUTH_HEADER"
IMAGE = "PLEASE_SET_YOUR_OWN_CONTAINER_IMAGE"
DEFAULT_CMD = "g16 {input_gjf} && formchk {input_chk}"


def upload_file(file_path: str):
    headers = {UPLOAD_HEADER: UPLOAD_TOKEN}
    with open(file_path, "rb") as f:
        files = {"file": (os.path.basename(file_path), f)}
        response = requests.post(UPLOAD_ENDPOINT, headers=headers, files=files)
    response.raise_for_status()
    result = response.json()
    return result["data"], result


def zip_gjf(gjf_path: str) -> str:
    gjf = Path(gjf_path)
    zip_path = gjf.with_suffix(".zip")
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.write(gjf, arcname=gjf.name)
    return str(zip_path)


def submit_gaussian_task(file_url: str, input_gjf_name: str, tasks_per_node=64, n_nodes=1, mem="32GB"):
    stem = Path(input_gjf_name).stem
    task_id = str(uuid.uuid4())
    cmd = DEFAULT_CMD.format(input_gjf=Path(input_gjf_name).name, input_chk=f"{stem}.chk")
    payload = {
        "params": {
            "inputfile": file_url,
            "software": "GAUSSIAN",
            "cmd": cmd,
            "n_nodes": n_nodes,
            "tasks_per_node": tasks_per_node,
            "mem": mem,
        },
        "image": IMAGE,
        "parentId": task_id,
        "taskId": task_id,
        "createdBy": "openclaw",
    }
    response = requests.post(SUBMIT_ENDPOINT, json=payload, headers={"Content-Type": "application/json"})
    response.raise_for_status()
    result = response.json()
    return {"job_id": result["data"]["id"], "task_id": task_id, "payload": result}


def poll_gaussian_result(job_id: int, poll_interval=15):
    while True:
        response = requests.get(STATUS_ENDPOINT, params={"id": job_id})
        response.raise_for_status()
        payload = response.json()
        status = payload.get("data", {}).get("status")
        if status in {"PENDING", "DISPATCHED", "RUNNING"}:
            print(f"[{time.strftime('%X')}] status={status}, waiting...")
            time.sleep(poll_interval)
            continue
        return payload


def download_result(task_id: str, output_zip: str):
    url = f"{DOWNLOAD_ENDPOINT}?taskId={task_id}"
    cmd = ["curl", "--fail", "--location", "-o", output_zip, url]
    subprocess.run(cmd, check=True)
    return output_zip


if __name__ == "__main__":
    LOCAL_FILE = "benzene.gjf"
    zipped = zip_gjf(LOCAL_FILE)
    uploaded_url, _ = upload_file(zipped)
    submission = submit_gaussian_task(uploaded_url, input_gjf_name=Path(LOCAL_FILE).name)
    final_data = poll_gaussian_result(submission["job_id"], poll_interval=15)
    print(json.dumps(final_data, indent=2, ensure_ascii=False))
    download_result(submission["task_id"], f"{submission['task_id']}.zip")
