---
name: cof-tdsp-excited-state
description: End-to-end excited-state workflow for COF dimers: freeze-all-but-H optimization, TD-DFT (Gaussian 16), Multiwfn hole-electron analysis, and fragment-resolved contributions. Use when the `calculate_mols` dimer fragments need PL/TDSP descriptors.
---

# COF TDSP / Excited-State Skill

This skill operationalizes **Step 5** of the dimer pipeline: optimize each dimer’s H atoms, run TD-DFT for low-lying singlets, convert Gaussian outputs, and quantify amine/aldehyde contributions to the hole/electron distribution. All Gaussian and Multiwfn invocations must use the dedicated skills (`gaussian-16`, `multiwfn-he`).

## Inputs
- `calculate_mols/dimer_*.xyz` + `dimer_*.mol` (from the dimer-fragment skill)
- Methods/templates from `scripts/`:
  - `scripts/freezexyz2gjf.py` – builds H-only opt inputs
  - `scripts/xyz2gjf_dimertdsp.py` – builds TDSP inputs
  - `scripts/dohe.py` – reference command sequence for Multiwfn (replaced by `multiwfn-he` skill)
  - `scripts/td_compos.py` – parses `.he.txt` + `.mol` to produce `frag_compos.csv`
- External dependencies configured through skills:
  - `gaussian-16` skill → remote script-runner for Gaussian jobs (opt + TD + optional `formchk`)
  - `multiwfn-he` skill → converts `.fchk` → `.he.txt` or `.log` → `.xyz` via scripted command sequences (use it instead of ad-hoc `Multiwfn` binaries)

## Directory layout
```
step5/
  calculate_mols/           # inputs (xyz + mol per dimer)
  opt/                      # Gaussian H-opt jobs (gjf/log/xyz)
  tdsp_dimer/               # TDSP jobs + fchk/he/csv
  scripts/                  # helper scripts from this skill
```
Create `opt/` and `tdsp_dimer/` per batch (date-stamped subfolders encouraged).

## Workflow overview
1. **Hydrogen-only geometry optimization** (one job per `*.xyz` in `calculate_mols/`).
2. **Convert optimized geometries to TD input** and launch TD-DFT jobs.
3. **Run Multiwfn analyses**:
   - `log → xyz` (post-opt sanity check)
   - `fchk → he.txt` (hole-electron analysis)
4. **Aggregate fragment contributions** with `td_compos.py` to produce `frag_compos.csv`.

The sections below detail each phase and reference the supporting skills.

## Step 1 – Freeze-all-but-H optimization
1. **Generate constrained GJF files**
   ```bash
   cd skills/cof-tdsp-excited-state
   python scripts/freezexyz2gjf.py path/to/calculate_mols/dimer_xxx.xyz --out opt_gjfs/
   ```
   - The script sets `Opt` with ModRedundant-like flags: H atoms flagged `0` (relaxed), heavy atoms `-1` (frozen). Adjust `method="B3LYP/6-31G* em=gd3bj"` if needed.
   - Outputs: `opt_gjfs/dimer_xxx.gjf`, `%chk` lines assume same basename.
2. **Upload each `.gjf`** via the `file-upload` skill (zip if needed) and capture the remote path.
3. **Submit jobs with `gaussian-16` skill**
   ```bash
   cd skills/gaussian-16/scripts
   ./gaussian_client.py --config config/gaussian_config.json \
     submit /files/.../dimer_xxx_opt.gjf --job-type opt
   ```
   - Record the `execution_id`.
   - Poll with `./gaussian_client.py ... poll <execution_id>` until finished; download the artifact ZIP containing `.log` and `.chk`.
4. **Convert optimized log → xyz**
   - Reuse the Multiwfn binary packaged with `multiwfn-he` by supplying the command sequence `100 → 2 → 2 → <xyz> → 0 → q` (see original `log2xyz.sh`).
   - Recommended helper: clone `scripts/log2xyz.sh` logic into a short Python wrapper that calls `skills/multiwfn-he/multiwfn/Multiwfn` so the dependency stays within that skill. Run it inside `opt/` to overwrite the old `.xyz` with optimized coordinates.

## Step 2 – TDSP (excited-state) Gaussian jobs
1. **Prepare TD inputs**
   ```bash
   cd skills/cof-tdsp-excited-state
   python scripts/xyz2gjf_dimertdsp.py path/to/opt/dimer_xxx.xyz
   ```
   - Default route: `#P PBE1PBE/def2SVP nosymm td(nstates=5,root=1) iop(9/40=4)`.
   - Outputs `tdsp_dimer/dimer_xxx.gjf` (adjust script or copy to match your run folder).
2. **Submit TD jobs** via `gaussian-16` skill (same flow as Step 1, but label `--job-type tdsp`). Include `formchk` in the remote wrapper so each job produces `.fchk` alongside `.log` (e.g., HPC script runs `g16 input.gjf` → `formchk input.chk input.fchk` → package artifacts).
3. **Collect artifacts**
   - After polling, download the ZIP and extract into `tdsp_dimer/` (expect `.log`, `.chk`, `.fchk`). Delete `.chk` locally once `formchk` succeeds.

## Step 3 – Multiwfn hole-electron analysis
1. **Run `multiwfn-he` skill on each `.fchk`**
   ```bash
   cd skills/multiwfn-he/scripts
   ./calc_he_s1.py /abs/path/to/tdsp_dimer/dimer_xxx.fchk --output /abs/path/to/tdsp_dimer/dimer_xxx.he.txt
   ```
   - This replicates `python ../dohe.py dimer_xxx.fchk` from the legacy flow.
2. **(Optional) Inspect `.he.txt`** for convergence / sanity checks.

## Step 4 – Fragment contribution CSV
1. Copy the `.mol` files corresponding to the analyzed dimers into `tdsp_dimer/` (names must match `dimer_xxx.mol`).
2. Run the aggregator:
   ```bash
   cd skills/cof-tdsp-excited-state
   python scripts/td_compos.py > tdsp_dimer/frag_compos.csv
   ```
   - The script locates all `*.mol`, matches `*.he.txt`, splits the imine bond, and sums hole/electron percentages per fragment. Output CSV columns: `pfxnam,ald_hole_pct,ami_hole_pct,ald_electron_pct,ami_electron_pct`.

## Automation tips
- **Batching Gaussian jobs**: build a manifest (`dimer_xxx`) and drive submissions/polls via a CSV to avoid manual tracking.
- **Retries**: keep the `file-upload` paths in a log so failed jobs can be re-submitted without re-uploading.
- **Multiwfn sequences**: for log→xyz conversion, duplicate the `multiwfn-he/scripts/calc_he_s1.py` template with `COMMAND_SEQUENCE = ["100", "2", "2", output_path, "0", "q"]` to avoid using ad-hoc shell HEREDOCs.
- **Provenance**: store each job’s JSON response (from `gaussian_client.py poll`) next to the outputs for reproducibility.

## Validation checklist
- Optimization logs end with `Normal termination` and the updated `.xyz` reflects hydrogen relaxation.
- TD jobs converge (`TD` section shows requested states). Verify excitation energies vs. expectations.
- `.fchk` exists and is ~hundreds of KB (not zero-byte).
- `frag_compos.csv` row count equals the number of analyzed dimers; percentages should sum to ~100 % per hole/electron column.

## References
- `resources/readme-step5.txt` – original step description.
- Scripts in `scripts/` mirror the legacy implementation for quick reuse/customization.
- `gaussian-16` + `multiwfn-he` skills provide the remote execution backends required by this workflow.
