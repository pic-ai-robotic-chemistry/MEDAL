---
name: mace-cof-optimizer
description: Submit, poll, and download MACE-optimized COF CIFs via the remote scorer API. Use when you need to batch CIF files, send them to the MACE pipeline, and fetch optimized CIF structures from `/result_cifs` for downstream workflows.
---

# MACE COF Optimizer Skill

## Quick start
1. **Prepare config**
   - Copy `scripts/config/mace_optimizer_config.example.json` → `scripts/config/mace_optimizer_config.json`.
   - Set `scorer_url` to your own MACE optimization service or gateway. This public repository intentionally uses a placeholder instead of a private deployment URL.
2. **Collect CIFs**
   - Place the starting COF `.cif` files in a folder. Filenames are sorted before submission; non-CIF files are ignored.
   - On submit, the client sends `cifs` as a JSON object: keys are CIF filenames and values are the full CIF text.
3. **Submit the job**
   ```bash
   cd skills/mace-cof-optimizer/scripts
   ./mace_cof_client.py --config config/mace_optimizer_config.json \
     submit /path/to/cif_folder experiment_20260322
   ```
   - This wraps `get_opt_only_input_json`: the JSON payload contains a `cifs` mapping of `{filename: cif_text}` plus the default `optimization_conf` (MACE off, GPU config, etc.).
4. **Poll until finished**
   ```bash
   ./mace_cof_client.py --config config/mace_optimizer_config.json poll <job_id>
   ```
   - Uses the configured interval/timeout; resilient to transient HTTP errors.
5. **Fetch optimized CIFs (primary output)**
   ```bash
   ./mace_cof_client.py --config config/mace_optimizer_config.json cifs --job-id <job_id> --out outputs/mace_results
   ```
   - `cifs` queries `/result_cifs` and is the primary retrieval path for downstream workflows.
   - The current service expects a `GET` request with a JSON body (for example `{"name": "..."}`), so the client sends the CIF lookup request that way rather than as URL query parameters.
   - If `--out` is set it writes the returned CIFs to disk, preserving server filenames when available.
   - Do not rely on `/result` when the downstream task only needs optimized CIF files; `score.json` may be absent even when CIF outputs exist.

## CLI reference
| Command | Purpose |
| --- | --- |
| `submit FOLDER NAME` | Uploads every `.cif` in `FOLDER` (sorted) and starts an optimization job named `NAME`. Prints the server response containing `job_id`. |
| `poll JOB_ID` | Blocks until the job finishes or hits the configured timeout. |
| `cifs [--job-id | --job-name] [--out DIR]` | Fetches optimized structures from `/result_cifs`. This is the default post-processing retrieval path. If `--out` is set, saves each CIF as `structure_###.cif`. |
| `result [--job-id | --job-name]` | Optional diagnostic command for score/metadata JSON from `/result`; not required for CIF-based downstream processing. |

All commands accept `--config /path/to/mace_optimizer_config.json`; if omitted, the default path under `scripts/config/` is used.

## Config reference (`scripts/config/mace_optimizer_config.json`)
| Field | Description |
| --- | --- |
| `scorer_url` | Base URL to the scorer service (required). |
| `submit_url` / `poll_url` / `result_url` / `result_cifs_url` | Optional explicit endpoints if they differ from the defaults (`<base>/submit`, `<base>/status`, etc.). |
| `poll_interval_seconds` | Delay between status checks (default 100s). |
| `poll_timeout_seconds` | Total time before `poll` raises `TimeoutError`. |
| `request_timeout_seconds` | HTTP timeout for GET requests. |

## Implementation notes
- `cifs_from_folder` and `get_opt_only_input_json` now submit `cifs` as `{filename: cif_text}` to match the current server contract.
- `submit_task`, `poll_status`, `get_result`, and `get_result_cifs` are wrapped inside `MACEOptimizerClient`, so they can be imported into other automation scripts or used via CLI.
- For this skill, treat `get_result_cifs` / `cifs` as the canonical retrieval step after a successful poll; `get_result` is diagnostic-only.
- The current `/result_cifs` integration uses `GET` with a JSON request body (`name` / `job_id`) because that matches the deployed service behavior.
- The CLI prints all JSON responses, making it easy to capture provenance logs or feed downstream workflows.
