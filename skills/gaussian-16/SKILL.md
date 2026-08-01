---
name: gaussian-16
description: Submit and monitor Gaussian 16 jobs via the unified HPC API using software=GAUSSIAN and a custom cmd override that runs g16 plus formchk. Supports config fallback from `gaussian_config.json` to `gaussian_config.example.json`.
---

# Gaussian 16 Unified HPC Skill

## Workflow
1. **Prepare the input** as a `.gjf` or ZIP bundle reachable by HTTP (`params.inputfile`).
2. **Configure this skill**:
   - Preferred: create `scripts/config/gaussian_config.json`
   - Fallback supported: if that file is absent, the client will automatically read `scripts/config/gaussian_config.example.json`
3. **Submit a Gaussian job** via the helper script:
   ```bash
   cd skills/gaussian-16/scripts
   ./gaussian_client.py submit http://example.com/path/input.gjf --job-type opt
   # or explicitly
   ./gaussian_client.py --config config/gaussian_config.example.json submit http://example.com/path/input.gjf --job-type opt
   # -> prints job_id + task_id
   ```
4. **Poll job status** with the returned integer `job_id`:
   ```bash
   ./gaussian_client.py poll <job_id>
   ```
5. **Download the result ZIP** with the returned `task_id`:
   ```bash
   ./gaussian_client.py download-url <task_id>
   ```

## Config resolution behavior
The client now resolves config in this order:
1. `--config <path>` if provided
2. `scripts/config/gaussian_config.json`
3. `scripts/config/gaussian_config.example.json`

That means an example config can serve as a valid runtime template when it already contains usable endpoints/defaults.

## Submission model
This skill targets the unified API described in `/workspace/inputs/README.md`:

- `POST /api/jobs`
- `GET /api/jobs?id=<job_id>`
- `GET /api/tasks/download?taskId=<task_id>`

It submits with:
- `software = "GAUSSIAN"`
- `cmd = "g16 {input_gjf} && formchk {input_chk}"`

For the unified API, `input_gjf` refers to the `.gjf` filename *inside the uploaded ZIP* (the remote side unzips automatically). The helper therefore supports:
- `--input-gjf-name benzene.gjf` to render the command correctly for ZIP uploads
- `input_chk = benzene.chk` from the same stem

That preserves matching filenames so the remote `formchk` step can convert the generated `.chk` into `.fchk`.

## Config reference
Fields accepted by the runtime config (json or example json):
| Field | Description |
| --- | --- |
| `api_base_url` | Base URL of the unified HPC API. |
| `submit_endpoint` | Override for POST submit endpoint; defaults to `<api_base_url>/api/jobs`. |
| `status_endpoint` | Override for GET status endpoint; defaults to `<api_base_url>/api/jobs`. |
| `download_endpoint` | Override for ZIP download endpoint; defaults to `<api_base_url>/api/tasks/download`. |
| `image` | Container image passed to the HPC API. |
| `created_by` | Value used for `createdBy`. |
| `software` | Should stay `GAUSSIAN` unless the API changes again. |
| `default_cmd` | Default remote command; should remain `g16 {input_gjf} && formchk {input_chk}`. |
| `mem` / `tasks_per_node` / `n_nodes` | Default resource request. |
| `poll_interval_seconds` / `max_poll_attempts` | Poll loop controls. |
| `objective_map` | Optional mapping from local job type labels to remote objective labels. |

## Script details
- **Path:** `scripts/gaussian_client.py`
- **Class:** `GaussianClient`
- **CLI subcommands:**
  - `submit FILE_URL [--job-type opt|plus|minus|tdsp] [--tasks-per-node N] [--nodes M] [--mem SIZE] [--cmd '...'] [--input-gjf-name NAME.gjf]`
  - `poll JOB_ID`
  - `download-url TASK_ID`

## Tips
- The submitted URL must be directly reachable by the HPC API; if needed, keep using your upload service separately.
- `job_id` is an integer used for polling; `task_id` is the UUID used for downloading results.
- If you override `cmd`, keep the `.gjf` / `.chk` stem consistent or Gaussian-to-formchk chaining will break.
