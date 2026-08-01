---
name: file-upload
description: Upload Gaussian/DFTB input archives to the remote worker service via HTTP with configurable endpoints/tokens. Use this when a workflow needs to push `.gjf`, `.zip`, or other payloads to the supercomputer gateway and return the server-side path for downstream jobs.
---

# File Upload Skill

## Quick start
1. **Check the upload endpoint**
   - Default config now uses a placeholder upload API: `https://your-own-upload-api.example.com/api/file/upload`. Replace it with your own endpoint before use.
   - The current API example uses a plain multipart upload (`-F "file=@..."`) and may not require the old auth header.
2. **Run the helper script**
   ```bash
   cd skills/file-upload/scripts
   ./upload_file.py /path/to/input.gjf
   # or specify a different config
   ./upload_file.py /path/to/input.zip --config /secure/configs/file_upload_config.json
   ```
   - Stdout prints the resolved remote path plus the raw JSON response for logging/debugging.
3. **Propagate the remote path**
   - Feed the returned path into downstream skills such as `gaussian-16` or `dftb` when building their `script_params`.

## Config reference (`scripts/config/file_upload_config.json`)
| Field | Description |
| --- | --- |
| `upload_endpoint` | Full URL of the upload API. |
| `file_upload_token` | Optional token inserted into the header specified below. Leave unset when the API does not require auth. |
| `file_upload_header` | Optional auth header name (for example `YOUR_UPLOAD_AUTH_HEADER`). Ignored if no token is configured. |
| `file_field_name` | Multipart field name (default `file`). |
| `timeout_seconds` | Optional request timeout. |
| `extra_headers` | Optional dict of additional headers (e.g. `User-Agent`). |

## Script details
- **Path:** `scripts/upload_file.py`
- **Function:** `upload_file(Path, config_path=None, file_field=None)` returns `(remote_path, response_json)`.
- The helper accepts both the old response shape (`{"code":200,"data":"..."}`) and newer variants that return the remote path under `data`, `path`, or `result.path` / `result.data`.
- **CLI flags:**
  - `--config` → alternate config path.
  - `--field` → override multipart field name for one-off uploads.

## Troubleshooting
- `FileNotFoundError`: confirm the local path is correct before calling the script.
- `requests.exceptions.*`: check connectivity to your own upload service endpoint.
- `Upload succeeded but remote path was not found`: inspect the printed raw payload and extend the parser if the backend changed its response schema again.
