---
name: cof-dimer-fragment
description: Extract the minimal COF dimer fragment from a periodic CIF. Use when a relaxed COF structure needs to be converted into vacuum dimer .mol/.xyz files for downstream quantum calculations.
---

# COF Dimer Fragment Skill

Convert periodic COF CIFs into isolated dimer fragments that match the experimental aldehyde/amine pairings. The workflow mirrors `dimer_step4-5/4-cut_dimer_from_cif` and produces `calculate_mols/dimer_*.mol` plus `dimer_*.xyz` for quantum chemistry runs.

## Inputs & prerequisites
- **Monomer libraries** (same as step 1 of mol2cif):
  - `ald-result/ald-*.mol`
  - `ami-result/ami-*.mol`
- **Optimized COF CIFs**: place under `opted_cifs/*.cif` (output of the remote optimizer skill).
- **Pairing manifest**: `training-transfer-0129.txt` (copied under `resources/`; original name `训练+迁移-0129.txt`). Columns: `ald,ami,plqy,class`. Only the first two columns are required here.
- **Environment**:
  - Python with RDKit, NumPy, ASE/PyMatGen (as used in the notebooks).
  - Jupyter or the ability to run `.ipynb` via `jupyter nbconvert --execute`.

## Directory scaffold
```
cof-dimer-work/
  ald-result/
  ami-result/
  opted_cifs/
  cuted_mols/          # raw fragments cut out of CIFs
  individual_dimers/   # vacuum reference dimers (.mol + .png)
  calculate_mols/      # final deliverables (.mol + .xyz)
```
Initialize empty output folders before running the steps.

## Step 1 – Build vacuum reference dimers (individual library)
Purpose: create idealized aldehyde/amine dimers in vacuum so later steps can align CIF fragments with their parent molecules.

1. Copy `step4-1-generate_individual_dimers.ipynb` (see original project) or reference its logic.
2. Run it with RDKit available. Options:
   - Open in JupyterLab/VS Code, set `ald_path` and `ami_path` loops, execute all cells.
   - Or run headless:
     ```bash
     jupyter nbconvert --to notebook --execute step4-1-generate_individual_dimers.ipynb \
       --output step4-1-generated.ipynb
     ```
3. The notebook iterates over every `ald-*.mol` × `ami-*.mol` combination and:
   - Detects aldehyde carbonyls / amine nitrogens via SMARTS-like scans.
   - Tries two relative orientations (flip vs. no flip at −120°) and keeps the one with maximal edge parallelism.
   - Merges duplicated atoms, removes leftover –CHO / –NH₂ groups, and forms the imine bond.
   - Writes `individual_dimers/dimer_ald-<i>_ami-<j>.mol` plus a PNG preview.
4. Verify a few outputs by checking the log (number of atoms, formula) and the PNG preview.

## Step 2 – Cut actual dimers from periodic CIFs
Purpose: slice two connected monomers from the relaxed COF cell to capture realistic bond lengths/angles before vacuum relaxation.

1. Place the MACE-relaxed CIFs in `opted_cifs/`.
2. Use the logic from `step4-2-cut_dimer_from_cif.ipynb`:
   - Load CIF via ASE/PyMatGen, select a representative imine linkage by locating matching aldehyde/amine fragments (lattice-aware neighbor searches).
   - Duplicate the unit cell if needed to capture both monomers within a single fragment.
   - Remove periodic duplicates and saturate dangling bonds with hydrogens according to bonding rules.
   - Save intermediate raw mol files into `cuted_mols/` for inspection.
3. Tips:
   - Work one CIF at a time to keep notebook memory manageable.
   - Keep a CSV mapping `cif_name → cuted_mol` for downstream bookkeeping.

## Step 3 – Match experimental pairs & export calculate_mols
Purpose: ensure we only keep dimers that exist in the experimental dataset.

1. Load `training-transfer-0129.txt` (CSV). Parse `ald` and `ami` columns (integers).
2. Run `step4-3-choose_dimers_in_data.ipynb`:
   - Cross-reference `(ald, ami)` tuples against both `individual_dimers/` and `cuted_mols/`.
   - For each match, generate two artifacts inside `calculate_mols/`:
     - `dimer_ald-<i>_ami-<j>.mol` – cleaned mol block ready for QC calculations.
     - `dimer_ald-<i>_ami-<j>.xyz` – 3D coordinates derived from the CIF slice.
   - Copy/rename any ancillary metadata files if needed by the next pipeline stage.
3. Confirm counts:
   - Number of MOL/XYZ pairs should equal the number of `(ald, ami)` combos present in the dataset and available in `opted_cifs/`.
   - Spot-check geometry against the PNG or visualizer to ensure bonds were not broken at the cut plane.

## Automation notes
- The current implementation lives in three notebooks. For batch runs, convert them into CLI scripts (e.g., using `nbconvert --execute` or rewriting critical cells into Python modules). Keep them under version control in `scripts/` once stabilized.
- All heavy geometric logic (edge parallelism, fragment stitching, atom filtering) is documented in `resources/readme-step4.txt`. Load it for implementation details.
- When scaling to hundreds of COFs, parallelize over CIF files but serialize writes into `cuted_mols/` / `calculate_mols/` to avoid filename collisions.

## Validation checklist
- **Connectivity**: every exported MOL must contain exactly two monomer units linked by a single imine (look for two C=N bonds).
- **Charge/valence**: RDKit `Chem.SanitizeMol` should pass without valence warnings.
- **Coordinate sanity**: RMSD between `calculate_mols/dimer_*.mol` and its `.xyz` counterpart should be <0.1 Å after alignment (ensures the XYZ was derived correctly).
- **Coverage**: ensure all `(ald, ami)` pairs from the manifest either have outputs or are logged as missing (e.g., due to absent CIF).

## References
- `resources/readme-step4.txt` – original step-4 instructions.
- `resources/training-transfer-0129.txt` – pairing manifest example.
- Original notebooks (outside this skill): `step4-1-generate_individual_dimers.ipynb`, `step4-2-cut_dimer_from_cif.ipynb`, `step4-3-choose_dimers_in_data.ipynb`.
