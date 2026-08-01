import os
import glob

def convert_xyz_to_gjf(xyz_file, output_dir, method="B3LYP/6-31G* em=gd3bj"):
    with open(xyz_file, 'r') as f:
        lines = f.readlines()
    
    natoms = int(lines[0].strip())
    title = lines[1].strip() or os.path.basename(xyz_file)
    
    coords = []
    for line in lines[2:2+natoms]:
        parts = line.split()
        element = parts[0]
        x, y, z = parts[1], parts[2], parts[3]
        # 氢原子标记为0（优化），其他原子标记为-1（冻结）
        flag = 0 if element.upper() == 'H' else -1
        coords.append(f"{element}  {flag}  {x}  {y}  {z}")
    
    basename = os.path.splitext(os.path.basename(xyz_file))[0]
    gjf_file = os.path.join(output_dir, f"{basename}.gjf")
    
    with open(gjf_file, 'w') as f:
        f.write(f"%chk={basename}.chk\n")
        f.write('%mem=10gb\n')
        f.write('%nproc=16\n')
        f.write(f"# {method} Opt\n\n")
        f.write(f"{title}\n\n")
        f.write("0 1\n")
        f.write("\n".join(coords))
        f.write("\n\n")
    
    print(f"生成: {gjf_file}")

# 使用方法
input_dir = "./"      # xyz文件所在目录
output_dir = "./"     # 输出目录
os.makedirs(output_dir, exist_ok=True)

for xyz in glob.glob(os.path.join(input_dir, "*.xyz")):
    convert_xyz_to_gjf(xyz, output_dir)
