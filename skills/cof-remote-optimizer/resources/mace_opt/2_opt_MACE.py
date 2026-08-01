import sys
from mace.calculators import mace_off, mace_mp
from ase.io import read, write
from ase.optimize import BFGS, LBFGS, FIRE, GPMin, MDMin, QuasiNewton
from ase.filters import UnitCellFilter, ExpCellFilter, FrechetCellFilter
import re
import io
from contextlib import redirect_stdout
import os
import pandas as pd
from joblib import Parallel, delayed
import json

import torch
import numpy as np
import random

#####################################################################
# os.environ['OMP_NUM_THREADS'] = '1'
# os.environ['MKL_NUM_THREADS'] = '1'
# os.environ['PYTHONHASHSEED'] = '1'
# torch.manual_seed(1)
# np.random.seed(1)
# random.seed(1)
# torch.cuda.manual_seed(1)
# torch.cuda.manual_seed_all(1)
# torch.backends.cudnn.deterministic = True
# torch.backends.cudnn.benchmark = False

os.environ["OMP_NUM_THREADS"] = "1"
os.environ["OPENBLAS_NUM_THREADS"] = "1"
os.environ["MKL_NUM_THREADS"] = "1"
os.environ["VECLIB_MAXIMUM_THREADS"] = "1"
os.environ["NUMEXPR_NUM_THREADS"] = "1"
torch.set_num_threads(1)
#####################################################################
n_jobs = 4
path = './'
target_folder = "/data_raw/"

#####################################################################

def calculate_density(crystal):
    # 计算总质量，ASE 中的 get_masses 方法返回一个数组，包含了所有原子的质量
    total_mass = sum(crystal.get_masses())  # 转换为克

    # 获取体积，ASE 的 get_volume 方法返回晶胞的体积，单位是 Å^3
    # 1 Å^3 = 1e-24 cm^3
    volume = crystal.get_volume()  # 转换为立方厘米

    # 计算密度，质量除以体积
    density = total_mass / (volume * 10 ** -24) / (6.022140857 * 10 ** 23)  # 单位是 g/cm^3
    return density


def run_calculation_one(path, file, target_folder, idx):
    os.environ["CUDA_VISIBLE_DEVICES"] = str(idx % 1 +0)
    # print("working on structure {}".format(idx))

    with io.StringIO() as buf, redirect_stdout(buf):
#        try:
#        molecule_single = file.split('_')[-1].split('.')[0]

        # molecule_count, density = optimization(path, file, target_folder, molecule_single,scalar_pressure=scalar_pressure)
        crystal = read(path + target_folder + file)
#        molecule_count = len(crystal.get_atomic_numbers()) / int(molecule_single)
        molecule_count = 1
        molecule_single = 1
        calc = mace_off(model="/home/zcxzcx1/volatile/model/MACE-OFF23_small.model", dispersion=True, device='cuda')
        crystal.calc = calc
        sf = FrechetCellFilter(crystal, scalar_pressure=0.0006)
        optimizer = QuasiNewton(sf)
        optimizer.run(fmax=0.01, steps=3000)
        crystal.write(path + 'cif_result_press/' + file[:-4] + "_press.cif")

        crystal = read(path + 'cif_result_press/' + file[:-4] + "_press.cif")
        crystal.calc = calc
        sf = FrechetCellFilter(crystal)
        # optimizer = BFGS(sf)
        optimizer = QuasiNewton(sf)
        optimizer.run(fmax=0.01, steps=3000)
        density = calculate_density(crystal)
        crystal.write(path + 'cif_result_final/' + file[:-4] + "_opt.cif")

        output = buf.getvalue()

        # Now worker stdout is available, write it into log file
#        with open("./test/aaa.log", "w") as f:
#            f.write(output)
        output = re.sub(r"\[[^\]]*\]", "", output)
        energy = float(re.split("\\s+", output.split('\n')[-2])[3][:])
        step_used = float(re.split("\\s+", output.split('\n')[-2])[1][:])
        energy_per_mol = energy / molecule_count * 96.485
        # 创建一个新行的字典
        new_row = {'name': file[:-4], 'density': density, 'energy_per_mol': energy_per_mol, 'energy': energy,
                   'molecule_count': molecule_count, 'molecule_single': molecule_single, 'step_used': step_used}

#        except:
#            new_row = {'name': file[:-4], 'density': 100000.0, 'energy_per_mol': 100000.0, 'energy': 100000.0,
#                       'molecule_count': 100000.0, 'molecule_single': 100000.0, 'step_used': 100000}
    #    print("{}/{}，{:.2%}, {} calculation is finished,density:{}, energy:{}, step used: {}".format(idx+1, len(files), idx / len(files),
    #                                                                           file, density, energy_per_mol, step_used))
    # print_gpu_memory_usage()
    #    molecule_count, density = optimization(path, file, target_folder, molecule_single)
    with open(path + 'json_result/' + file[:-4] + ".json", 'w') as json_file:
        json.dump(new_row, json_file, indent=4)
        
    return new_row


def already_have_calculation_one(path, file, target_folder, idx):
    # print("reading on structure {}".format(idx))
    with open(path + 'json_result/' + file[:-4] + ".json", 'r') as file:
        old_row = json.load(file)
    return old_row


# path = '/home/zhudan/Desktop/chengxi/std_test'
# molecule_single = 14
# target_folder = "/fox_raw/"
# df = pd.DataFrame(columns=['name', 'density', 'energy_kj', 'step_used'])
#
# for root, dirs, files in os.walk(path + target_folder):
#     new_row = Parallel(n_jobs=1)(delayed(run_calculation_one)(path,file,target_folder,molecule_single,idx) for idx,file in enumerate(files[:]))
#     for row in new_row:
#         df = pd.concat([df, pd.DataFrame([row])], ignore_index=True, axis=0)
#     df.to_csv(path + '/result.csv')

df = pd.DataFrame(columns=['name', 'density','energy_per_mol', 'energy', 'molecule_count', 'molecule_single', 'step_used'])

try:
    os.mkdir(path+"/cif_result_press")
    os.mkdir(path+"/cif_result_final")
except:
    pass
try:
    os.mkdir(path+"/json_result")
except:
    pass
    
for root, dirs, files in os.walk(path + "/json_result/"):
    for file in files:
        with open(path + 'json_result/' + file, 'r') as full_file:
            json_row = json.load(full_file)   
        if all(json_row[key] == value for key, value in {'density': 100000.0,'energy_per_mol': 100000.0,'energy': 100000.0,'molecule_count': 100000.0,'molecule_single': 100000.0,'step_used': 100000.0}.items()):
            os.remove(path + 'json_result/' + file)
            print(str(path + 'json_result/' + file)+" is removed since calculation is not completed", json_row)

for root, dirs, files in os.walk(path + target_folder):
    old_row = Parallel(n_jobs=n_jobs)(
        delayed(already_have_calculation_one)(path, file, target_folder, idx) for idx, file in
        enumerate(files) if os.path.exists(path + 'json_result/' + file[:-4] + ".json"))

    filtered_files = [file for file in files if not os.path.exists(path + 'json_result/' + file[:-4] + ".json")]
    new_row = Parallel(n_jobs=n_jobs)(
        delayed(run_calculation_one)(path, file, target_folder, idx) for idx, file in
        enumerate(filtered_files))

    for row in new_row:
        df = pd.concat([df, pd.DataFrame([row])], ignore_index=True, axis=0)
    for row in old_row:
        df = pd.concat([df, pd.DataFrame([row])], ignore_index=True, axis=0)


df.to_csv(path + '/result.csv')


