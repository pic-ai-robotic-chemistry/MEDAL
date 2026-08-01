---
name: cof-monomer-descriptors
description: Remote-ready workflow for generating COF monomer chemical descriptors from SMILES strings. Use when Gaussian g16 must run on a supercomputer via HTTP API, Multiwfn is available locally, and you need to extract descriptors (CDFT, TDSP, hole-electron metrics) with the djh toolkit.
---

# COF Monomer Descriptor Skill

## Overview
Use this skill to convert a SMILES string into COF monomer descriptors even when Gaussian 16 is only available on a remote supercomputer. The bundled workflow handles structure preparation, remote Gaussian submission, local Multiwfn geometry extraction, descriptor generation with the `djh` toolkit, and TDSP hole-electron analysis. All Multiwfn processing in this skill is done locally through the sibling `multiwfn-mac` skill; there is no supported remote Multiwfn path.

Scripts live under `scripts/monomer_descriptor_calculation/`:
- `monomer_calc.py` – main workflow entry point.
- `hpc_client.py` – minimal HTTP client for the supercomputer job API.
- `dohe.py` – legacy Multiwfn wrapper kept for reference; production calls should go through the `multiwfn-mac` skill helpers.
- `djh/` – descriptor utilities (FormchkInterface, CDFT readers, etc.).
- `config/supercomputer_config.example.json` – template for API credentials.

Reference docs:
- `references/supercomputer_config.md` – describes all config fields and overrides.

## Quick Start Workflow

1. **Prep environment**
   - Install RDKit and the Python deps (requests + djh requirements).
   - Ensure the shell environment exposes a Python interpreter compatible with both `python` and `python3`. On machines where only `python3` exists, either add a `python` shim/symlink or update script shebangs/launch commands to use `python3` consistently. The bundled `dohe.py` must run under the same interpreter family that launches `monomer_calc.py`.
   - The workflow now expects the sibling `skills/multiwfn-mac/` skill to be present; its helper scripts provide the supported entry points for all Multiwfn calls used by this workflow.
2. **Configure script runner API**
   - Copy `scripts/monomer_descriptor_calculation/config/supercomputer_config.example.json` to `config/supercomputer_config.json` in your working copy.
   - Fill in your own upload endpoint, upload auth header/token, and optional bearer token as described in `references/supercomputer_config.md`. This repository does not ship working private server credentials.
3. **Hole–electron backend**
   - The workflow now calls the dedicated `skills/multiwfn-mac/scripts/calc_he_s1.py` helper for HE analysis.
   - Keep the `multiwfn-mac` skill directory intact (especially `scripts/calc_he_s1.py` and `multiwfn/multiwfn`) so TDSP jobs can resolve the helper and bundled binary.
   - The legacy `dohe.py` remains as reference only; the main workflow should not rely on it for Multiwfn invocation.

### Bundled Multiwfn build (local dependency)
- The canonical and only supported Multiwfn entry points live in the sibling `skills/multiwfn-mac/` skill.
- `cof-monomer-tdsp-workflow` should call `calc_he_s1.py`, `calc_cdft.py`, and `log_to_xyz.py` from that skill instead of invoking `Multiwfn` directly.
- Keep `skills/multiwfn-mac/multiwfn/multiwfn` executable and present alongside its helper scripts.
- There is no remote Multiwfn client in the supported workflow; Multiwfn post-processing is intentionally local.

4. **Run the workflow**
   ```bash
   python monomer_calc.py \
     --smiles "O=C(O)c1ccc(cc1)C=CC(=O)O" \
     --name monomer_001 \
     --workdir ./calc_monomer_001 \
     --config config/supercomputer_config.json
   ```
   - `--resources` is kept for backward compatibility but ignored by the script-runner submission path.
   - Set `--dohe-env` if you exported a different env var name.
5. **Collect outputs**
   - Optimized geometries + logs land under `workdir`.
   - Spin-state calculations sit in `workdir/plus`, `workdir/minus`, `workdir/tdsp`.
   - Descriptor summary writes to `<name>.des` in `workdir`.

## Default compute sizing

- Gaussian input generation defaults to `--nproc 32` and `%nproc=32` unless explicitly overridden.
- Remote script-runner submissions default to `tasks_per_node=32` and `n_nodes=1` unless the config sets other values.
- Keep the Gaussian `%nproc` value aligned with `tasks_per_node` to avoid local/remote resource mismatches.

## Remote Gaussian Submission Details

- `run_remote_gaussian` now uploads each generated `.gjf` to the worker endpoint, wraps it into a one-file ZIP, and submits that ZIP to the unified HPC API.
- The submission path is now:
  - `POST /api/jobs`
  - `GET /api/jobs?id=<job_id>`
  - `GET /api/tasks/download?taskId=<task_id>`
- The client injects `software=GAUSSIAN` and renders `cmd` as `g16 {input_gjf} && formchk {input_chk}`, where `input_gjf` is the `.gjf` filename inside the uploaded ZIP and `input_chk` is the matching `.chk` name.
- Result archives are extracted under `<state>_remote_<timestamp>/`. The workflow searches that folder for the matching `.log` and `.fchk`, copies them next to the `.gjf`, and TDDFT runs immediately trigger hole–electron analysis on the copied `.fchk` via the `multiwfn-mac` skill helper.
- Tune `max_poll_attempts` / `poll_interval_seconds` in the config to match queue wait times.
- **Resume-by-ID rule (important):** if a task times out only because local polling expired, recover the original `job_id` and `task_id` from the local logs before considering resubmission. Resubmission should be reserved for cases where the remote task is confirmed missing/failed or the user explicitly asks to rerun.

## Descriptor Extraction

- `extract_descriptors` expects `plus/`, `minus/`, and `tdsp/` folders to each hold `<name>.fchk` and `<name>.log`.
- The script copies ±1 state `fchk` files into the workspace root (`<name>±1.fchk`) before running `djh` routines so that `read_CDFT` locates them without extra configuration.
- TDSP hole-electron metrics rely on `dohe.py` producing `<name>.he.txt` via Multiwfn command automation.

## Troubleshooting & Tips

- **Config not found** → `SupercomputerClient` raises `FileNotFoundError`. Verify `--config` or duplicate the example template.
- **Polling timed out locally** → treat this as a recovery problem first, not a rerun problem. Extract the original `Execution ID:` from the task log, call the same result endpoint again, and resume waiting on that existing remote job. Only after the old execution is proven irrecoverable should you submit a fresh job.
- **Missing `.fchk`** → ensure the remote job script runs `formchk` before packaging results, or modify the remote workflow accordingly.
- **Multiwfn path issues** → update `PATH` or adjust the `cmd` strings in `monomer_calc.py` / `dohe.py` to point to the binary.
- **Multiwfn automation incompatibility** → this skill currently drives Multiwfn through shell-piped menu input (`echo ... | Multiwfn`). On some local builds this can fail even when the binary exists, producing Fortran stdin/list-input errors and preventing `*.he.txt` or `*_CDFT.txt` from being generated. In that case, the automation wrapper (not the remote Gaussian job) must be adapted for the local Multiwfn build before descriptor extraction can finish.
- **Multiwfn helper lookup** → this workflow expects the sibling skill `skills/multiwfn-mac/` to exist and contain `scripts/calc_he_s1.py`, `scripts/calc_cdft.py`, `scripts/log_to_xyz.py`, plus the bundled `multiwfn/multiwfn` binary.
- **Legacy direct Multiwfn calls** → `dohe.py` and old `djh/cdft.py`/`log_to_xyz` shell pipelines should be treated as migrated; production flow should route through the local `multiwfn-mac` skill helpers only.
- **`env: python: No such file or directory`** → Multiwfn helper scripts are now invoked through the current interpreter (`sys.executable`) instead of executing legacy wrappers directly.
- **Resource overrides** → pass a JSON string to `--resources`. This is forwarded directly to the API payload, so keep the structure compatible with the supercomputer service.

## Resources

- `scripts/monomer_descriptor_calculation/` – executable pipeline + helper modules.
- `references/supercomputer_config.md` – config documentation + example payload.