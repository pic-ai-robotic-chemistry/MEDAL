#!/usr/bin/env python3
"""Helper utilities for uploading calculation input files to the remote worker service.

The script reads credentials + endpoints from a JSON config file to avoid hard-coding
private infrastructure values directly in the skill.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Dict, Optional, Tuple

import requests

DEFAULT_CONFIG_PATH = Path(__file__).resolve().parent / "config" / "file_upload_config.json"
DEFAULT_EXAMPLE_CONFIG_PATH = Path(__file__).resolve().parent / "config" / "file_upload_config.example.json"


class FileUploadError(RuntimeError):
    """Raised when the upload service responds with a non-success payload."""


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
            f"Upload config not found at {path}. Expected config/file_upload_config.json or config/file_upload_config.example.json."
        )

    with open(path, "r", encoding="utf-8") as handle:
        cfg = json.load(handle)

    required_keys = ["upload_endpoint"]
    for key in required_keys:
        if key not in cfg or not cfg[key]:
            raise KeyError(f"Missing required '{key}' in {path}")

    return cfg


def upload_file(
    file_path: Path,
    config_path: Optional[Path] = None,
    file_field: Optional[str] = None,
) -> Tuple[str, Dict]:
    cfg = load_config(config_path)
    endpoint = cfg["upload_endpoint"].rstrip("/")
    token = cfg.get("file_upload_token")
    header_name = cfg.get("file_upload_header", "FILE_UPLOAD_IDENTIFIES")
    timeout = cfg.get("timeout_seconds", 60)
    field_name = file_field or cfg.get("file_field_name", "file")

    if not file_path.exists():
        raise FileNotFoundError(f"输入文件不存在: {file_path}")

    headers = dict(cfg.get("extra_headers", {}))
    if token:
        headers[header_name] = token

    print(f"[UPLOAD] POST {endpoint} ({file_path.name})")
    with open(file_path, "rb") as handle:
        files = {field_name: (file_path.name, handle)}
        response = requests.post(endpoint, headers=headers, files=files, timeout=timeout)

    response.raise_for_status()
    payload = response.json()

    remote_path = None
    if isinstance(payload, dict):
        if isinstance(payload.get("data"), str):
            remote_path = payload.get("data")
        elif isinstance(payload.get("path"), str):
            remote_path = payload.get("path")
        elif isinstance(payload.get("result"), dict):
            result = payload.get("result") or {}
            if isinstance(result.get("data"), str):
                remote_path = result.get("data")
            elif isinstance(result.get("path"), str):
                remote_path = result.get("path")

    if not remote_path:
        raise FileUploadError(f"Upload succeeded but remote path was not found in response: {payload}")

    print(f"[UPLOAD] success → {remote_path}")
    return remote_path, payload


def main() -> None:
    parser = argparse.ArgumentParser(description="Upload a Gaussian/DFTB input archive via the worker service")
    parser.add_argument("file", help="Path to the local file to upload")
    parser.add_argument(
        "--config",
        help="Optional path to a JSON config. Defaults to scripts/config/file_upload_config.json",
    )
    parser.add_argument(
        "--field",
        help="Override the multipart field name (defaults to config or 'file')",
    )
    args = parser.parse_args()

    remote_path, payload = upload_file(Path(args.file), args.config, args.field)
    print(json.dumps({"remote_path": remote_path, "response": payload}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
