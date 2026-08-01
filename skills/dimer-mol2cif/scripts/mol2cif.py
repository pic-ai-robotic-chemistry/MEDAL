# Auto-generated from mol2cif.ipynb

import numpy as np
from rdkit import Chem
from rdkit.Chem import AllChem
from rdkit.Chem.Draw import rdMolDraw2D
from rdkit.Chem.rdMolDescriptors import CalcMolFormula
from rdkit.Geometry import Point3D
import sys

# ==================== 基础工具函数 ====================

def read_mol_file(filepath):
    mol = Chem.MolFromMolFile(filepath, removeHs=False)
    if mol is None:
        raise ValueError(f"无法读取mol文件: {filepath}")
    return mol

def find_aldehyde_groups(mol):
    groups = []
    for atom in mol.GetAtoms():
        if atom.GetSymbol() == 'C':
            for bond in atom.GetBonds():
                neighbor = bond.GetOtherAtom(atom)
                if neighbor.GetSymbol() == 'O' and bond.GetBondType() == Chem.BondType.DOUBLE:
                    if neighbor.GetDegree() == 1:
                        groups.append((atom.GetIdx(), neighbor.GetIdx()))
                        break
    return groups

def find_amine_nitrogens(mol):
    nitrogens = []
    for atom in mol.GetAtoms():
        if atom.GetSymbol() == 'N':
            h_count = atom.GetTotalNumHs()
            if h_count >= 2 and atom.GetDegree() == 1:
                nitrogens.append(atom.GetIdx())
    return nitrogens

def draw_molecule(mol, filepath, size=(1200, 900)):
    drawer = rdMolDraw2D.MolDraw2DCairo(size[0], size[1])
    drawer.drawOptions().addAtomIndices = False
    drawer.DrawMolecule(mol)
    drawer.FinishDrawing()
    with open(filepath, 'wb') as f:
        f.write(drawer.GetDrawingText())
    print(f"  结构图已保存: {filepath}")

def rotate_vec_2d(vec, angle_deg):
    angle = np.radians(angle_deg)
    cos_a, sin_a = np.cos(angle), np.sin(angle)
    return np.array([cos_a * vec[0] - sin_a * vec[1], sin_a * vec[0] + cos_a * vec[1]])

def mirror_point_along_axis(point, axis_origin, axis_dir):
    p_rel = point - axis_origin
    d = axis_dir / np.linalg.norm(axis_dir)
    p_mirror = 2 * np.dot(p_rel, d) * d - p_rel
    return p_mirror + axis_origin

def mirror_vec_along_axis(vec, axis_dir):
    d = axis_dir / np.linalg.norm(axis_dir)
    return 2 * np.dot(vec, d) * d - vec

def rotate_point(point, center, angle):
    """2D旋转点（只影响x,y，保留z如果存在）"""
    cos_a, sin_a = np.cos(angle), np.sin(angle)
    p = point[:2] - center[:2]
    rotated = np.array([cos_a * p[0] - sin_a * p[1], sin_a * p[0] + cos_a * p[1]])
    return rotated + center[:2]

def rotate_point_3d(point, center, angle):
    """2D旋转点，保留z坐标"""
    cos_a, sin_a = np.cos(angle), np.sin(angle)
    p = np.array([point[0] - center[0], point[1] - center[1]])
    rotated_xy = np.array([cos_a * p[0] - sin_a * p[1], sin_a * p[0] + cos_a * p[1]])
    z = point[2] if len(point) > 2 else 0
    return np.array([rotated_xy[0] + center[0], rotated_xy[1] + center[1], z])

def mirror_point_along_axis_3d(point, axis_origin, axis_dir):
    """沿轴镜像点，只影响x,y，保留z坐标"""
    p_rel = np.array([point[0] - axis_origin[0], point[1] - axis_origin[1]])
    d = axis_dir[:2] / np.linalg.norm(axis_dir[:2])
    p_mirror = 2 * np.dot(p_rel, d) * d - p_rel
    z = point[2] if len(point) > 2 else 0
    return np.array([p_mirror[0] + axis_origin[0], p_mirror[1] + axis_origin[1], z])

def get_edge_direction(conf, vertex_idx, all_vertices_idx):
    vertex_pos = np.array([conf.GetAtomPosition(vertex_idx).x, conf.GetAtomPosition(vertex_idx).y])
    min_dist = float('inf')
    nearest_pos = None
    for idx in all_vertices_idx:
        if idx == vertex_idx:
            continue
        pos = np.array([conf.GetAtomPosition(idx).x, conf.GetAtomPosition(idx).y])
        dist = np.linalg.norm(pos - vertex_pos)
        if dist < min_dist:
            min_dist = dist
            nearest_pos = pos
    edge_dir = nearest_pos - vertex_pos
    return edge_dir / np.linalg.norm(edge_dir)

def calc_edge_parallelism(ald_edge_dir, ami_edge_dir_original, ami_ny_dir, nc_dir, flip):
    current_edge = ami_edge_dir_original.copy()
    current_ny = ami_ny_dir.copy()
    if flip:
        current_edge = mirror_vec_along_axis(current_edge, current_ny)
    target_ny = rotate_vec_2d(nc_dir, 120)
    rot_angle = np.arctan2(target_ny[1], target_ny[0]) - np.arctan2(current_ny[1], current_ny[0])
    cos_r, sin_r = np.cos(rot_angle), np.sin(rot_angle)
    final_edge = np.array([
        cos_r * current_edge[0] - sin_r * current_edge[1],
        sin_r * current_edge[0] + cos_r * current_edge[1]
    ])
    return np.abs(np.dot(ald_edge_dir, final_edge))

# ==================== 分子合并函数 ====================

def determine_flip(ald_path, ami_path):
    """根据边平行度判断是否需要翻转"""
    ald_mol = read_mol_file(ald_path)
    ami_mol = read_mol_file(ami_path)
    # 不再调用Compute2DCoords，直接使用原有坐标
    
    ald_conf = ald_mol.GetConformer()
    ami_conf = ami_mol.GetConformer()
    
    ald_groups = find_aldehyde_groups(ald_mol)
    ami_nitrogens = find_amine_nitrogens(ami_mol)
    
    ald_c_indices = [g[0] for g in ald_groups]
    ald_c_idx, ald_o_idx = ald_groups[0]
    ami_n_idx = ami_nitrogens[0]
    
    ald_edge_dir = get_edge_direction(ald_conf, ald_c_idx, ald_c_indices)
    ami_edge_dir = get_edge_direction(ami_conf, ami_n_idx, ami_nitrogens)
    
    ami_n_atom = ami_mol.GetAtomWithIdx(ami_n_idx)
    ami_y_idx = None
    for neighbor in ami_n_atom.GetNeighbors():
        if neighbor.GetSymbol() == 'C':
            ami_y_idx = neighbor.GetIdx()
            break
    
    ami_n_pos = np.array([ami_conf.GetAtomPosition(ami_n_idx).x, ami_conf.GetAtomPosition(ami_n_idx).y])
    ami_y_pos = np.array([ami_conf.GetAtomPosition(ami_y_idx).x, ami_conf.GetAtomPosition(ami_y_idx).y])
    ami_ny_dir = (ami_y_pos - ami_n_pos) / np.linalg.norm(ami_y_pos - ami_n_pos)
    
    ald_c_pos = np.array([ald_conf.GetAtomPosition(ald_c_idx).x, ald_conf.GetAtomPosition(ald_c_idx).y])
    ald_o_pos = np.array([ald_conf.GetAtomPosition(ald_o_idx).x, ald_conf.GetAtomPosition(ald_o_idx).y])
    co_dir = ald_o_pos - ald_c_pos
    nc_dir = -co_dir / np.linalg.norm(co_dir)
    
    p_noflip = calc_edge_parallelism(ald_edge_dir, ami_edge_dir, ami_ny_dir, nc_dir, False)
    p_flip = calc_edge_parallelism(ald_edge_dir, ami_edge_dir, ami_ny_dir, nc_dir, True)
    
    dev_noflip = min(abs(p_noflip), 1 - abs(p_noflip))
    dev_flip = min(abs(p_flip), 1 - abs(p_flip))
    
    return dev_flip < dev_noflip, p_noflip, p_flip

def merge_with_2d_coords_and_track(ald_mol, ami_mol, flip=False):
    """合并分子并跟踪删除的顶点位置"""
    
    def snap_direction_to_standard(direction):
        """将方向舍入到最近的标准方向（30度的倍数）"""
        standard_angles = [i * 30 for i in range(12)]
        angle = np.degrees(np.arctan2(direction[1], direction[0]))
        if angle < 0:
            angle += 360
        
        # 找到最近的标准角度
        min_diff = float('inf')
        best_angle = 0
        for sa in standard_angles:
            diff = abs(angle - sa)
            if diff > 180:
                diff = 360 - diff
            if diff < min_diff:
                min_diff = diff
                best_angle = sa
        
        rad = np.radians(best_angle)
        return np.array([np.cos(rad), np.sin(rad)])
    
    # 不再调用Compute2DCoords，直接使用原有坐标
    
    ald_groups = find_aldehyde_groups(ald_mol)
    ami_nitrogens = find_amine_nitrogens(ami_mol)
    
    ald_c_idx, ald_o_idx = ald_groups[0]
    ami_n_idx = ami_nitrogens[0]
    
    ald_conf = ald_mol.GetConformer()
    ami_conf = ami_mol.GetConformer()
    
    # 记录ald所有CHO的位置和方向
    ald_vertex_info = []
    for i, (c_idx, o_idx) in enumerate(ald_groups):
        if i == 0:
            continue
        c_pos = np.array([ald_conf.GetAtomPosition(c_idx).x, ald_conf.GetAtomPosition(c_idx).y])
        c_atom = ald_mol.GetAtomWithIdx(c_idx)
        ring_c_idx = None
        for neighbor in c_atom.GetNeighbors():
            if neighbor.GetIdx() != o_idx:
                ring_c_idx = neighbor.GetIdx()
                break
        ring_c_pos = np.array([ald_conf.GetAtomPosition(ring_c_idx).x, ald_conf.GetAtomPosition(ring_c_idx).y])
        direction = c_pos - ring_c_pos
        direction = direction / np.linalg.norm(direction)
        # 舍入到标准方向
        direction = snap_direction_to_standard(direction)
        ald_vertex_info.append((ring_c_idx, ring_c_pos, direction))
    
    # 记录ami所有NH2的位置和方向
    ami_vertex_info = []
    for i, n_idx in enumerate(ami_nitrogens):
        if i == 0:
            continue
        n_pos = np.array([ami_conf.GetAtomPosition(n_idx).x, ami_conf.GetAtomPosition(n_idx).y])
        n_atom = ami_mol.GetAtomWithIdx(n_idx)
        ring_c_idx = None
        for neighbor in n_atom.GetNeighbors():
            if neighbor.GetSymbol() == 'C':
                ring_c_idx = neighbor.GetIdx()
                break
        ring_c_pos = np.array([ami_conf.GetAtomPosition(ring_c_idx).x, ami_conf.GetAtomPosition(ring_c_idx).y])
        direction = n_pos - ring_c_pos
        direction = direction / np.linalg.norm(direction)
        # 舍入到标准方向
        direction = snap_direction_to_standard(direction)
        ami_vertex_info.append((ring_c_idx, ring_c_pos, direction))
    
    # 对ami进行变换
    ald_c_pos = np.array([ald_conf.GetAtomPosition(ald_c_idx).x, ald_conf.GetAtomPosition(ald_c_idx).y])
    ald_o_pos = np.array([ald_conf.GetAtomPosition(ald_o_idx).x, ald_conf.GetAtomPosition(ald_o_idx).y])
    
    ami_n_pos = np.array([ami_conf.GetAtomPosition(ami_n_idx).x, ami_conf.GetAtomPosition(ami_n_idx).y])
    ami_n_atom = ami_mol.GetAtomWithIdx(ami_n_idx)
    ami_y_idx = None
    for neighbor in ami_n_atom.GetNeighbors():
        if neighbor.GetSymbol() == 'C':
            ami_y_idx = neighbor.GetIdx()
            break
    ami_y_pos = np.array([ami_conf.GetAtomPosition(ami_y_idx).x, ami_conf.GetAtomPosition(ami_y_idx).y])
    
    # 翻转
    if flip:
        ny_dir = ami_y_pos - ami_n_pos
        for i in range(ami_mol.GetNumAtoms()):
            pos = ami_conf.GetAtomPosition(i)
            p = np.array([pos.x, pos.y])
            p_new = mirror_point_along_axis(p, ami_n_pos, ny_dir)
            ami_conf.SetAtomPosition(i, Point3D(p_new[0], p_new[1], pos.z))  # 保留z坐标
        for j in range(len(ami_vertex_info)):
            ring_c_idx, ring_c_pos, direction = ami_vertex_info[j]
            new_ring_c_pos = np.array([ami_conf.GetAtomPosition(ring_c_idx).x, ami_conf.GetAtomPosition(ring_c_idx).y])
            new_direction = mirror_vec_along_axis(direction, ny_dir)
            ami_vertex_info[j] = (ring_c_idx, new_ring_c_pos, new_direction)
        ami_y_pos = np.array([ami_conf.GetAtomPosition(ami_y_idx).x, ami_conf.GetAtomPosition(ami_y_idx).y])
    
    target_n_pos = ald_o_pos
    cn_dir = target_n_pos - ald_c_pos
    cn_dir = cn_dir / np.linalg.norm(cn_dir)
    nc_dir = -cn_dir
    #target_ny_dir = rotate_vec_2d(nc_dir, -120)
 
    target_ny_dir = rotate_vec_2d(nc_dir, 120)
    current_ny_dir = ami_y_pos - ami_n_pos
    current_ny_dir = current_ny_dir / np.linalg.norm(current_ny_dir)
    
    rot_angle = np.arctan2(target_ny_dir[1], target_ny_dir[0]) - np.arctan2(current_ny_dir[1], current_ny_dir[0])
    cos_r, sin_r = np.cos(rot_angle), np.sin(rot_angle)
    
    ami_n_pos = np.array([ami_conf.GetAtomPosition(ami_n_idx).x, ami_conf.GetAtomPosition(ami_n_idx).y])
    
    # 旋转ami分子
    for i in range(ami_mol.GetNumAtoms()):
        pos = ami_conf.GetAtomPosition(i)
        p = np.array([pos.x, pos.y]) - ami_n_pos
        new_p = np.array([cos_r * p[0] - sin_r * p[1], sin_r * p[0] + cos_r * p[1]])
        new_p = new_p + ami_n_pos
        ami_conf.SetAtomPosition(i, Point3D(new_p[0], new_p[1], pos.z))  # 保留z坐标
    
    for j in range(len(ami_vertex_info)):
        ring_c_idx, ring_c_pos, direction = ami_vertex_info[j]
        new_ring_c_pos = np.array([ami_conf.GetAtomPosition(ring_c_idx).x, ami_conf.GetAtomPosition(ring_c_idx).y])
        new_direction = np.array([cos_r * direction[0] - sin_r * direction[1], sin_r * direction[0] + cos_r * direction[1]])
        ami_vertex_info[j] = (ring_c_idx, new_ring_c_pos, new_direction)
    
    # 平移ami分子
    ami_n_pos_new = np.array([ami_conf.GetAtomPosition(ami_n_idx).x, ami_conf.GetAtomPosition(ami_n_idx).y])
    translation = target_n_pos - ami_n_pos_new
    for i in range(ami_mol.GetNumAtoms()):
        pos = ami_conf.GetAtomPosition(i)
        ami_conf.SetAtomPosition(i, Point3D(pos.x + translation[0], pos.y + translation[1], pos.z))  # 保留z坐标
    
    for j in range(len(ami_vertex_info)):
        ring_c_idx, ring_c_pos, direction = ami_vertex_info[j]
        new_ring_c_pos = np.array([ami_conf.GetAtomPosition(ring_c_idx).x, ami_conf.GetAtomPosition(ring_c_idx).y])
        ami_vertex_info[j] = (ring_c_idx, new_ring_c_pos, direction)
    
    # 合并分子
    combined = Chem.RWMol(Chem.CombineMols(ald_mol, ami_mol))
    offset = ald_mol.GetNumAtoms()
    ami_n_combined_idx = ami_n_idx + offset
    
    for j in range(len(ami_vertex_info)):
        ring_c_idx, ring_c_pos, direction = ami_vertex_info[j]
        ami_vertex_info[j] = (ring_c_idx + offset, ring_c_pos, direction)
    
    combined.RemoveBond(ald_c_idx, ald_o_idx)
    combined.RemoveAtom(ald_o_idx)
    
    def update_idx(idx, removed_idx):
        return idx - 1 if removed_idx < idx else idx
    
    ami_n_combined_idx = update_idx(ami_n_combined_idx, ald_o_idx)
    ald_c_idx = update_idx(ald_c_idx, ald_o_idx)
    for j in range(len(ald_vertex_info)):
        ring_c_idx, ring_c_pos, direction = ald_vertex_info[j]
        ald_vertex_info[j] = (update_idx(ring_c_idx, ald_o_idx), ring_c_pos, direction)
    for j in range(len(ami_vertex_info)):
        ring_c_idx, ring_c_pos, direction = ami_vertex_info[j]
        ami_vertex_info[j] = (update_idx(ring_c_idx, ald_o_idx), ring_c_pos, direction)
    
    imine_c_idx = ald_c_idx
    imine_n_idx = ami_n_combined_idx
    
    combined.AddBond(ald_c_idx, ami_n_combined_idx, Chem.BondType.DOUBLE)
    
    # 删除剩余的CHO
    while True:
        combined.UpdatePropertyCache(strict=False)
        ald_groups_remaining = find_aldehyde_groups(combined)
        if not ald_groups_remaining:
            break
        c_idx, o_idx = ald_groups_remaining[-1]
        c_atom = combined.GetAtomWithIdx(c_idx)
        ring_c_idx = None
        for neighbor in c_atom.GetNeighbors():
            if neighbor.GetSymbol() == 'C' and neighbor.GetIsAromatic():
                ring_c_idx = neighbor.GetIdx()
                break
        combined.RemoveBond(c_idx, o_idx)
        if ring_c_idx is not None:
            combined.RemoveBond(c_idx, ring_c_idx)
        atoms_to_remove = sorted([c_idx, o_idx], reverse=True)
        for rem_idx in atoms_to_remove:
            combined.RemoveAtom(rem_idx)
            imine_c_idx = update_idx(imine_c_idx, rem_idx)
            imine_n_idx = update_idx(imine_n_idx, rem_idx)
            for j in range(len(ald_vertex_info)):
                idx, pos, direction = ald_vertex_info[j]
                ald_vertex_info[j] = (update_idx(idx, rem_idx), pos, direction)
            for j in range(len(ami_vertex_info)):
                idx, pos, direction = ami_vertex_info[j]
                ami_vertex_info[j] = (update_idx(idx, rem_idx), pos, direction)
    
    # 删除剩余的NH2
    while True:
        combined.UpdatePropertyCache(strict=False)
        ami_nitrogens_remaining = find_amine_nitrogens(combined)
        if not ami_nitrogens_remaining:
            break
        n_idx = ami_nitrogens_remaining[-1]
        n_atom = combined.GetAtomWithIdx(n_idx)
        ring_c_idx = None
        for neighbor in n_atom.GetNeighbors():
            if neighbor.GetSymbol() == 'C':
                ring_c_idx = neighbor.GetIdx()
                break
        if ring_c_idx is not None:
            combined.RemoveBond(n_idx, ring_c_idx)
        combined.RemoveAtom(n_idx)
        imine_c_idx = update_idx(imine_c_idx, n_idx)
        imine_n_idx = update_idx(imine_n_idx, n_idx)
        for j in range(len(ald_vertex_info)):
            idx, pos, direction = ald_vertex_info[j]
            ald_vertex_info[j] = (update_idx(idx, n_idx), pos, direction)
        for j in range(len(ami_vertex_info)):
            idx, pos, direction = ami_vertex_info[j]
            ami_vertex_info[j] = (update_idx(idx, n_idx), pos, direction)
    
    Chem.SanitizeMol(combined)
    
    return combined.GetMol(), imine_c_idx, imine_n_idx, ald_vertex_info, ami_vertex_info

def add_vertex_atoms(mol, ald_vertex_info, ami_vertex_info, bond_length=1.4):
    """在顶点位置添加C和N原子"""
    mol_rw = Chem.RWMol(mol)
    conf = mol_rw.GetConformer()
    
    new_c_coords = []
    new_n_coords = []
    new_c_indices = []
    new_n_indices = []
    c_ring_indices = []
    n_ring_indices = []
    
    for ring_c_idx, ring_c_pos_recorded, direction in ald_vertex_info:
        # 使用mol中的实际坐标，而不是记录的坐标
        actual_pos = np.array([conf.GetAtomPosition(ring_c_idx).x, conf.GetAtomPosition(ring_c_idx).y])
        new_pos = actual_pos + direction * bond_length
        new_c_coords.append(new_pos)
        c_ring_indices.append(ring_c_idx)
        new_idx = mol_rw.AddAtom(Chem.Atom(6))
        new_c_indices.append(new_idx)
        conf.SetAtomPosition(new_idx, Point3D(new_pos[0], new_pos[1], 0))
        mol_rw.AddBond(ring_c_idx, new_idx, Chem.BondType.SINGLE)
    
    for ring_c_idx, ring_c_pos_recorded, direction in ami_vertex_info:
        # 使用mol中的实际坐标，而不是记录的坐标
        actual_pos = np.array([conf.GetAtomPosition(ring_c_idx).x, conf.GetAtomPosition(ring_c_idx).y])
        new_pos = actual_pos + direction * bond_length
        new_n_coords.append(new_pos)
        n_ring_indices.append(ring_c_idx)
        new_idx = mol_rw.AddAtom(Chem.Atom(7))
        new_n_indices.append(new_idx)
        conf.SetAtomPosition(new_idx, Point3D(new_pos[0], new_pos[1], 0))
        mol_rw.AddBond(ring_c_idx, new_idx, Chem.BondType.SINGLE)
    
    Chem.SanitizeMol(mol_rw)
    return mol_rw.GetMol(), new_c_coords, new_n_coords, new_c_indices, new_n_indices, c_ring_indices, n_ring_indices

# ==================== 网格对齐函数 ====================

def find_corner_vertex(coords):
    """找到3个顶点中的'角落'顶点（距离另外两个之和最小）"""
    coords = np.array(coords)
    n = len(coords)
    dist_sums = []
    for i in range(n):
        dist_sum = sum(np.linalg.norm(coords[i] - coords[j]) for j in range(n) if j != i)
        dist_sums.append(dist_sum)
    corner_idx = np.argmin(dist_sums)
    other_indices = [i for i in range(n) if i != corner_idx]
    return corner_idx, other_indices

def get_rotation_angle_to_align_axes(corner_pos, adj1_pos, adj2_pos):
    """计算需要旋转的角度，使直角与xy轴平行"""
    vec1 = adj1_pos - corner_pos
    vec1 = vec1 / np.linalg.norm(vec1)
    
    angle1 = np.arctan2(vec1[1], vec1[0])
    target_angles = [0, np.pi/2, np.pi, -np.pi/2]
    
    best_angle = 0
    best_diff = float('inf')
    for target in target_angles:
        diff = abs(angle1 - target)
        if diff > np.pi:
            diff = 2 * np.pi - diff
        if diff < best_diff:
            best_diff = diff
            best_angle = target - angle1
    
    return best_angle

def find_imine_bond(mol):
    """找到imine键（C=N双键）"""
    conf = mol.GetConformer()
    for bond in mol.GetBonds():
        if bond.GetBondType() == Chem.BondType.DOUBLE:
            a1 = bond.GetBeginAtom()
            a2 = bond.GetEndAtom()
            if (a1.GetSymbol() == 'C' and a2.GetSymbol() == 'N') or \
               (a1.GetSymbol() == 'N' and a2.GetSymbol() == 'C'):
                if a1.GetSymbol() == 'C':
                    c_idx, n_idx = a1.GetIdx(), a2.GetIdx()
                else:
                    c_idx, n_idx = a2.GetIdx(), a1.GetIdx()
                return c_idx, n_idx
    return None, None

def get_fragment_atoms(mol, start_idx, exclude_idx):
    """通过BFS获取从start_idx开始、不经过exclude_idx的所有原子"""
    visited = set([exclude_idx])
    queue = [start_idx]
    fragment = []
    
    while queue:
        idx = queue.pop(0)
        if idx in visited:
            continue
        visited.add(idx)
        fragment.append(idx)
        atom = mol.GetAtomWithIdx(idx)
        for neighbor in atom.GetNeighbors():
            n_idx = neighbor.GetIdx()
            if n_idx not in visited:
                queue.append(n_idx)
    
    return fragment

def align_to_grid(mol, c_coords, n_coords):
    """对齐分子使顶点形成的直角与xy轴平行"""
    mol_rw = Chem.RWMol(mol)
    conf = mol_rw.GetConformer()
    
    new_c_coords = [np.array(c) for c in c_coords]
    new_n_coords = [np.array(n) for n in n_coords]
    
    imine_c_idx, imine_n_idx = find_imine_bond(mol_rw)
    
    # ========== 步骤1：旋转整个分子使C顶点的直角与xy轴平行 ==========
    c_corner_idx, c_adj_indices = find_corner_vertex(new_c_coords)
    c_corner = new_c_coords[c_corner_idx]
    c_adj1 = new_c_coords[c_adj_indices[0]]
    c_adj2 = new_c_coords[c_adj_indices[1]]
    
    c_rot_angle = get_rotation_angle_to_align_axes(c_corner, c_adj1, c_adj2)
    
    if abs(c_rot_angle) > 0.001:
        for i in range(mol_rw.GetNumAtoms()):
            pos = conf.GetAtomPosition(i)
            p = np.array([pos.x, pos.y])
            new_p = rotate_point(p, np.array([0, 0]), c_rot_angle)
            conf.SetAtomPosition(i, Point3D(new_p[0], new_p[1], pos.z))  # 保留z坐标
        
        for i in range(len(new_c_coords)):
            new_c_coords[i] = rotate_point(new_c_coords[i], np.array([0, 0]), c_rot_angle)
        for i in range(len(new_n_coords)):
            new_n_coords[i] = rotate_point(new_n_coords[i], np.array([0, 0]), c_rot_angle)
    
    # ========== 步骤2：旋转ami片段使N顶点的直角与xy轴平行 ==========
    n_corner_idx, n_adj_indices = find_corner_vertex(new_n_coords)
    n_corner = new_n_coords[n_corner_idx]
    n_adj1 = new_n_coords[n_adj_indices[0]]
    n_adj2 = new_n_coords[n_adj_indices[1]]
    
    n_rot_angle = get_rotation_angle_to_align_axes(n_corner, n_adj1, n_adj2)
    
    if abs(n_rot_angle) > 0.001:
        ami_atoms = get_fragment_atoms(mol_rw, imine_n_idx, imine_c_idx)
        imine_c_pos = np.array([conf.GetAtomPosition(imine_c_idx).x, conf.GetAtomPosition(imine_c_idx).y])
        
        for atom_idx in ami_atoms:
            pos = conf.GetAtomPosition(atom_idx)
            p = np.array([pos.x, pos.y])
            new_p = rotate_point(p, imine_c_pos, n_rot_angle)
            conf.SetAtomPosition(atom_idx, Point3D(new_p[0], new_p[1], pos.z))  # 保留z坐标
        
        for i in range(len(new_n_coords)):
            new_n_coords[i] = rotate_point(new_n_coords[i], imine_c_pos, n_rot_angle)
    
    Chem.SanitizeMol(mol_rw)
    return mol_rw.GetMol(), new_c_coords, new_n_coords

# ==================== 补氢函数 ====================

def add_hydrogens_to_dimer(mol):
    """
    对dimer分子补氢：
    1. 用RDKit补氢
    2. 删除C顶点和N顶点上的H
    3. 对C顶点补2个H（sp2杂化，120度夹角）
    4. 根据imine键取向删除与对应轴更平行的H
    """
    
    # 找到aligned_mol中最后三个C原子和最后三个N原子（它们是新增的顶点原子）
    num_atoms = mol.GetNumAtoms()
    c_vertex_indices = []
    n_vertex_indices = []
    
    # 从后往前找，找到最后3个C和最后3个N
    for i in range(num_atoms - 1, -1, -1):
        atom = mol.GetAtomWithIdx(i)
        if atom.GetSymbol() == 'C' and len(c_vertex_indices) < 3:
            c_vertex_indices.append(i)
        elif atom.GetSymbol() == 'N' and len(n_vertex_indices) < 3:
            n_vertex_indices.append(i)
        if len(c_vertex_indices) == 3 and len(n_vertex_indices) == 3:
            break
    
    c_vertex_indices.sort()
    n_vertex_indices.sort()
    
    print(f"  C顶点索引: {c_vertex_indices}")
    print(f"  N顶点索引: {n_vertex_indices}")
    
    # Step 1: 用RDKit补氢
    mol_h = Chem.AddHs(mol, addCoords=True)
    print(f"  RDKit补氢后原子数: {mol_h.GetNumAtoms()}")
    
    # Step 2: 删除C顶点和N顶点上的H
    h_to_remove = []
    for idx in c_vertex_indices + n_vertex_indices:
        atom = mol_h.GetAtomWithIdx(idx)
        for neighbor in atom.GetNeighbors():
            if neighbor.GetSymbol() == 'H':
                h_to_remove.append(neighbor.GetIdx())
    
    print(f"  删除顶点H数: {len(h_to_remove)}")
    
    mol_rw = Chem.RWMol(mol_h)
    for h_idx in sorted(h_to_remove, reverse=True):
        mol_rw.RemoveAtom(h_idx)
    
    Chem.SanitizeMol(mol_rw)
    
    # Step 3: 对C顶点补2个H（120度夹角）
    # C顶点索引在删除H后不变（因为H索引都比C大）
    conf_rw = mol_rw.GetConformer()
    
    h_bond_length = 1.0
    for c_idx in c_vertex_indices:
        c_atom = mol_rw.GetAtomWithIdx(c_idx)
        c_pos = np.array([conf_rw.GetAtomPosition(c_idx).x, conf_rw.GetAtomPosition(c_idx).y])
        
        ring_c = list(c_atom.GetNeighbors())[0]
        ring_c_pos = np.array([conf_rw.GetAtomPosition(ring_c.GetIdx()).x, 
                              conf_rw.GetAtomPosition(ring_c.GetIdx()).y])
        
        d = c_pos - ring_c_pos
        d = d / np.linalg.norm(d)
        
        h1_dir = rotate_vec_2d(d, 60)
        h2_dir = rotate_vec_2d(d, -60)
        
        h1_pos = c_pos + h1_dir * h_bond_length
        h2_pos = c_pos + h2_dir * h_bond_length
        
        h1_idx = mol_rw.AddAtom(Chem.Atom(1))
        conf_rw.SetAtomPosition(h1_idx, Point3D(h1_pos[0], h1_pos[1], 0))
        mol_rw.AddBond(c_idx, h1_idx, Chem.BondType.SINGLE)
        
        h2_idx = mol_rw.AddAtom(Chem.Atom(1))
        conf_rw.SetAtomPosition(h2_idx, Point3D(h2_pos[0], h2_pos[1], 0))
        mol_rw.AddBond(c_idx, h2_idx, Chem.BondType.SINGLE)
    
    Chem.SanitizeMol(mol_rw)
    print(f"  补C顶点H后原子数: {mol_rw.GetNumAtoms()}")
    
    # Step 4: 根据imine键取向删除H
    imine_c_idx, imine_n_idx = find_imine_bond(mol_rw)
    conf_rw = mol_rw.GetConformer()
    c_pos_imine = np.array([conf_rw.GetAtomPosition(imine_c_idx).x, conf_rw.GetAtomPosition(imine_c_idx).y])
    n_pos_imine = np.array([conf_rw.GetAtomPosition(imine_n_idx).x, conf_rw.GetAtomPosition(imine_n_idx).y])
    imine_vec = n_pos_imine - c_pos_imine
    imine_vec = imine_vec / np.linalg.norm(imine_vec)
    
    if abs(imine_vec[0]) > abs(imine_vec[1]):
        imine_axis = 'X'
    else:
        imine_axis = 'Y'
    print(f"  Imine键与{imine_axis}轴更平行")
    
    # 只处理c_vertex_indices中的C原子
    h_to_remove = []
    for c_idx in c_vertex_indices:
        c_atom = mol_rw.GetAtomWithIdx(c_idx)
        c_pos = np.array([conf_rw.GetAtomPosition(c_idx).x, conf_rw.GetAtomPosition(c_idx).y])
        
        h_list = []
        for neighbor in c_atom.GetNeighbors():
            if neighbor.GetSymbol() == 'H':
                h_idx = neighbor.GetIdx()
                h_pos = np.array([conf_rw.GetAtomPosition(h_idx).x, conf_rw.GetAtomPosition(h_idx).y])
                ch_vec = h_pos - c_pos
                ch_vec = ch_vec / np.linalg.norm(ch_vec)
                
                if imine_axis == 'X':
                    parallelism = abs(ch_vec[0])
                else:
                    parallelism = abs(ch_vec[1])
                
                h_list.append((h_idx, parallelism))
        
        h_list.sort(key=lambda x: x[1], reverse=True)
        h_to_remove.append(h_list[0][0])
        print(f"    C({c_idx}): 删除H({h_list[0][0]}), 平行度={h_list[0][1]:.3f}")
    
    for h_idx in sorted(h_to_remove, reverse=True):
        mol_rw.RemoveAtom(h_idx)
    
    Chem.SanitizeMol(mol_rw)
    print(f"  最终原子数: {mol_rw.GetNumAtoms()}")
    
    return mol_rw.GetMol(),imine_axis

# ==================== 主函数 ====================

def main(ald_path, ami_path, output_prefix):
    print("=" * 70)
    print("  COF Dimer 完整流程")
    print("=" * 70)
    
    print("\n[1. 读取分子文件]")
    print(f"  ald: {ald_path}")
    print(f"  ami: {ami_path}")
    
    # 判断是否需要翻转
    print("\n[2. 计算边平行度]")
    flip, p_noflip, p_flip = determine_flip(ald_path, ami_path)
    dev_noflip = min(abs(p_noflip), 1 - abs(p_noflip))
    dev_flip = min(abs(p_flip), 1 - abs(p_flip))
    print(f"  不翻转: 边平行度 = {p_noflip:.4f}, 偏离 = {dev_noflip:.4f}")
    print(f"  翻转: 边平行度 = {p_flip:.4f}, 偏离 = {dev_flip:.4f}")
    print(f"  ✓ 选择: {'翻转' if flip else '不翻转'}")
    
    # 合并分子
    print("\n[3. 合并分子]")
    mol, c_idx, n_idx, ald_vertex_info, ami_vertex_info = merge_with_2d_coords_and_track(
        read_mol_file(ald_path),
        read_mol_file(ami_path),
        flip=flip
    )
    print(f"  ald剩余顶点: {len(ald_vertex_info)}")
    print(f"  ami剩余顶点: {len(ami_vertex_info)}")
    
    # 添加顶点原子
    print("\n[4. 添加顶点原子]")
    mol_with_vertices, new_c_coords, new_n_coords, c_indices, n_indices, c_ring_indices, n_ring_indices = add_vertex_atoms(
        mol, ald_vertex_info, ami_vertex_info
    )
    print(f"  添加C顶点: {len(new_c_coords)}个")
    print(f"  添加N顶点: {len(new_n_coords)}个")
    
    # 对齐到网格
    print("\n[5. 对齐到网格]")
    mol_aligned, aligned_c_coords, aligned_n_coords = align_to_grid(
        mol_with_vertices, new_c_coords, new_n_coords
    )
    print("  C顶点坐标:")
    for i, coord in enumerate(aligned_c_coords):
        print(f"    C{i+1}: ({coord[0]:.4f}, {coord[1]:.4f})")
    print("  N顶点坐标:")
    for i, coord in enumerate(aligned_n_coords):
        print(f"    N{i+1}: ({coord[0]:.4f}, {coord[1]:.4f})")
    
    # 补氢
    print("\n[6. 补氢]")
    mol_final,imine_axis = add_hydrogens_to_dimer(mol_aligned)
    
    # 保存最终结果
    print("\n[7. 保存结果]")
    final_mol_path = f"{output_prefix}_final.mol"
    final_png_path = f"{output_prefix}_final.png"
    Chem.MolToMolFile(mol_final, final_mol_path)
    print(f"  MOL文件: {final_mol_path}")
    draw_molecule(mol_final, final_png_path)
    
    # 同时保存中间结果
    aligned_mol_path = f"{output_prefix}_aligned.mol"
    Chem.MolToMolFile(mol_aligned, aligned_mol_path)
    print(f"  对齐MOL文件: {aligned_mol_path}")
    
    print("\n" + "=" * 70)
    print("完成!")
    print("=" * 70)
    
    return mol_final,np.array(aligned_c_coords),np.array(aligned_n_coords),imine_axis




# Cell 参数：a，b
import numpy as np

def max_axis_distance(A: np.ndarray, B: np.ndarray):
    A = np.asarray(A)
    B = np.asarray(B)
    assert A.shape == (3, 2) and B.shape == (3, 2)

    Ax, Ay = A[:, 0], A[:, 1]
    Bx, By = B[:, 0], B[:, 1]

    Dx = max(abs(Ax.max() - Bx.min()), abs(Bx.max() - Ax.min()))
    Dy = max(abs(Ay.max() - By.min()), abs(By.max() - Ay.min()))
    return Dx, Dy

import glob,os
# 注意需要跑两次
### 第一次：角度为120度 target_ny_dir = rotate_vec_2d(nc_dir, 120) 
ald_mols=glob.glob('ald-result/*.mol')
os.makedirs('cif_results',exist_ok=True)
ald_mols=glob.glob('ald-result/*.mol')
ami_mols=glob.glob('ami-result/*.mol')
### 第二次：角度为-120度 # target_ny_dir = rotate_vec_2d(nc_dir, -120)

#nums=[9,15,17,18,19,20,21,23,24,26,28,30,33,34,36,37,38,39,40]
#ald_mols=[f'ald-result/ald-{n}.mol' for n in nums]


for ald_path in ald_mols:
    for ami_path in ami_mols:
        ald_id = ald_path.split('ald-')[-1].split('.')[-2]
        ami_id = ami_path.split('ami-')[-1].split('.')[-2]
        output_prefix=f"./cif_results/dimer_ald-{ald_id}_ami-{ami_id}"
        final_mol,aligned_c_coords,aligned_n_coords,imine_axis=main(ald_path, ami_path, output_prefix)
        a,b=max_axis_distance(aligned_c_coords,aligned_n_coords)
        if imine_axis=='X':
            a+=1.5
        else:
            b+=1.5
        # 测试：搭建CIF文件
        from ase.io import read, write
        from ase import Atoms
        import numpy as np

        output_prefix=f"./cif_results/dimer_ald-{ald_id}_ami-{ami_id}"
        # 读取mol文件（单个重复单元）
        mol = read(f'{output_prefix}_final.mol')

        # 定义晶胞（斜方晶系示例）
        # a, b 是平面内的周期矢量长度
        # gamma 是a和b之间的夹角（斜着复制的关键）
        # c 是层间距
        a = a   
        b = b
        c = 12   
        alpha = 90
        beta = 90
        gamma = 90 
        mol.set_cell([a, b, c, alpha, beta, gamma])
        mol.set_pbc(True)

        # 关键：调整边界原子位置，使其在周期性边界处正确成键
        # 这需要根据你的具体结构手动调整

        mol.center()
        write(f'{output_prefix}.cif', mol)

### 第二次：角度为-120度 # target_ny_dir = rotate_vec_2d(nc_dir, -120)
#ald_mols=['ald-result/ald-6.mol','ald-result/ald-27.mol']
#nums=[9,15,17,18,19,20,21,23,24,26,28,30,33,34,36,37,38,39,40]
#ald_mols=[f'ald-result/ald-{n}.mol' for n in nums]


