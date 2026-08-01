#!/usr/bin/env python3
from __future__ import annotations
import json
import os
import re
import subprocess
import sys
import traceback
from pathlib import Path

ROOT = Path('/Users/zikaixie/.openclaw/workspace')
WORKDIR = Path('/Users/zikaixie/.openclaw/workspace/runs/cof-fluor-20260417-2019/ami-18')
NAME = 'ami-18'
SMILES = 'C(#Cc1cc(C#Cc2ccccc2)c2ccc3c(C#Cc4ccccc4)cc(C#Cc4ccccc4)c4ccc1c2c43)c1ccccc1'
SKILL_SCRIPTS = ROOT / 'skills' / 'cof-monomer-tdsp-workflow' / 'scripts'
CONFIG = SKILL_SCRIPTS / 'config' / 'supercomputer_config.json'
SIDEcar = WORKDIR / f'{NAME}.descriptor-notes.txt'
DES = WORKDIR / f'{NAME}.des'
LOG = WORKDIR / 'wrapper.status.log'

sys.path.insert(0, str(SKILL_SCRIPTS))
os.chdir(ROOT)

from monomer_calc import extract_descriptors  # type: ignore
from djh.formchk_interface import FormchkInterface  # type: ignore
from djh.cdft import runcdft, read_CDFT  # type: ignore
from djh.read_he import read_hole_contri  # type: ignore


def log(msg: str) -> None:
    text = msg.rstrip() + '\n'
    print(text, end='')
    with LOG.open('a', encoding='utf-8') as fh:
        fh.write(text)


def grep_first_float(pattern: str, text: str):
    m = re.search(pattern, text, re.MULTILINE)
    return float(m.group(1)) if m else None


def build_best_effort_des() -> tuple[list[str], list[str]]:
    missing: list[str] = []
    lines: list[str] = []

    neutral_fchk = WORKDIR / f'{NAME}.fchk'
    neutral_log = WORKDIR / f'{NAME}.log'
    td_log = WORKDIR / 'tdsp' / f'{NAME}.log'
    td_fchk = WORKDIR / 'tdsp' / f'{NAME}.fchk'
    cdft_txt = WORKDIR / f'{NAME}_CDFT.txt'

    try:
        fchk = FormchkInterface(str(neutral_fchk))
        homo = fchk.homo()[0]
        lumo = fchk.lumo()[0]
        gap = fchk.gap()[0]
        lines += [f'HOMO:  {homo}', f'LUMO:  {lumo}', f'GAP:  {gap}']
    except Exception as e:
        missing.append(f'HOMO/LUMO/GAP unavailable: {e}')

    cwd = Path.cwd()
    os.chdir(WORKDIR)
    try:
        if not (WORKDIR / f'{NAME}+1.fchk').exists() and (WORKDIR / 'plus' / f'{NAME}.fchk').exists():
            import shutil
            shutil.copy(WORKDIR / 'plus' / f'{NAME}.fchk', WORKDIR / f'{NAME}+1.fchk')
        if not (WORKDIR / f'{NAME}-1.fchk').exists() and (WORKDIR / 'minus' / f'{NAME}.fchk').exists():
            import shutil
            shutil.copy(WORKDIR / 'minus' / f'{NAME}.fchk', WORKDIR / f'{NAME}-1.fchk')
        try:
            runcdft(f'{NAME}.fchk')
        except Exception as e:
            missing.append(f'CDFT helper execution issue: {e}')

        vip = vea = hardness = None
        try:
            _ = read_CDFT(f'{NAME}.fchk')
            vip = _[12]
            vea = _[13]
            hardness = _[15]
        except Exception as e:
            missing.append(f'Full CDFT parse incomplete: {e}')
            if cdft_txt.exists():
                txt = cdft_txt.read_text(encoding='utf-8', errors='ignore')
                vip = grep_first_float(r'(?:First\s+)?vertical IP:\s+([-+]?\d*\.?\d+)', txt)
                vea = grep_first_float(r'(?:First\s+)?vertical EA:\s+([-+]?\d*\.?\d+)', txt)
                hardness = grep_first_float(r'Hardness\s*:?\s+([-+]?\d*\.?\d+)', txt)
        if vip is not None:
            lines.append(f'VIP:  {vip}')
        else:
            missing.append('VIP missing from CDFT output')
        if vea is not None:
            lines.append(f'VEA:  {vea}')
        else:
            missing.append('VEA missing from CDFT output')
        if hardness is not None:
            lines.append(f'Hardness:  {hardness}')
        else:
            missing.append('Hardness missing from CDFT output')
        if vip is not None and vea is not None and (vip - vea) != 0:
            electroph = round((vip + vea) ** 2 / 8 / (vip - vea), 4)
            lines.append(f'Electrophilicity index:  {electroph}')
        else:
            missing.append('Electrophilicity index not computed because VIP/VEA were incomplete')
    finally:
        os.chdir(cwd)

    try:
        des_text = DES.read_text(encoding='utf-8', errors='ignore') if DES.exists() else ''
    except Exception:
        des_text = ''

    polar_match = re.search(r'POLAR:\s*(.+)', des_text)
    dipole_match = re.search(r'DIPOLE:\s*(.+)', des_text)
    polar_val = polar_match.group(1).strip() if polar_match else None
    dipole_val = dipole_match.group(1).strip() if dipole_match else None

    if polar_val and polar_val != 'N/A':
        lines.append(f'POLAR:  {polar_val}')
    else:
        missing.append('POLAR unavailable: helper/log parsing did not provide isotropic polarizability')
    if dipole_val and dipole_val != 'N/A':
        lines.append(f'DIPOLE:  {dipole_val}')
    else:
        missing.append('DIPOLE unavailable: logfile helper mismatch or dipole parser not available in current environment')

    try:
        txt = td_log.read_text(encoding='utf-8', errors='ignore')
        singlet = re.search(r'Excited State\s+\d+:\s+Singlet\S*\s+([0-9.]+) eV\s+.*?f=([0-9.]+)', txt)
        triplet = re.search(r'Excited State\s+\d+:\s+Triplet\S*\s+([0-9.]+) eV', txt)
        if singlet:
            s1 = float(singlet.group(1))
            fosc = singlet.group(2)
            lines += [f'ex_energy_s1(E_S1):  {s1}', f'fosc_s1:  {fosc}', f'ex_energy_s1:  {s1}', f'fosc:  {fosc}']
        else:
            s1 = None
            missing.append('S1 excitation energy / oscillator strength missing from tdsp log')
        if triplet:
            t1 = float(triplet.group(1))
            lines.append(f'ex_energy_t1:  {t1}')
        else:
            t1 = None
            missing.append('T1 excitation energy missing from tdsp log')
        if singlet and triplet:
            delta = round(s1 - t1, 4)
            lines += [f'Singlet-triplet gap(delta_est):  {delta}', f'delta_est:  {delta}']
    except Exception as e:
        missing.append(f'TDSP parsing failed: {e}')

    try:
        sr, d_index, hdi, edi, hole_contri, elec_contri = read_hole_contri(str(td_fchk))
        lines += [f'sr:  {sr}', f'd_index:  {d_index}', f'hdi:  {hdi}', f'edi:  {edi}']
    except Exception as e:
        missing.append(f'HE metrics unavailable: {e}')

    return lines, missing


def write_sidecar(missing: list[str], workflow_rc: int, workflow_err: str | None):
    side_lines = [
        f'name: {NAME}',
        f'workdir: {WORKDIR}',
        f'workflow_return_code: {workflow_rc}',
    ]
    if workflow_err:
        side_lines += ['', 'workflow_error:', workflow_err.strip()]
    side_lines += ['', 'missing_or_partial_items:']
    if missing:
        side_lines.extend([f'- {m}' for m in missing])
    else:
        side_lines.append('- none')
    SIDEcar.write_text('\n'.join(side_lines) + '\n', encoding='utf-8')


def main() -> int:
    WORKDIR.mkdir(parents=True, exist_ok=True)
    for p in [LOG, SIDEcar]:
        if p.exists():
            p.unlink()
    cmd = [
        sys.executable,
        str(SKILL_SCRIPTS / 'monomer_calc.py'),
        '--smiles', SMILES,
        '--name', NAME,
        '--workdir', str(WORKDIR),
        '--config', str(CONFIG),
    ]
    log('[START] launching monomer workflow')
    log('[CMD] ' + ' '.join(cmd))
    proc = subprocess.run(cmd, cwd=ROOT, text=True, capture_output=True)
    if proc.stdout:
        log('[STDOUT]\n' + proc.stdout)
    if proc.stderr:
        log('[STDERR]\n' + proc.stderr)

    workflow_err = None
    if proc.returncode != 0:
        workflow_err = f'workflow failed with rc={proc.returncode}'
        log(f'[WARN] primary workflow exited rc={proc.returncode}; attempting best-effort descriptor salvage')

    missing: list[str] = []
    try:
        if proc.returncode == 0 and DES.exists():
            des_text = DES.read_text(encoding='utf-8', errors='ignore')
            if 'POLAR: N/A' in des_text:
                missing.append('POLAR unavailable: helper/log parsing did not provide isotropic polarizability')
            if 'DIPOLE: N/A' in des_text:
                missing.append('DIPOLE unavailable: logfile helper mismatch or dipole parser not available in current environment')
            if missing:
                write_sidecar(missing, proc.returncode, workflow_err)
                log('[INFO] workflow succeeded; wrote sidecar for partial optional fields')
            else:
                write_sidecar([], proc.returncode, workflow_err)
                log('[INFO] workflow succeeded with complete descriptor set expected by current wrapper checks')
            return 0

        lines, missing = build_best_effort_des()
        DES.write_text('\n'.join(lines).rstrip() + '\n', encoding='utf-8')
        write_sidecar(missing, proc.returncode, workflow_err)
        log('[INFO] best-effort descriptor file written after primary workflow issue')
        return 0
    except Exception:
        tb = traceback.format_exc()
        log('[FATAL] salvage failed\n' + tb)
        write_sidecar(missing + [f'Salvage failed: {tb.splitlines()[-1]}'], proc.returncode, workflow_err)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
