# gplearn Symbolic Regression Runbook

Use this checklist before executing the skill script:

1. **Dataset hygiene**
   - Input must be a CSV file with a binary target column (values 0/1). Convert labels manually if needed.
   - Remove identifier columns that leak the label (sample_id, smiles_id, etc.) unless they are true features.
   - Keep column names ASCII-only when possible to avoid parser surprises inside gplearn.

2. **Training/validation split**
   - The script evaluates accuracy on the training set (mirroring the exploratory workflow). For hold-out validation, manually split the CSV and run twice.
   - When providing a pre-split dataset, keep both files in the same directory and invoke the script separately so outputs stay organized.

3. **Hyperparameters**
   - Default config reproduces the "194 个 100% 公式" discovery sweep (population 3000, generations 100).
   - To iterate faster, drop `--population-size` to ~800 and `--generations` to 30 during prototyping, then re-run with the full config.
   - Complex operator sets can be injected via `--function-set add,sub,mul,div,sqrt,log`. Ensure operators exist in gplearn.

4. **Output directory discipline**
   - Point `--output-dir` to a clean folder per experiment (e.g., `outputs/gplearn/run_20250317_full/`).
   - The script writes five files; snapshot the folder or commit to git for provenance.

5. **Reproducibility**
   - Random seed defaults to 42. Override via `--random-state` when you want independent runs for diversity.
   - Keep a log of CLI flags in your lab notebook so the reports can be contextualized.

6. **Post-processing**
   - Use `all_formulas_by_accuracy.csv` to filter >99% accuracy entries for manual inspection.
   - `formulas_by_accuracy_groups.txt` is the quickest way to find simplest formulas in each performance band.
   - For deployment, translate selected expressions into PySR-compatible syntax or implement directly in your scoring service.
