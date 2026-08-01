import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Dict, Optional

import numpy as np
from rdkit import Chem
from rdkit.Chem import AllChem

from hpc_client import SupercomputerClient

try:
    from djh.formchk_interface import FormchkInterface
    from djh.my_libs import logfile, Mwfn
    from djh.cdft import read_CDFT, runcdft
    from djh.read_he import read_hole_contri
except ImportError:
    print("Warning: Custom 'djh' modules not found. Descriptor extraction step may fail if not run in the correct environment.")


class StageError(RuntimeError):
    def __init__(self, stage: str, message: str):
        super().__init__(message)
        self.stage = stage


# ---------------------------------------------------------------------------
# Structure preparation helpers
# ---------------------------------------------------------------------------
def smiles_to_xyz(smiles: str, output_path: Path) -> str:
    mol = Chem.MolFromSmiles(smiles)
    if mol is None:
        raise ValueError(f"Failed to parse SMILES: {smiles}")

    mol = Chem.AddHs(mol)
    strategies = []

    p1 = AllChem.ETKDGv3(); p1.randomSeed = 42
    strategies.append(("ETKDGv3(seed=42)", p1))
    p2 = AllChem.ETKDGv3(); p2.randomSeed = 7; p2.useRandomCoords = True
    strategies.append(("ETKDGv3(seed=7,randomCoords)", p2))
    p3 = AllChem.ETKDGv3(); p3.randomSeed = 2026; p3.useRandomCoords = True
    strategies.append(("ETKDGv3(seed=2026,randomCoords)", p3))
    p4 = AllChem.ETKDGv2(); p4.randomSeed = 99; p4.useRandomCoords = True
    strategies.append(("ETKDGv2(seed=99,randomCoords)", p4))

    last_status = None
    last_error = None
    success = False

    for label, params in strategies:
        work_mol = Chem.Mol(mol)
        try:
            status = AllChem.EmbedMolecule(work_mol, params)
            print(f"[INFO] Embed attempt {label}: status={status}")
            if status == 0:
                try:
                    AllChem.UFFOptimizeMolecule(work_mol, maxIters=500)
                except Exception as opt_exc:
                    print(f"[WARN] UFF optimize failed after {label}: {opt_exc}")
                mol = work_mol
                last_status = status
                success = True
                break
            last_status = status
        except Exception as exc:
            last_error = exc
            print(f"[WARN] Embed attempt {label} raised: {exc}")

    if not success:
        try:
            work_mol = Chem.Mol(mol)
            status = AllChem.EmbedMolecule(work_mol, randomSeed=1234, useRandomCoords=True)
            print(f"[INFO] Embed attempt distance-geometry fallback: status={status}")
            if status == 0:
                try:
                    AllChem.UFFOptimizeMolecule(work_mol, maxIters=500)
                except Exception as opt_exc:
                    print(f"[WARN] UFF optimize failed after distance-geometry fallback: {opt_exc}")
                mol = work_mol
                last_status = status
                success = True
            else:
                last_status = status
        except Exception as exc:
            last_error = exc
            print(f"[WARN] Distance-geometry fallback raised: {exc}")

    if not success:
        msg = f"3D embedding failed after multiple strategies (last status {last_status}). Check SMILES: {smiles}"
        if last_error is not None:
            msg += f" | last exception: {last_error}"
        raise RuntimeError(msg)

    conf = mol.GetConformer()
    num_atoms = mol.GetNumAtoms()
    lines = [str(num_atoms), f"Generated from SMILES: {smiles}"]
    for i in range(num_atoms):
        atom = mol.GetAtomWithIdx(i)
        pos = conf.GetAtomPosition(i)
        lines.append(f"{atom.GetSymbol():2s}  {pos.x:12.6f}  {pos.y:12.6f}  {pos.z:12.6f}")

    xyz_text = "\n".join(lines) + "\n"
    output_path.write_text(xyz_text)
    print(f"[INFO] 初始XYZ结构已生成: {output_path} ({num_atoms} atoms)")
    return xyz_text


def generate_gjf(xyz_path: Path, job_type: str, nproc='64', mem='32gb') -> Path:
    chrg = '0'
    spin = '1'
    if job_type == 'opt':
        key1 = '#p opt freq wb97xd nosymm 6-311+g** cphf=grid=fine'
    elif job_type == 'plus':
        key1 = '#p stable=opt wb97xd nosymm 6-311+g** scf=xqc'
        chrg = '-1'; spin = '2'
    elif job_type == 'minus':
        key1 = '#p stable=opt wb97xd nosymm 6-311+g** scf=xqc'
        chrg = '1'; spin = '2'
    elif job_type == 'tdsp':
        key1 = '#p pbe1pbe/def2tzvp iop(9/40=4) td(nstates=5,root=1,50-50) nosymm'
    else:
        raise ValueError(f"Unknown job type: {job_type}")

    xyz_lines = xyz_path.read_text().splitlines()
    gjf_path = xyz_path.with_suffix('.gjf')
    chk_name = xyz_path.stem + '.chk'
    with open(gjf_path, 'w') as f:
        f.write(f'%nproc={nproc}\n')
        f.write(f'%mem={mem}\n')
        f.write(f'%chk={chk_name}\n')
        f.write(f'{key1}\n\n')
        f.write(f'Title: {job_type} calculation\n\n')
        f.write(f'{chrg} {spin}\n')
        for line in xyz_lines[2:]:
            f.write(line + '\n')
        f.write('\n\n')
    print(f"[INFO] GJF文件已生成: {gjf_path} (Job: {job_type})")
    return gjf_path


# ---------------------------------------------------------------------------
# Remote Gaussian execution helpers
# ---------------------------------------------------------------------------
def run_dohe_analysis(fchk_path: Path, env_var: str = "DOHE_SCRIPT_PATH"):
    skill_root = Path(__file__).resolve().parents[2] / 'multiwfn-mac'
    helper_script = skill_root / 'scripts' / 'calc_he_s1.py'
    multiwfn_bin = skill_root / 'multiwfn' / 'multiwfn'
    output_path = fchk_path.with_suffix('.he.txt')
    if output_path.exists():
        print(f"[INFO] Reusing existing HE analysis: {output_path}")
        return output_path
    if not helper_script.exists():
        raise FileNotFoundError(f"Multiwfn helper skill not found: {helper_script}")
    cmd = [sys.executable, str(helper_script), str(fchk_path), '--output', str(output_path)]
    if multiwfn_bin.exists():
        cmd.extend(['--multiwfn', str(multiwfn_bin)])
    print(f"[RUNNING] Executing hole-electron analysis via multiwfn skill helper {helper_script} ...")
    subprocess.run(cmd, cwd=fchk_path.parent, check=True)
    return output_path


def run_remote_gaussian(gjf_path: Path, client: SupercomputerClient, job_type: str,
                        is_tdsp: bool = False,
                        dohe_env_var: str = "DOHE_SCRIPT_PATH") -> Path:
    workdir = gjf_path.parent
    job_name = gjf_path.stem
    expected_log = workdir / f"{job_name}.log"
    expected_fchk = workdir / f"{job_name}.fchk"
    if expected_log.exists() and expected_fchk.exists():
        print(f"[INFO] Reusing existing {job_type} artifacts: {expected_log}, {expected_fchk}")
        if is_tdsp:
            run_dohe_analysis(expected_fchk, dohe_env_var)
        return expected_log

    print(f"[HPC] Submitting job {job_name} ({job_type}) from {workdir} ...")
    try:
        submission = client.submit_gaussian_job(gjf_path, job_type=job_type)
        job_id = submission['job_id']
        task_id = submission['task_id']
        client.wait_for_completion(job_id)
        artifacts = client.download_results(task_id, workdir, job_name)
    except Exception as exc:
        raise StageError(job_type, f"remote stage failed for {job_name}/{job_type}: {exc}")

    log_path = artifacts['log']
    fchk_path = artifacts['fchk']
    if is_tdsp:
        try:
            run_dohe_analysis(fchk_path, dohe_env_var)
        except Exception as exc:
            raise StageError(job_type, f"HE analysis failed for {job_name}/{job_type}: {exc}")

    print(f"[HPC] Job {job_name} completed successfully.")
    return log_path


# ---------------------------------------------------------------------------
# Post-processing helpers
# ---------------------------------------------------------------------------
def log_to_xyz_multiwfn(log_path: Path) -> Path:
    xyz_path = log_path.with_suffix('.xyz')
    if xyz_path.exists():
        print(f"[INFO] Reusing existing xyz: {xyz_path}")
        return xyz_path
    skill_root = Path(__file__).resolve().parents[2] / 'multiwfn-mac'
    helper_script = skill_root / 'scripts' / 'log_to_xyz.py'
    multiwfn_bin = skill_root / 'multiwfn' / 'multiwfn'
    if not helper_script.exists():
        raise FileNotFoundError(f"Multiwfn log→xyz helper skill not found: {helper_script}")
    cmd = [sys.executable, str(helper_script), str(log_path), '--output', str(xyz_path)]
    if multiwfn_bin.exists():
        cmd.extend(['--multiwfn', str(multiwfn_bin)])
    print(f"[INFO] 正在通过 multiwfn skill 将 {log_path} 转换为 {xyz_path} ...")
    subprocess.run(cmd, check=True)
    return xyz_path


def write_descriptor_sidecar(workdir: Path, base_name: str, notes):
    sidecar = workdir / f"{base_name}.descriptor-notes.txt"
    sidecar.write_text("\n".join(notes) + "\n", encoding='utf-8')
    return sidecar


def extract_descriptors(workdir: Path, base_name: str, des_output: str):
    print(f"[INFO] 开始提取描述符...")
    cwd = Path.cwd()
    os.chdir(workdir)

    notes = []
    fchknam = f"{base_name}.fchk"
    neutral_log = f"{base_name}.log"
    tdlog = f"tdsp/{base_name}.log"
    tdfchk = f"tdsp/{fchknam}"
    shutil.copy(f"minus/{fchknam}", f"./{base_name}-1.fchk")
    shutil.copy(f"plus/{fchknam}", f"./{base_name}+1.fchk")

    original_stdout = os.sys.stdout
    try:
        with open(des_output, 'w') as f_out:
            os.sys.stdout = f_out
            fchk = FormchkInterface(fchknam)
            homo = fchk.homo()[0]
            lumo = fchk.lumo()[0]
            gap = fchk.gap()[0]
            print('HOMO: ', homo)
            print('LUMO: ', lumo)
            print('GAP: ', gap)

            runcdft(fchknam)
            _, _, _, _, _, _, _, _, _, _, _, _, vip, vea, _, hardness, _ = read_CDFT(fchknam)
            print('VIP: ', vip)
            print('VEA: ', vea)
            print('Hardness: ', hardness)
            print('Electrophilicity index: ', round((vip+vea)**2/4/2/(vip-vea),4))

            mwfn = Mwfn(input_file=neutral_log)
            polar = None
            if hasattr(mwfn, 'get_mole_polar'):
                polar = mwfn.get_mole_polar()
            if polar is not None:
                print('Isotropic polarizability: ', polar)
                print('POLAR: ', polar)
            else:
                notes.append('POLAR unavailable: helper/log parsing did not provide isotropic polarizability')
                print('Isotropic polarizability: N/A')
                print('POLAR: N/A')

            dipole_norm = None
            if hasattr(logfile, 'dipole'):
                log = logfile(lognam=neutral_log)
                dipole = log.dipole()
                dipole_norm = np.linalg.norm(dipole)
            if dipole_norm is not None:
                print('Dipole moment magnitude: ', dipole_norm)
                print('DIPOLE: ', dipole_norm)
            else:
                notes.append('DIPOLE unavailable: logfile helper mismatch or dipole parser not available in current environment')
                print('Dipole moment magnitude: N/A')
                print('DIPOLE: N/A')

            triplet_lines = subprocess.getoutput(f"grep ' <S\\*\\*2>=2.000' {tdlog}")
            singlet_lines = subprocess.getoutput(f"grep ' <S\\*\\*2>=0.000' {tdlog}")
            ex_energy_t1 = float(triplet_lines.split('\n')[0].split()[-6])
            ex_energy_s1 = float(singlet_lines.split('\n')[0].split()[-6])
            fosc_s1 = singlet_lines.split('\n')[0].split()[-2].split('=')[-1]
            delta_est = round(ex_energy_s1 - ex_energy_t1, 4)
            print('ex_energy_s1(E_S1): ', ex_energy_s1)
            print('fosc_s1: ', fosc_s1)
            print('ex_energy_t1: ', ex_energy_t1)
            print('Singlet-triplet gap(delta_est): ', delta_est)
            print('ex_energy_s1: ', ex_energy_s1)
            print('fosc: ', fosc_s1)
            print('delta_est: ', delta_est)

            sr, d_index, hdi, edi, _, _ = read_hole_contri(tdfchk)
            print('sr: ', sr)
            print('d_index: ', d_index)
            print('hdi: ', hdi)
            print('edi: ', edi)
    finally:
        os.sys.stdout = original_stdout
        os.chdir(cwd)

    if notes:
        sidecar = write_descriptor_sidecar(workdir, base_name, [f'name: {base_name}', f'workdir: {workdir}', 'workflow_return_code: 0', '', 'missing_or_partial_items:'] + [f'- {n}' for n in notes])
        print(f"[INFO] workflow succeeded; wrote sidecar for partial optional fields: {sidecar}")
    print(f"[INFO] 描述符提取完成，已保存至: {workdir / des_output}")


# ---------------------------------------------------------------------------
# Main workflow
# ---------------------------------------------------------------------------
def load_resources_override(json_str: Optional[str]) -> Optional[Dict]:
    if not json_str:
        return None
    return json.loads(json_str)


def save_stage_status(workdir: Path, name: str, payload: Dict):
    path = workdir / f"{name}.stage-status.json"
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')


def main():
    parser = argparse.ArgumentParser(description="Automated SMILES to Chemical Descriptors Workflow")
    parser.add_argument("--smiles", type=str, required=True)
    parser.add_argument("--name", type=str, default="molecule")
    parser.add_argument("--workdir", type=str, default="calc_workspace")
    parser.add_argument("--nproc", type=str, default="64")
    parser.add_argument("--mem", type=str, default="32gb")
    parser.add_argument("--config", type=str, default="config/supercomputer_config.json")
    parser.add_argument("--resources", type=str, default=None)
    parser.add_argument("--dohe-env", type=str, default="DOHE_SCRIPT_PATH")
    args = parser.parse_args()

    workdir = Path(args.workdir).resolve()
    workdir.mkdir(parents=True, exist_ok=True)
    print(f"=== 开始执行计算流 | 工作目录: {workdir} ===")

    client = SupercomputerClient(args.config)
    try:
        client.debug_log_path = str(workdir / f"{args.name}.hpc.debug.log")
    except Exception:
        pass
    resource_override = load_resources_override(args.resources)
    if resource_override:
        print("[WARN] Resource overrides are ignored by the script-based submission workflow.")

    stage_payload = {'name': args.name, 'workdir': str(workdir), 'status': 'running', 'completed_stages': []}
    save_stage_status(workdir, args.name, stage_payload)

    try:
        init_xyz = workdir / f"{args.name}.xyz"
        if not init_xyz.exists():
            smiles_to_xyz(args.smiles, init_xyz)
        else:
            print(f"[INFO] Reusing existing initial xyz: {init_xyz}")
        stage_payload['completed_stages'].append('smiles_to_xyz')
        save_stage_status(workdir, args.name, stage_payload)

        opt_gjf = generate_gjf(init_xyz, job_type='opt', nproc=args.nproc, mem=args.mem)
        opt_log = run_remote_gaussian(opt_gjf, client, job_type='opt', is_tdsp=False, dohe_env_var=args.dohe_env)
        stage_payload['completed_stages'].append('opt')
        save_stage_status(workdir, args.name, stage_payload)

        opt_xyz = log_to_xyz_multiwfn(opt_log)
        stage_payload['completed_stages'].append('log_to_xyz')
        save_stage_status(workdir, args.name, stage_payload)

        for state in ['plus', 'minus', 'tdsp']:
            state_dir = workdir / state
            state_dir.mkdir(parents=True, exist_ok=True)
            state_xyz = state_dir / f"{args.name}.xyz"
            if not state_xyz.exists():
                shutil.copy(opt_xyz, state_xyz)
            gjf_path = generate_gjf(state_xyz, job_type=state, nproc=args.nproc, mem=args.mem)
            run_remote_gaussian(gjf_path, client, job_type=state, is_tdsp=(state == 'tdsp'), dohe_env_var=args.dohe_env)
            stage_payload['completed_stages'].append(state)
            save_stage_status(workdir, args.name, stage_payload)

        des_filename = f"{args.name}.des"
        if not (workdir / des_filename).exists():
            extract_descriptors(workdir, args.name, des_filename)
        else:
            print(f"[INFO] Reusing existing descriptor file: {workdir / des_filename}")
        stage_payload['completed_stages'].append('descriptors')
        stage_payload['status'] = 'success'
        save_stage_status(workdir, args.name, stage_payload)

        print(f"=== 工作流执行完毕 ===")
        print(f"数据保存目录: {workdir}")
        print(f"最终描述符文件: {workdir / des_filename}")
        return workdir, workdir / des_filename
    except StageError as exc:
        stage_payload['status'] = 'failed'
        stage_payload['failed_stage'] = exc.stage
        stage_payload['error'] = str(exc)
        save_stage_status(workdir, args.name, stage_payload)
        raise
    except Exception as exc:
        stage_payload['status'] = 'failed'
        stage_payload['failed_stage'] = 'local'
        stage_payload['error'] = str(exc)
        save_stage_status(workdir, args.name, stage_payload)
        raise


if __name__ == "__main__":
    main()
