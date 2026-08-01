---
name: dimer-mol2cif
description: Build periodic COF CIF files by pairing aldehyde (ald-*.mol) and amine (ami-*.mol) monomers (4+4) with the mol2cif workflow. Use when you need to enumerate ald/ami combinations and export the resulting unit cells under `cif_results/*.cif`.
---

# Dimer mol→CIF Skill

## What’s included
- `resources/dimer2cif/` – direct copy of `/Users/zikaixie/PycharmProjects/ScienceClaw/dimer/dimer_step1-3/1-dimer2cif`
  - `ald-result/` and `ami-result/`: sample `.mol` monomer libraries (filenames `ald-#.mol`, `ami-#.mol`).
  - `mol2cif.ipynb`: authoritative notebook (`dimer-2-enhanced.ipynb` version) with the full RDKit/ASE pipeline.
  - `cif_results/`: target folder for generated `dimer_ald-*_ami-*.cif` files.

## Environment
```bash
conda activate rdkit  # 或者确保 pip 安装的 rdkit/ase 可用
pip install rdkit-pypi ase numpy ipykernel
```
The notebook assumes RDKit + ASE are importable in the active Python environment.

## Workflow
1. **Prepare monomer files**
   - Place aldehydes under `resources/dimer2cif/ald-result/` (naming `ald-XX.mol`).
   - Place amines under `resources/dimer2cif/ami-result/` (naming `ami-XX.mol`).
   - Only 4+4 topologies are supported by this workflow.
2. **Launch the notebook**
   ```bash
   cd skills/dimer-mol2cif/resources/dimer2cif
   jupyter notebook mol2cif.ipynb  # 或使用 VSCode/Jupyter Lab
   ```
   - The notebook exposes helper functions (group detection, flipping logic, assembly, CIF writer) and a driver loop near the bottom where you select lists of `ald_ids` / `ami_ids`.
   - Update the ID lists, run all cells, and monitor `cif_results/` for new CIF outputs.
3. **Headless/CLI option**
   - Convert the notebook to a script (`jupyter nbconvert --to script mol2cif.ipynb`) or reuse the generated copy at `scripts/mol2cif.py`.
   - Edit the lists of `ald_ids`/`ami_ids` near the bottom of the script and run `python scripts/mol2cif.py` to batch-generate CIFs without the notebook UI.
4. **Collect outputs**
   - Each ald+ami pair writes intermediates (`*_final.mol`, PNG previews) and the final CIF to `cif_results/dimer_ald-XX_ami-YY.cif`.
   - Downstream workflows (e.g., submission to MACE/DFFTB) should point to these CIFs.

## Tips
- The pipeline assumes input `.mol` files already have curated coordinates (the script no longer recomputes 2D coords). If you regenerate `.mol` from SMILES, run a quick RDKit geometry clean-up before dropping them in the folders.
- The final CIF lattice uses heuristics (`a/b` from monomer span, `c=12 Å`). Adjust the cell construction block near the end of the notebook/script if your system needs different layer spacing or gamma angle.
- `cif_results/` may accumulate auxiliary files—only `*.cif` are needed; other files can be deleted once you verify the build.
- Keep a backup of the original notebook; if you customize it heavily, copy it to a new filename so upgrades from upstream don’t overwrite your edits.
