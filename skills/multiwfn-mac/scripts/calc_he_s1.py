#!/usr/bin/env python3
"""Run Multiwfn hole-electron (S1) analysis for a Gaussian .fchk file."""
from __future__ import annotations

import argparse
import subprocess
from pathlib import Path
from typing import List

DEFAULT_MULTIWFN = Path(__file__).resolve().parent.parent / "multiwfn" / "multiwfn"

def get_level(logfile: Path) -> str | None:
    result = subprocess.run(
        f'grep "Excited State" {logfile} | grep "<S\\*\\*2>=0.000" | head -1',
        shell=True, capture_output=True, text=True
    )
    s1_line = result.stdout.strip()

    if s1_line:
        return s1_line.split()[2].strip(':')
    else:
        print("未找到 S1")
        return None


def build_command_sequence(s1_level: str) -> List[str]:
    return [
        "18",
        "1",
        "",
        s1_level,
        "1",
        "2",
        "0",
        "3",
        "2",
        "7",
        "0",
        "0",
        "0",
        "q",
    ]


def calc_he_s1(fchk_path: Path, multiwfn_bin: Path = DEFAULT_MULTIWFN, output_path: Path | None = None) -> Path:
    if not fchk_path.exists():
        raise FileNotFoundError(f"FCHK file not found: {fchk_path}")

#    if not multiwfn_bin.exists():
#        raise FileNotFoundError(
#            f"Multiwfn executable not found: {multiwfn_bin}. Export a custom path with --multiwfn if needed."
#        )

    # Derive logfile from fchk path: .fchk -> .log
    logfile = fchk_path.with_suffix(".log")
    if not logfile.exists():
        raise FileNotFoundError(f"Log file not found: {logfile}")

    s1_level = get_level(logfile)
    if s1_level is None:
        raise RuntimeError(f"无法从 {logfile} 中找到 S1 激发态信息")

    out_path = output_path or fchk_path.with_suffix(".he.txt")
    out_path.parent.mkdir(parents=True, exist_ok=True)

    # Build interactive script
    command_sequence = build_command_sequence(s1_level)
    payload = "\n".join(command_sequence) + "\n"

    print(f"[Multiwfn] {multiwfn_bin} {fchk_path} -> {out_path}")
    with out_path.open("w", encoding="utf-8") as handle:
        proc = subprocess.run(
            [str(multiwfn_bin), str(fchk_path)],
            input=payload,
            text=True,
            stdout=handle,
            stderr=subprocess.STDOUT,
            check=True,
        )
    return out_path


def main() -> None:
    parser = argparse.ArgumentParser(description="Compute S1 hole-electron descriptors using Multiwfn")
    parser.add_argument("fchk", help="Path to the Gaussian .fchk file")
    parser.add_argument("--multiwfn", help="Path to the Multiwfn executable (defaults to bundled copy)")
    parser.add_argument("--output", help="Optional output path for the generated .he.txt")
    args = parser.parse_args()

    multiwfn_bin = Path(args.multiwfn).expanduser().resolve() if args.multiwfn else DEFAULT_MULTIWFN
    fchk_path = Path(args.fchk).expanduser().resolve()
    out_path = Path(args.output).expanduser().resolve() if args.output else None

    result = calc_he_s1(fchk_path, multiwfn_bin, out_path)
    print(f"Saved hole-electron analysis to {result}")


if __name__ == "__main__":
    main()
