#!/usr/bin/env python3
"""Convert a Gaussian log file to xyz using Multiwfn."""
from __future__ import annotations

import argparse
import subprocess
from pathlib import Path
from typing import List

DEFAULT_MULTIWFN = Path(__file__).resolve().parent.parent / 'multiwfn' / 'multiwfn'
COMMAND_SEQUENCE_PREFIX: List[str] = [
    '100',
    '2',
    '2',
]
COMMAND_SEQUENCE_SUFFIX: List[str] = [
    '0',
    'q',
]


def log_to_xyz(log_path: Path, multiwfn_bin: Path = DEFAULT_MULTIWFN, output_path: Path | None = None) -> Path:
    if not log_path.exists():
        raise FileNotFoundError(f'Log file not found: {log_path}')
    if not multiwfn_bin.exists():
        raise FileNotFoundError(f'Multiwfn executable not found: {multiwfn_bin}')

    out_path = output_path or log_path.with_suffix('.xyz')
    out_path.parent.mkdir(parents=True, exist_ok=True)
    payload = '\n'.join(COMMAND_SEQUENCE_PREFIX + [str(out_path)] + COMMAND_SEQUENCE_SUFFIX) + '\n'

    print(f'[Multiwfn-LOG2XYZ] {multiwfn_bin} {log_path} -> {out_path}')
    subprocess.run(
        [str(multiwfn_bin), str(log_path)],
        input=payload,
        text=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.STDOUT,
        check=True,
        cwd=log_path.parent,
    )
    return out_path


def main() -> None:
    parser = argparse.ArgumentParser(description='Convert Gaussian log to xyz using Multiwfn')
    parser.add_argument('log', help='Path to the Gaussian .log file')
    parser.add_argument('--multiwfn', help='Path to the Multiwfn executable (defaults to bundled copy)')
    parser.add_argument('--output', help='Optional output xyz path')
    args = parser.parse_args()

    multiwfn_bin = Path(args.multiwfn).expanduser().resolve() if args.multiwfn else DEFAULT_MULTIWFN
    log_path = Path(args.log).expanduser().resolve()
    output = Path(args.output).expanduser().resolve() if args.output else None

    result = log_to_xyz(log_path, multiwfn_bin=multiwfn_bin, output_path=output)
    print(f'Saved xyz to {result}')


if __name__ == '__main__':
    main()
