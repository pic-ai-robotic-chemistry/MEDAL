#!/usr/bin/env python3
"""Convert remote DFTB+ artifacts (geo_end.*) into *_dftb_opted.cif."""
from __future__ import annotations

import argparse
import tempfile
import zipfile
from pathlib import Path

from ase.io import read, write


def extract(zip_path: Path, output_dir: Path | None = None) -> Path:
    if not zip_path.exists():
        raise FileNotFoundError(zip_path)
    output_dir = output_dir or zip_path.parent

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        with zipfile.ZipFile(zip_path, "r") as zf:
            zf.extractall(tmp)

        # prefer geo_end.gen, then geo_end.xyz
        candidate = None
        for name in ["geo_end.gen", "geo_end.xyz"]:
            matches = list(tmp.rglob(name))
            if matches:
                candidate = matches[0]
                break
        if candidate is None:
            raise FileNotFoundError("No geo_end.gen/geo_end.xyz inside the archive")

        atoms = read(candidate)
        stem = zip_path.stem.replace("_input", "")
        out_path = Path(output_dir) / f"{stem}_dftb_opted.cif"
        write(out_path, atoms, format="cif")
        print(f"[DFTB] wrote {out_path}")
        return out_path


def main() -> None:
    parser = argparse.ArgumentParser(description="Extract geo_end.* from a DFTB result ZIP and write CIF")
    parser.add_argument("zip", help="ZIP archive downloaded from the DFTB runner")
    parser.add_argument("--out", help="Directory for the optimized CIF (defaults to ZIP parent)")
    args = parser.parse_args()

    extract(Path(args.zip).expanduser().resolve(), Path(args.out).expanduser().resolve() if args.out else None)


if __name__ == "__main__":
    main()
