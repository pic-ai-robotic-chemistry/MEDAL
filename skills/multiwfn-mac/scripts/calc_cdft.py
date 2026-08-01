#!/usr/bin/env python3
"""Run Multiwfn conceptual-DFT analysis for N / N+1 / N-1 Gaussian .fchk files."""
from __future__ import annotations

import argparse
import shutil
import subprocess
from pathlib import Path
from typing import List

DEFAULT_MULTIWFN = Path(__file__).resolve().parent.parent / 'multiwfn' / 'multiwfn'
COMMAND_SEQUENCE_PREFIX: List[str] = [
    '22',
    '2',
]
COMMAND_SEQUENCE_SUFFIX: List[str] = [
    '0',
    'q',
]


def calc_cdft(base_fchk: Path, plus_fchk: Path, minus_fchk: Path,
              multiwfn_bin: Path = DEFAULT_MULTIWFN, output_path: Path | None = None) -> Path:
    for p in (base_fchk, plus_fchk, minus_fchk):
        if not p.exists():
            raise FileNotFoundError(f'FCHK file not found: {p}')
    if not multiwfn_bin.exists():
        raise FileNotFoundError(f'Multiwfn executable not found: {multiwfn_bin}')

    out_path = output_path or base_fchk.with_name(base_fchk.stem + '_CDFT.txt')
    out_path.parent.mkdir(parents=True, exist_ok=True)

    payload = '\n'.join(COMMAND_SEQUENCE_PREFIX + [str(base_fchk), str(plus_fchk), str(minus_fchk)] + COMMAND_SEQUENCE_SUFFIX) + '\n'
    print(f'[Multiwfn-CDFT] {multiwfn_bin} {base_fchk} (+ {plus_fchk}, {minus_fchk}) -> {out_path}')

    with out_path.open('w', encoding='utf-8') as handle:
        subprocess.run(
            [str(multiwfn_bin), str(base_fchk)],
            input=payload,
            text=True,
            stdout=handle,
            stderr=subprocess.STDOUT,
            check=True,
            cwd=base_fchk.parent,
        )

    generated = base_fchk.parent / 'CDFT.txt'
    if generated.exists() and generated.resolve() != out_path.resolve():
        shutil.move(str(generated), str(out_path))
    return out_path


def main() -> None:
    parser = argparse.ArgumentParser(description='Compute CDFT descriptors using Multiwfn')
    parser.add_argument('base_fchk', help='Path to the neutral Gaussian .fchk file')
    parser.add_argument('plus_fchk', help='Path to the N+1 Gaussian .fchk file')
    parser.add_argument('minus_fchk', help='Path to the N-1 Gaussian .fchk file')
    parser.add_argument('--multiwfn', help='Path to the Multiwfn executable (defaults to bundled copy)')
    parser.add_argument('--output', help='Optional output path for the generated _CDFT.txt report')
    args = parser.parse_args()

    multiwfn_bin = Path(args.multiwfn).expanduser().resolve() if args.multiwfn else DEFAULT_MULTIWFN
    base_fchk = Path(args.base_fchk).expanduser().resolve()
    plus_fchk = Path(args.plus_fchk).expanduser().resolve()
    minus_fchk = Path(args.minus_fchk).expanduser().resolve()
    output = Path(args.output).expanduser().resolve() if args.output else None

    result = calc_cdft(base_fchk, plus_fchk, minus_fchk, multiwfn_bin=multiwfn_bin, output_path=output)
    print(f'Saved CDFT analysis to {result}')


if __name__ == '__main__':
    main()
