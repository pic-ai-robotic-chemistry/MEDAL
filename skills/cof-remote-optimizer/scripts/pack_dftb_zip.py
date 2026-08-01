#!/usr/bin/env python3
"""Prepare DFTB+ job bundles (POSCAR + dftb_in.hsd + source CIF) for remote submission."""
from __future__ import annotations

import argparse
import shutil
import tempfile
import zipfile
from pathlib import Path

from ase.io import read, write


def pack_single(cif_path: Path, hsd_path: Path, output_dir: Path) -> Path:
    if not cif_path.exists():
        raise FileNotFoundError(f"CIF not found: {cif_path}")
    if not hsd_path.exists():
        raise FileNotFoundError(f"dftb_in.hsd not found: {hsd_path}")

    atoms = read(cif_path)
    stem = cif_path.stem
    output_dir.mkdir(parents=True, exist_ok=True)
    zip_path = output_dir / f"{stem}_dftb_input.zip"

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        poscar_path = tmp / "POSCAR"
        write(poscar_path, atoms, format="vasp")
        shutil.copy2(hsd_path, tmp / "dftb_in.hsd")
        shutil.copy2(cif_path, tmp / cif_path.name)

        with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            zf.write(poscar_path, arcname="POSCAR")
            zf.write(tmp / "dftb_in.hsd", arcname="dftb_in.hsd")
            zf.write(tmp / cif_path.name, arcname=cif_path.name)

    return zip_path


def main() -> None:
    parser = argparse.ArgumentParser(description="Bundle CIF + POSCAR + dftb_in.hsd for remote DFTB")
    parser.add_argument("cifs", nargs="+", help="One or more CIF files produced by the mol2cif step")
    parser.add_argument("--hsd", default="resources/step2_dftb_opt/dftb_in.hsd",
                        help="Template dftb_in.hsd to copy into each bundle")
    parser.add_argument("--out", default="build/dftb_zips", help="Output directory for ZIP archives")
    args = parser.parse_args()

    hsd_path = Path(args.hsd).expanduser().resolve()
    out_dir = Path(args.out).expanduser().resolve()

    for cif in args.cifs:
        zip_path = pack_single(Path(cif).expanduser().resolve(), hsd_path, out_dir)
        print(f"[PACK] {zip_path}")


if __name__ == "__main__":
    main()
