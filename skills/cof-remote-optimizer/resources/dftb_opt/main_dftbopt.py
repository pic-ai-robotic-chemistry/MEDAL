# 第二步的处理: 将第一步生成的cif文件用DFTB+优化
# 需要服务器上部署DFTB+
# 运行方法：（1）将dftb_in.hsd和所有第一步生成的cif文件放在当前文件夹下。
# （2）运行python ./main_dftbopt.py 这一步批量优化cif文件的结构（串行）
# （3）运行结束后会在当前目录下生成一系列XXX_dftb_opted.cif文件，都是优化完毕的结果文件，用于下一步的结构优化


import os,sys,glob
from ase.io import read, write
allcif=glob.glob('*.cif')

# Generate the working dirs
for cifnam in allcif:
    pfxnam=cifnam.split('.')[0]
    os.system('mkdir -p '+pfxnam)
    atoms = read(cifnam)
    write("POSCAR", atoms, format="vasp")
    os.system('mv POSCAR '+pfxnam)
    os.system('cp dftb_in.hsd '+pfxnam)

def subdftb(i):
    pfxnam=i.split('.')[0]
    os.chdir(pfxnam)
    os.system('dftb+ > '+pfxnam+'.out')
    # 文件名
    gen_file = "geo_end.gen"
    xyz_file = "geo_end.xyz"

    # 检查输出文件是否存在
    if os.path.isfile(gen_file):
        atoms = read(gen_file)
        print(f"Using {gen_file} as source geometry.")
    elif os.path.isfile(xyz_file):
        atoms = read(xyz_file)
        print(f"Using {xyz_file} as source geometry.")
    else:
        raise FileNotFoundError("No optimized structure file found (geo_end.xyz or geo_end.gen)")

    # 写出 POSCAR
    write("DFTB_opt_POSCAR", atoms, format="vasp")

    # 写出 CIF
    write(f"{pfxnam}_dftb_opted.cif", atoms, format="cif")
    print(f"CIF file written: {pfxnam}_dftb_opted.cif")
    # 复制到当前文件夹
    os.system(f'cp {pfxnam}_dftb_opted.cif ..')
    os.chdir('..')

# Submit the task

for cifnam in allcif:
    subdftb(cifnam)

# allgen2cif.py
