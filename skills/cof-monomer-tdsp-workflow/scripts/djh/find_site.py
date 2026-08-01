"""
简化版对位碳原子查找模块

用法示例：
    from find_para_carbons_simple import get_para_carbons
    
    # 直接返回列表
    para_list = get_para_carbons('your_file.gjf')
    print(para_list)  # 输出: [34, 23, 45, 56]
"""

import numpy as np
from scipy.spatial.distance import cdist
import networkx as nx

def get_para_carbons(gjf_file):
    """
    从gjf文件获取四个对位碳原子序号
    
    参数:
        gjf_file (str): gjf文件路径
    
    返回:
        list: 包含4个整数的列表，代表对位碳原子的索引
    """
    # 读取gjf文件
    atoms, coords = _read_gjf(gjf_file)
    
    # 计算中心
    center = np.mean(coords, axis=0)
    
    # 构建连接图并找到苯环
    G = _build_graph(atoms, coords)
    rings = _find_rings(G, atoms)
    
    # 找到最远的4个苯环
    furthest = _get_furthest_rings(rings, coords, center)
    
    # 获取对位碳原子
    para_carbons = []
    for ring in furthest:
        connecting = _find_connector(ring, G, atoms)
        if connecting is not None:
            para = _find_para(ring, connecting)
            if para is not None:
                para_carbons.append(para)
    
    return para_carbons

def _read_gjf(filename):
    """读取gjf文件"""
    atoms, coords = [], []
    with open(filename, 'r') as f:
        lines = f.readlines()
    
    start = next(i for i, line in enumerate(lines) if line.split( ) == ['0', '1']) + 1
    
    for line in lines[start:]:
        if not line.strip():
            break
        parts = line.split()
        if len(parts) >= 4:
            atoms.append(parts[0])
            coords.append([float(parts[1]), float(parts[2]), float(parts[3])])
    
    return atoms, np.array(coords)

def _build_graph(atoms, coords, threshold=1.7):
    """构建连接图"""
    G = nx.Graph()
    for i in range(len(atoms)):
        G.add_node(i)
    
    distances = cdist(coords, coords)
    for i in range(len(atoms)):
        for j in range(i+1, len(atoms)):
            if distances[i][j] < threshold and not (atoms[i] == 'H' and atoms[j] == 'H'):
                G.add_edge(i, j)
    
    return G

def _find_rings(G, atoms):
    """找到所有苯环"""
    cycles = nx.cycle_basis(G)
    return [c for c in cycles if len(c) == 6 and all(atoms[i] == 'C' for i in c)]

def _get_furthest_rings(rings, coords, center):
    """获取最远的4个苯环"""
    distances = [(r, np.linalg.norm(np.mean(coords[r], axis=0) - center)) for r in rings]
    distances.sort(key=lambda x: x[1], reverse=True)
    return [r for r, _ in distances[:4]]

def _find_connector(ring, G, atoms):
    """找到连接碳原子"""
    ring_set = set(ring)
    for c in ring:
        if any(n not in ring_set and atoms[n] != 'H' for n in G.neighbors(c)):
            return c
    return None

def _find_para(ring, connector):
    """找到对位碳原子"""
    ring_list = list(ring)
    idx = ring_list.index(connector)
    return ring_list[(idx + 3) % 6]

# 命令行使用
if __name__ == "__main__":
    import sys
    gjf_file = sys.argv[1] if len(sys.argv) > 1 else print('No gjf file!')
    print(get_para_carbons(gjf_file))
