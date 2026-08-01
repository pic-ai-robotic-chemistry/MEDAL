#!/usr/bin/env python3
"""
从CIF晶体结构中提取分子子结构 - Jupyter Notebook版本

依赖: pip install numpy networkx
"""

import re
import numpy as np
import networkx as nx
from networkx.algorithms import isomorphism
from pathlib import Path
from collections import deque, Counter

# ============== 解析器 ==============

class CIFParser:
    """解析CIF文件"""
    
    @staticmethod
    def parse(filepath):
        with open(filepath, 'r') as f:
            content = f.read()
        
        # 提取晶胞参数
        cell_params = {}
        patterns = {
            'a': r'_cell_length_a\s+([\d.]+)',
            'b': r'_cell_length_b\s+([\d.]+)',
            'c': r'_cell_length_c\s+([\d.]+)',
            'alpha': r'_cell_angle_alpha\s+([\d.]+)',
            'beta': r'_cell_angle_beta\s+([\d.]+)',
            'gamma': r'_cell_angle_gamma\s+([\d.]+)'
        }
        for key, pattern in patterns.items():
            match = re.search(pattern, content)
            if match:
                cell_params[key] = float(match.group(1))
        
        # 提取原子坐标
        atoms = []
        lines = content.split('\n')
        in_atom_loop = False
        header_indices = {}
        
        for line in lines:
            line = line.strip()
            if line.startswith('loop_'):
                in_atom_loop = False
                header_indices = {}
            elif line.startswith('_atom_site_'):
                in_atom_loop = True
                key = line.split()[0]
                header_indices[key] = len(header_indices)
            elif in_atom_loop and line and not line.startswith('_'):
                parts = line.split()
                if len(parts) >= 5:
                    try:
                        element = parts[header_indices.get('_atom_site_type_symbol', 0)]
                        label = parts[header_indices.get('_atom_site_label', 1)]
                        fract_x = float(parts[header_indices.get('_atom_site_fract_x', 3)])
                        fract_y = float(parts[header_indices.get('_atom_site_fract_y', 4)])
                        fract_z = float(parts[header_indices.get('_atom_site_fract_z', 5)])
                        atoms.append({
                            'element': element,
                            'label': label,
                            'fract': np.array([fract_x, fract_y, fract_z])
                        })
                    except (ValueError, IndexError):
                        continue
        
        return cell_params, atoms


class MOLParser:
    """解析MOL文件（使用RDKit）"""
    
    @staticmethod
    def parse(filepath):
        from rdkit import Chem
        
        mol = Chem.MolFromMolFile(filepath, removeHs=False)
        if mol is None:
            raise ValueError(f"RDKit无法解析MOL文件: {filepath}")
        
        # 提取原子
        atoms = []
        for atom in mol.GetAtoms():
            atoms.append({'element': atom.GetSymbol()})
        
        # 提取键
        bonds = []
        for bond in mol.GetBonds():
            a1 = bond.GetBeginAtomIdx()
            a2 = bond.GetEndAtomIdx()
            # 键类型：1=单键, 2=双键, 3=三键
            btype = int(bond.GetBondTypeAsDouble())
            bonds.append((a1, a2, btype))
        
        return atoms, bonds


# ============== 晶胞变换 ==============

class CellTransform:
    """分数坐标与笛卡尔坐标转换"""
    
    def __init__(self, cell_params):
        a, b, c = cell_params['a'], cell_params['b'], cell_params['c']
        alpha = np.radians(cell_params['alpha'])
        beta = np.radians(cell_params['beta'])
        gamma = np.radians(cell_params['gamma'])
        
        cos_a, cos_b, cos_g = np.cos(alpha), np.cos(beta), np.cos(gamma)
        sin_g = np.sin(gamma)
        
        self.matrix = np.array([
            [a, b * cos_g, c * cos_b],
            [0, b * sin_g, c * (cos_a - cos_b * cos_g) / sin_g],
            [0, 0, c * np.sqrt(1 - cos_a**2 - cos_b**2 - cos_g**2 + 2*cos_a*cos_b*cos_g) / sin_g]
        ])
        self.inv_matrix = np.linalg.inv(self.matrix)
    
    def to_cartesian(self, fract):
        return np.dot(self.matrix, fract)
    
    def min_image_distance(self, fract1, fract2):
        delta = fract2 - fract1
        delta = delta - np.round(delta)
        cart_delta = np.dot(self.matrix, delta)
        return np.linalg.norm(cart_delta)


# ============== 分子图构建 ==============

COVALENT_RADII = {
    'H': 0.31, 'C': 0.76, 'N': 0.71, 'O': 0.66, 'S': 1.05, 'F': 0.57,
    'Cl': 1.02, 'Br': 1.20, 'I': 1.39, 'P': 1.07, 'B': 0.84, 'Si': 1.11
}

class MolecularGraph:
    """构建分子图"""
    
    @staticmethod
    def from_cif(atoms, cell_transform, bond_tolerance=0.4):
        # 过滤H原子并计算笛卡尔坐标
        filtered = []
        for atom in atoms:
            if atom['element'] != 'H':
                cart = cell_transform.to_cartesian(atom['fract'])
                filtered.append({
                    'element': atom['element'],
                    'label': atom['label'],
                    'fract': atom['fract'],
                    'cart': cart
                })
        
        G = nx.Graph()
        for i, atom in enumerate(filtered):
            G.add_node(i, element=atom['element'])
        
        # 添加键（考虑PBC）
        n = len(filtered)
        for i in range(n):
            for j in range(i+1, n):
                e1, e2 = filtered[i]['element'], filtered[j]['element']
                r1 = COVALENT_RADII.get(e1, 1.5)
                r2 = COVALENT_RADII.get(e2, 1.5)
                max_dist = r1 + r2 + bond_tolerance
                
                dist = cell_transform.min_image_distance(
                    filtered[i]['fract'], filtered[j]['fract']
                )
                if dist < max_dist:
                    G.add_edge(i, j)
        
        # 返回图和原子字典（用索引作为键）
        filtered_dict = {i: atom for i, atom in enumerate(filtered)}
        return G, filtered_dict
    
    @staticmethod
    def from_mol(atoms, bonds):
        # 过滤H原子
        idx_map = {}  # 原始索引 -> 新索引
        counter = 0
        for i, atom in enumerate(atoms):
            if atom['element'] != 'H':
                idx_map[i] = counter
                counter += 1
        
        G = nx.Graph()
        filtered = {}
        new_idx = 0
        for i, atom in enumerate(atoms):
            if atom['element'] != 'H':
                G.add_node(new_idx, element=atom['element'])
                filtered[new_idx] = atom
                new_idx += 1
        
        # 添加键
        for a1, a2, btype in bonds:
            if a1 in idx_map and a2 in idx_map:
                G.add_edge(idx_map[a1], idx_map[a2])
        
        return G, filtered, idx_map


# ============== 子结构匹配 ==============

class SubstructureMatcher:
    """子图同构匹配"""
    
    @staticmethod
    def node_match(n1, n2):
        e1, e2 = n1['element'], n2['element']
        if e1 == e2:
            return True
        if {e1, e2} == {'O', 'N'}:  # O↔N替换（醛→亚胺）
            return True
        return False
    
    @staticmethod
    def find_first_match(cif_graph, mol_graph):
        """只找第一个匹配"""
        GM = isomorphism.GraphMatcher(cif_graph, mol_graph, node_match=SubstructureMatcher.node_match)
        for match in GM.subgraph_isomorphisms_iter():
            return match
        return None


# ============== 输出写入 ==============

class OutputWriter:
    """输出文件写入"""
    
    @staticmethod
    def unwrap_coordinates(match, cif_atoms, cif_graph, cell_transform):
        """展开周期性边界坐标"""
        cell_matrix = cell_transform.matrix
        cif_indices = list(match.keys())
        adjusted_fract = {}
        
        start_idx = cif_indices[0]
        adjusted_fract[start_idx] = cif_atoms[start_idx]['fract'].copy()
        
        visited = {start_idx}
        queue = deque([start_idx])
        
        while queue:
            current = queue.popleft()
            current_fract = adjusted_fract[current]
            
            for neighbor in cif_graph.neighbors(current):
                if neighbor in match and neighbor not in visited:
                    visited.add(neighbor)
                    queue.append(neighbor)
                    neighbor_fract = cif_atoms[neighbor]['fract'].copy()
                    delta = neighbor_fract - current_fract
                    delta = delta - np.round(delta)
                    adjusted_fract[neighbor] = current_fract + delta
        
        return {idx: np.dot(cell_matrix, fract) for idx, fract in adjusted_fract.items()}
    
    @staticmethod
    def filter_terminal_atoms(match, mol_atoms, mol_bonds, mol_idx_map, mode, cif_atoms):
        """过滤末端原子"""
        if mode not in ['ald', 'ami']:
            bonds = [(mol_idx_map[a1], mol_idx_map[a2], bt) for a1, a2, bt in mol_bonds 
                     if a1 in mol_idx_map and a2 in mol_idx_map]
            return match, bonds
        
        matched = set(match.values())
        mol_adj = {idx: {} for idx in matched}
        for a1, a2, bt in mol_bonds:
            if a1 in mol_idx_map and a2 in mol_idx_map:
                ma1, ma2 = mol_idx_map[a1], mol_idx_map[a2]
                if ma1 in matched and ma2 in matched:
                    mol_adj[ma1][ma2] = bt
                    mol_adj[ma2][ma1] = bt
        
        to_remove = set()
        mol_to_cif = {v: k for k, v in match.items()}
        
        if mode == 'ald':
            # 删除末端O（度为1）及其相连的C
            for mol_idx in matched:
                if mol_atoms[mol_idx]['element'] == 'O' and len(mol_adj[mol_idx]) == 1:
                    to_remove.add(mol_idx)
                    to_remove.update(mol_adj[mol_idx].keys())
        
        elif mode == 'ami':
            # 删除末端N（度为1，非三键）
            for mol_idx in matched:
                cif_elem = cif_atoms[mol_to_cif[mol_idx]]['element']
                if cif_elem == 'N' and len(mol_adj[mol_idx]) == 1:
                    neighbor = list(mol_adj[mol_idx].keys())[0]
                    if mol_adj[mol_idx][neighbor] != 3:  # 非三键（非氰基）
                        to_remove.add(mol_idx)
        
        filtered_match = {k: v for k, v in match.items() if v not in to_remove}
        filtered_bonds = [(mol_idx_map[a1], mol_idx_map[a2], bt) for a1, a2, bt in mol_bonds
                         if a1 in mol_idx_map and a2 in mol_idx_map
                         and mol_idx_map[a1] not in to_remove and mol_idx_map[a2] not in to_remove]
        
        return filtered_match, filtered_bonds
    
    @staticmethod
    def write_mol(path, match, mol_atoms, mol_bonds, cif_atoms, mol_idx_map, 
                  cif_graph, cell_transform, mode):
        """写入MOL文件"""
        filtered_match, filtered_bonds = OutputWriter.filter_terminal_atoms(
            match, mol_atoms, mol_bonds, mol_idx_map, mode, cif_atoms
        )
        
        coords = OutputWriter.unwrap_coordinates(match, cif_atoms, cif_graph, cell_transform)
        coords = {k: coords[k] for k in filtered_match.keys()}
        
        mol_indices = sorted(set(filtered_match.values()))
        mol_to_new = {old: new for new, old in enumerate(mol_indices)}
        
        remapped_bonds = [(mol_to_new[a1], mol_to_new[a2], bt) for a1, a2, bt in filtered_bonds
                         if a1 in mol_to_new and a2 in mol_to_new]
        
        output_atoms = sorted(filtered_match.items(), key=lambda x: mol_to_new[x[1]])
        
        with open(path, 'w') as f:
            f.write("Extracted from CIF\n  Generated by extract_substructure.py\n\n")
            f.write(f"{len(output_atoms):3d}{len(remapped_bonds):3d}  0  0  0  0            999 V2000\n")
            
            for cif_idx, mol_idx in output_atoms:
                coord = coords[cif_idx]
                mol_elem = mol_atoms[mol_idx]['element']
                cif_elem = cif_atoms[cif_idx]['element']
                elem = cif_elem if {mol_elem, cif_elem} == {'O', 'N'} else mol_elem
                f.write(f"{coord[0]:10.4f}{coord[1]:10.4f}{coord[2]:10.4f} {elem:<3s} 0  0  0  0  0  0  0  0  0  0  0  0\n")
            
            for a1, a2, bt in remapped_bonds:
                f.write(f"{a1+1:3d}{a2+1:3d}{bt:3d}  0  0  0  0\n")
            
            f.write("M  END\n")
        
        return len(output_atoms), len(remapped_bonds)
    
    @staticmethod
    def write_xyz(path, match, mol_atoms, mol_bonds, cif_atoms, mol_idx_map,
                  cif_graph, cell_transform, mode):
        """写入XYZ文件"""
        filtered_match, _ = OutputWriter.filter_terminal_atoms(
            match, mol_atoms, mol_bonds, mol_idx_map, mode, cif_atoms
        )
        
        coords = OutputWriter.unwrap_coordinates(match, cif_atoms, cif_graph, cell_transform)
        coords = {k: coords[k] for k in filtered_match.keys()}
        
        mol_indices = sorted(set(filtered_match.values()))
        mol_to_new = {old: new for new, old in enumerate(mol_indices)}
        output_atoms = sorted(filtered_match.items(), key=lambda x: mol_to_new[x[1]])
        
        with open(path, 'w') as f:
            f.write(f"{len(output_atoms)}\nExtracted substructure\n")
            for cif_idx, mol_idx in output_atoms:
                coord = coords[cif_idx]
                mol_elem = mol_atoms[mol_idx]['element']
                cif_elem = cif_atoms[cif_idx]['element']
                elem = cif_elem if {mol_elem, cif_elem} == {'O', 'N'} else mol_elem
                f.write(f"{elem}  {coord[0]:.6f}  {coord[1]:.6f}  {coord[2]:.6f}\n")


# ============== 主函数 ==============

def extract_substructure(cif_file, mol_file, output_file, mode):
    """
    从CIF中提取分子子结构
    
    参数:
        cif_file: CIF晶体结构文件路径
        mol_file: MOL模板文件路径  
        output_file: 输出MOL文件路径
        mode: 'ald' | 'ami' | 'dimer'
              - ald: 删除末端C=O（醛基），O→N转换
              - ami: 删除末端N（排除氰基C≡N）
              - dimer: 不删除，完整输出
    
    返回:
        n_atoms: 输出原子数
        n_bonds: 输出键数
    """
    if mode not in ['ald', 'ami', 'dimer']:
        raise ValueError(f"mode必须是 'ald', 'ami', 或 'dimer'，当前为: {mode}")
    
    print(f"模式: {mode}")
    print(f"读取CIF: {cif_file}")
    cell_params, cif_atoms = CIFParser.parse(cif_file)
    print(f"  原子数: {len(cif_atoms)}")
    
    print(f"读取MOL: {mol_file}")
    mol_atoms, mol_bonds = MOLParser.parse(mol_file)
    print(f"  原子数: {len(mol_atoms)}, 键数: {len(mol_bonds)}")
    
    print("构建分子图...")
    cell_transform = CellTransform(cell_params)
    cif_graph, cif_filtered = MolecularGraph.from_cif(cif_atoms, cell_transform)
    mol_graph, mol_filtered, mol_idx_map = MolecularGraph.from_mol(mol_atoms, mol_bonds)
    
    print("搜索匹配...")
    match = SubstructureMatcher.find_first_match(cif_graph, mol_graph)
    
    if not match:
        print("未找到匹配!")
        return 0, 0
    
    print(f"  找到匹配")
    
    output_path = Path(output_file)
    xyz_path = output_path.with_suffix('.xyz')
    
    n_atoms, n_bonds = OutputWriter.write_mol(
        output_path, match, mol_filtered, mol_bonds,
        cif_filtered, mol_idx_map, cif_graph, cell_transform, mode
    )
    OutputWriter.write_xyz(
        xyz_path, match, mol_filtered, mol_bonds,
        cif_filtered, mol_idx_map, cif_graph, cell_transform, mode
    )
    
    print(f"\n输出: {output_path}")
    print(f"      {xyz_path}")
    print(f"原子数: {n_atoms}, 键数: {n_bonds}")
    
    if mode in ['ald', 'ami']:
        removed = len(match) - n_atoms
        print(f"删除末端原子: {removed}")
    
    return n_atoms, n_bonds


# ============== 使用示例 ==============
if __name__ == "__main__":
    # 示例1: 切ald单元
    # extract_substructure("ald_6_ami_14.cif", "ald-6.mol", "ald6_out.mol", "ald")
    
    # 示例2: 切ami单元  
    # extract_substructure("ald_1_ami_2.cif", "ami-2.mol", "ami2_out.mol", "ami")
    
    # 示例3: 切dimer
    # extract_substructure("ald_1_ami_2.cif", "dimer_ald-1_ami-2.mol", "dimer_out.mol", "dimer")
    
    pass

import os
cifnam='opted_cifs/dimer_ald-10_ami-2.cif'
ald_id='10'
ami_id='2'
if not os.path.exists('cuted_mols'):
    os.makedirs('cuted_mols')
ald_nam=f'ald-result/ald-{ald_id}.mol'
ami_nam=f'ami-result/ami-{ami_id}.mol'
dimer_nam=f'individual_dimers/dimer_ald-{ald_id}_ami-{ami_id}.mol'
out_ald=f'cuted_mols/ald_from_ald-{ald_id}_ami-{ami_id}.mol'
out_ami=f'cuted_mols/ami_from_ald-{ald_id}_ami-{ami_id}.mol'
out_dimer=f'cuted_mols/dimer_from_ald-{ald_id}_ami-{ami_id}.mol'
print('##'*200)
extract_substructure(cifnam, ald_nam, out_ald, 'ald')
extract_substructure(cifnam, ami_nam, out_ami, 'ami')
extract_substructure(cifnam, dimer_nam, out_dimer, 'dimer')

