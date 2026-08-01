---
name: cof-dimer-tdsp-workflow
description: Orchestrate the full COF dimer excited-state pipeline by chaining `dimer-mol2cif`, `cof-remote-optimizer`, `cof-dimer-fragment`, and `tdsp-excited-state`. Use when you need end-to-end TD descriptors starting from monomer .mol files.
---

# COF Dimer TDSP Workflow

This process skill stitches together the four specialized skills you already have: build COF CIFs, optimize them, slice dimers, then compute excited-state descriptors. No new scripts are required—the value here is the handoff discipline and run-of-show.

## Prerequisites
- Libraries of aldehyde (`ald-*.mol`) and amine (`ami-*.mol`) monomers.
- Access/configuration for all downstream skills:
  1. `dimer-mol2cif`
  2. `cof-remote-optimizer`
  3. `cof-dimer-fragment`
  4. `tdsp-excited-state`
- Remote services configured for DFTB, Gaussian 16, and Multiwfn via the respective skills those steps depend on.

## Data handoff map
| Stage | Skill | Key Inputs | Key Outputs | Next Stage consumes |
| --- | --- | --- | --- | --- |
| 1 | `dimer-mol2cif` | `ald-*.mol`, `ami-*.mol` | `initial_cifs/*.cif` | Stage 2 |
| 2 | `cof-remote-optimizer` | `initial_cifs/*.cif` | `optimized_cifs/*_dftb_opted.cif`, `mace_results/*.cif` | Stage 3 |
| 3 | `cof-dimer-fragment` | Optimized CIFs + monomer manifest (`training-transfer-0129.txt`) | `calculate_mols/dimer_*.mol`, `dimer_*.xyz` | Stage 4 |
| 4 | `tdsp-excited-state` | `calculate_mols` folder | `opt/`, `tdsp_dimer/`, `frag_compos.csv` | Final results |

## Step-by-step execution

### 1. Build periodic COF candidates (`dimer-mol2cif`)
1. Follow that skill’s instructions to enumerate aldehyde/amine pairings.
2. Produce the initial CIF library (one per pairing). Keep the manifest (which pair → filename) for downstream joins.

### 2. Remote structural optimization (`cof-remote-optimizer`)
1. Feed the CIF folder into the remote optimizer skill.
2. Run DFTB bundling → upload → job submission → extraction as documented there.
3. Pass the resulting `*_dftb_opted.cif` files through the MACE refinement stage to obtain your final `mace_results/*.cif`.
4. Archive intermediate artifacts; Stage 3 only needs the final refined CIFs plus the aldehyde/amine metadata.

### 3. Extract dimer fragments (`cof-dimer-fragment`)
1. Supply the optimized CIFs, monomer `.mol` libraries, and the dataset manifest (`training-transfer-0129.txt`).
2. Walk through the three mini-steps:
   - Generate the vacuum reference dimers (if not already cached).
   - Cut real dimers out of each CIF.
   - Filter/match against the manifest to populate `calculate_mols/dimer_*.mol` & `.xyz`.
3. Validate coverage: every target (ald, ami) combo destined for spectral analysis should now have a corresponding entry in `calculate_mols/`.

### 4. TD excited-state computations (`tdsp-excited-state`)
1. Use the tdsp skill you just renamed to run hydrogen-only optimizations, TDSP Gaussian jobs, Multiwfn analyses, and fragment composition aggregation.
2. Ensure the remote Gaussian + Multiwfn skills are called for every task; capture `frag_compos.csv` plus per-dimer `.he.txt` files as deliverables.

## Operational tips
- **Folder discipline**: keep a mirrored directory tree per batch (e.g., `runs/20260323/{initial_cifs,optimized_cifs,calculate_mols,tdsp}`) so handoffs are scriptable.
- **Metadata tracking**: maintain a single CSV manifest with columns `ald_id, ami_id, cif_path, dimer_xyz, opt_log, td_log, he_txt, csv_row_index` to simplify audits.
- **Parallelization**: stages 2–4 can process multiple dimers in parallel as long as the remote queues can handle the load. Gate progress between stages by checking for missing files before promotion.
- **QC gates**: after each stage, spot-check a random subset (visualize CIF/dimer geometry, inspect TD spectra) before unlocking the next stage.

## Completion criteria
- `frag_compos.csv` exists with a row for each requested (ald, ami) pair.
- All intermediate artifacts archived (zips from DFTB/Gaussian, Multiwfn logs) for traceability.
- Any failures (e.g., optimization not converged, TD job aborted) are logged with retry instructions before declaring the workflow done.
