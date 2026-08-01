---
name: gplearn-symbolic-regression
description: Run the lab-grade gplearn SymbolicClassifier sweep (from inputs/gplearn) on any binary CSV to reproduce the detailed TXT/CSV formula reports (accuracy + complexity rankings, grouped summaries). Use when asked to "像脚本一样" analyze a CSV with gplearn and emit the five report files.
---

# gplearn Symbolic Regression Skill

## Overview
This skill ships a reusable workflow and script for executing the gplearn symbolic regression pipeline that Dr. Zikai curated in `inputs/gplearn/`. Provide a binary-labeled CSV and the tooling will train a `SymbolicClassifier`, extract every evolved program, deduplicate formulas, and export the same TXT + CSV artifacts as the original lab notebook.

Outputs per run (all placed in the chosen output directory):
1. `all_formulas_detailed.txt`
2. `all_formulas_by_accuracy.csv`
3. `all_formulas_by_complexity.csv`
4. `formulas_by_accuracy_groups.txt`
5. `formulas_summary_table.txt`

## Quick Start Workflow
1. **Stage the data**
   - Ensure the CSV is accessible locally (e.g., copy to `inputs/gplearn/` or `outputs/experiment_X/`).
   - Confirm the target column contains binary values (0/1). Rename it if needed (default name `class`).
2. **Run the automation script**
   - Script path: `skills/gplearn-symbolic-regression/scripts/run_symbolic_regression.py`
   - Basic invocation (mirrors the reference script):
     ```bash
     python3 skills/gplearn-symbolic-regression/scripts/run_symbolic_regression.py \
       /abs/path/to/data.csv --target-column class --output-dir /abs/path/to/results
     ```
   - The CLI prints each phase (load data → train → collect programs → write reports) so you can monitor progress.
3. **Review outputs**
   - `all_formulas_by_accuracy.csv` for quick filtering (e.g., accuracy ≥ 0.99).
   - `formulas_by_accuracy_groups.txt` to grab the simplest expression per accuracy band.
   - `all_formulas_detailed.txt` when you need the full narrative log.
4. **Document & archive**
   - Capture the full CLI command (flags = provenance).
   - If multiple runs are required, keep outputs in separate folders (`outputs/gplearn/run_YYYYMMDDHHMM`).

## Script Parameters & Tips
- `--target-column`: defaults to `class`. Override when the label column has another name.
- `--output-dir`: defaults to the CSV directory. Set it explicitly to keep experiments organized.
- `--config-json`: supply a JSON file containing any SymbolicClassifier kwargs to override the defaults (population size, metric, etc.).
- Quick overrides without JSON:
  - `--population-size 800`
  - `--generations 30`
  - `--function-set add,sub,mul,div,sqrt`
  - `--random-state 1337`
- The defaults replicate the heavy sweep (population 3000, generations 100) that produced 194 perfect formulas. For scouting runs, dial the overrides down, validate results, then rerun with the full config.

## Reference Material
- **Runbook:** `references/workflow.md` — checklist for dataset prep, hyperparameter strategy, and post-processing ideas. Read it when planning multi-run studies or when adapting the pipeline to new chemical endpoints.

## Maintenance Notes
- The script requires `gplearn`, `numpy`, `pandas`, and `scikit-learn`. Ensure they’re installed in the execution environment.
- When gplearn upgrades change operator names or internal program attributes, update the script in `scripts/run_symbolic_regression.py` accordingly and retest on `inputs/gplearn/data_train_for_SR.csv` to confirm parity with historical outputs.
