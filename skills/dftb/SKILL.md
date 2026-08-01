---
name: dftb
description: Submit and monitor DFTB+ jobs via the unified HPC API using software=DFTB+. Use after uploading a DFTB+ input bundle to a reachable HTTP URL.
---

# DFTB+ Unified HPC Skill

## Workflow
1. **Prepare the input bundle** (`.zip`, `.tar`, etc.) at a reachable HTTP URL.
2. **Configure this skill** by copying `scripts/config/dftb_config.example.json` to `scripts/config/dftb_config.json` and filling in production values.
3. **Submit a DFTB+ job**:
   ```bash
   cd skills/dftb/scripts
   ./dftb_client.py --config config/dftb_config.json \
     submit http://example.com/input.zip --tasks-per-node 8 --nodes 1
   # -> prints job_id + task_id
   ```
4. **Poll status** using the integer `job_id`:
   ```bash
   ./dftb_client.py --config config/dftb_config.json poll <job_id>
   ```
5. **Get the result ZIP URL** using the UUID `task_id`:
   ```bash
   ./dftb_client.py --config config/dftb_config.json download-url <task_id>
   ```

## Submission model
This skill now targets the unified API from `/workspace/inputs/README.md`:

- `POST /api/jobs`
- `GET /api/jobs?id=<job_id>`
- `GET /api/tasks/download?taskId=<task_id>`

It submits with:
- `software = "DFTB+"`
- default `cmd = "srun --mpi=pmi2 dftb+ > output.out"`

That `cmd` is the current DFTB+ run command and is the one you asked me to surface for examples.

## Config reference (`scripts/config/dftb_config.json`)
| Field | Description |
| --- | --- |
| `api_base_url` | Base URL of your own HPC API. |
| `submit_endpoint` | Override for POST submit endpoint; defaults to `<api_base_url>/api/jobs`. |
| `status_endpoint` | Override for GET status endpoint; defaults to `<api_base_url>/api/jobs`. |
| `download_endpoint` | Override for ZIP download endpoint; defaults to `<api_base_url>/api/tasks/download`. |
| `image` | Container image passed to the HPC API. |
| `created_by` | Value used for `createdBy`. |
| `software` | Should remain `DFTB+`. |
| `default_cmd` | Default remote command; currently `srun --mpi=pmi2 dftb+ > output.out`. |
| `mem` / `tasks_per_node` / `n_nodes` | Default resource request. |
| `poll_interval_seconds` / `max_poll_attempts` | Poll loop controls. |

## Script details
- **Path:** `scripts/dftb_client.py`
- **Class:** `DFTBClient`
- **CLI subcommands:**
  - `submit FILE_URL [--tasks-per-node N] [--nodes M] [--mem SIZE] [--cmd '...']`
  - `poll JOB_ID`
  - `download-url TASK_ID`

## Example payload
```json
{
  "params": {
    "inputfile": "http://example.com/input.zip",
    "software": "DFTB+",
    "cmd": "srun --mpi=pmi2 dftb+ > output.out",
    "n_nodes": 1,
    "tasks_per_node": 8,
    "mem": "4GB"
  },
  "image": "PLEASE_SET_YOUR_OWN_CONTAINER_IMAGE",
  "parentId": "<task-uuid>",
  "taskId": "<task-uuid>",
  "createdBy": "openclaw"
}
```

## Tips
- `job_id` is used for polling; `task_id` is used for download.
- If you override `cmd`, make sure it matches the file layout inside your uploaded DFTB+ input bundle.
- The upload step is still external to this skill; this client only talks to the unified HPC submit/status/download API.
