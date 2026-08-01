---
name: multiwfn-he
description: Run Multiwfn’s hole–electron (S1) analysis on Gaussian .fchk files. Use when you need the `.he.txt` output produced by the standard menu sequence (18 → 1 → … → q) without retyping commands manually.
---

# Multiwfn Hole–Electron Skill

## Bundled dependencies
- A prebuilt Multiwfn binary + support files live under `multiwfn-he/multiwfn/` (copied from the COF monomer skill).
- The helper script defaults to that binary. If you relocate the skill, copy the entire `multiwfn/` folder along with it.
- You can still point to a system-wide Multiwfn via `--multiwfn /path/to/Multiwfn`.

## Quick start
1. `cd skills/multiwfn-he/scripts`
2. Run the helper on any Gaussian `.fchk` file:
   ```bash
   ./calc_he_s1.py /path/to/state.fchk
   # Custom binary / destination
   ./calc_he_s1.py /path/to/state.fchk \
       --multiwfn ~/opt/Multiwfn/Multiwfn --output results/state.he.txt
   ```
3. The script pipes the canonical command sequence `18 → 1 → (Enter) → 1 1 2 0 3 2 7 0 0 0 → q` into Multiwfn and writes `<basename>.he.txt` (or your `--output` path).

## Script reference
### `scripts/calc_he_s1.py`
- `calc_he_s1(fchk_path, multiwfn_bin, output_path=None)`
  - Validates file paths, builds the interactive input payload, and streams Multiwfn’s stdout to the chosen `.he.txt` file.
- CLI flags:
  - `fchk`: required path to the `.fchk` file.
  - `--multiwfn`: overrides the binary (defaults to `../multiwfn/multiwfn`).
  - `--output`: override destination for the `.he.txt` report.
- To tweak the Multiwfn navigation, edit the `COMMAND_SEQUENCE` list at the top of the script (each entry corresponds to one ENTER keypress).

### `scripts/calc_cdft.py`
- Runs Multiwfn conceptual-DFT analysis for neutral / N+1 / N-1 `.fchk` files and writes `<basename>_CDFT.txt`.
- CLI:
  ```bash
  ./calc_cdft.py neutral.fchk plus.fchk minus.fchk --output neutral_CDFT.txt
  ```

### `scripts/log_to_xyz.py`
- Converts Gaussian `.log` to optimized `.xyz` through Multiwfn’s menu sequence.
- CLI:
  ```bash
  ./log_to_xyz.py state.log --output state.xyz
  ```

## Notes & troubleshooting
- Multiwfn writes all prompts/results to stdout; if you prefer to see them live, remove the redirected `stdout` in the script or `tail -f` the generated `.he.txt`.
- If Multiwfn complains about fonts or DISPLAY, set `Multiwfn_noGUI=1` in your shell before running the script.
- The generated `.he.txt` files live next to the `.fchk` by default, matching the behavior of the original `calc_he_s1` helper.
