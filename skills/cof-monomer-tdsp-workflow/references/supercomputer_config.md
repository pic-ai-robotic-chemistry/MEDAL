# Unified HPC Submission Config

Store credentials in `config/supercomputer_config.json` (relative to the working copy of the scripts). Copy
`scripts/config/supercomputer_config.example.json` to that location and fill in your own private server values before running the workflow. Do not commit real endpoints or tokens to a public repository.

```json
{
  "upload_endpoint": "https://your-own-upload-api.example.com/api/file/upload",
  "file_upload_token": "PLEASE_SET_YOUR_OWN_UPLOAD_TOKEN",
  "file_upload_header": "YOUR_UPLOAD_AUTH_HEADER",
  "api_base_url": "https://your-own-hpc-api.example.com",
  "submit_endpoint": "https://your-own-hpc-api.example.com/api/jobs",
  "status_endpoint": "https://your-own-hpc-api.example.com/api/jobs",
  "download_endpoint": "https://your-own-hpc-api.example.com/api/tasks/download",
  "auth_token": null,
  "image": "PLEASE_SET_YOUR_OWN_CONTAINER_IMAGE",
  "created_by": "openclaw",
  "software": "GAUSSIAN",
  "default_cmd": "g16 {input_gjf} && formchk {input_chk}",
  "poll_interval_seconds": 15,
  "max_poll_attempts": 720,
  "tasks_per_node": 32,
  "n_nodes": 1,
  "mem": "64GB",
  "objective": "计算",
  "objective_map": {
    "opt": "结构优化",
    "plus": "加电子态",
    "minus": "去电子态",
    "tdsp": "TDDFT"
  }
}
```

## Flow

1. Upload the local `.gjf` to the file worker.
2. Wrap it into a one-file ZIP before upload so the unified API can unzip it remotely.
3. Submit to the unified HPC API:
   - `POST /api/jobs`
4. Poll the integer `job_id`:
   - `GET /api/jobs?id=<job_id>`
5. Download the final ZIP with the UUID `taskId`:
   - `GET /api/tasks/download?taskId=<taskId>`

## Field definitions

- **upload_endpoint**: Upload API used before HPC submission.
- **file_upload_token / file_upload_header**: Header-based auth for uploads.
- **api_base_url**: Base URL of the unified HPC API.
- **submit_endpoint / status_endpoint / download_endpoint**: Optional explicit endpoint overrides.
- **image**: Container image passed to the HPC service.
- **software**: For this workflow, should remain `GAUSSIAN`.
- **default_cmd**: Remote command. Here `input_gjf` is the `.gjf` filename inside the uploaded ZIP, and `input_chk` is the same basename with `.chk`.
- **tasks_per_node / n_nodes / mem**: Resource request for the HPC job.
- **objective / objective_map**: Labels for local bookkeeping and server-side display.
- **poll_interval_seconds / max_poll_attempts**: Poll loop controls.

## Note on filenames

The remote side unzips the uploaded archive automatically. Therefore `cmd` must reference the `.gjf` filename inside the ZIP, not the ZIP filename itself. This is why the default command is:

```bash
g16 {input_gjf} && formchk {input_chk}
```

## Multiwfn post-processing

This workflow does **not** submit Multiwfn to a remote service. Gaussian runs remotely, then Multiwfn post-processing is performed locally through the sibling `skills/multiwfn-mac/` helpers.
