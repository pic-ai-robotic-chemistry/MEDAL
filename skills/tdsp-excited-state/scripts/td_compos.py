from rdkit import Chem
from rdkit.Chem import Draw
from rdkit.Chem import rdDepictor
#from PIL import Image, ImageDraw, ImageFont

#mol_path = "./dimer_from_ald-4_ami-11_addH.mol"
def cut_dimer(mol_path):
    # ---------- 1) Read molecule ----------
    m = Chem.MolFromMolFile(mol_path, sanitize=True, removeHs=False)
    if m is None:
        raise ValueError("无法读取 mol 文件。请确认文件有效。")

    rdDepictor.Compute2DCoords(m)

    # ---------- 2) Find imine bond C=N (double bond), prefer carbon bearing 1 H ----------
    candidates = []
    for b in m.GetBonds():
        if b.GetBondType() != Chem.BondType.DOUBLE:
            continue
        a1, a2 = b.GetBeginAtom(), b.GetEndAtom()
        if {a1.GetSymbol(), a2.GetSymbol()} != {"C", "N"}:
            continue

        c_atom = a1 if a1.GetSymbol() == "C" else a2
        n_atom = a2 if c_atom is a1 else a1
        c_h = c_atom.GetTotalNumHs()
        candidates.append((b.GetIdx(), c_atom.GetIdx(), n_atom.GetIdx(), c_h))

    imine = next((c for c in candidates if c[3] == 1), None) or (candidates[0] if candidates else None)
    if imine is None:
        raise ValueError("未找到符合条件的 C=N 亚胺键（双键且 C 端为 CH）。")

    bond_idx, c_idx, n_idx, c_h = imine

    # ---------- 3) Split into two units by breaking the imine bond ----------
    num_original_atoms = m.GetNumAtoms()

    # Add atom map numbers so we can identify fragments reliably after fragmentation
    m_map = Chem.Mol(m)
    for a in m_map.GetAtoms():
        a.SetAtomMapNum(a.GetIdx() + 1)  # 1-based for readability

    frag_map = Chem.FragmentOnBonds(m_map, [bond_idx], addDummies=True, dummyLabels=[(0, 0)])
    rdDepictor.Compute2DCoords(frag_map)

    # Fragments as atom-index tuples on the fragmented molecule (0-based, includes dummies)
    frag_idx_tuples = Chem.GetMolFrags(frag_map, asMols=False, sanitizeFrags=True)

    # Identify which tuple contains original C / N (by atom-map number)
    def tuple_contains_mapnum(frag_mol, idx_tuple, mapnum):
        for i in idx_tuple:
            if frag_mol.GetAtomWithIdx(i).GetAtomMapNum() == mapnum:
                return True
        return False

    c_mapnum = c_idx + 1
    n_mapnum = n_idx + 1

    n_tuple = next(t for t in frag_idx_tuples if tuple_contains_mapnum(frag_map, t, n_mapnum))
    c_tuple = next(t for t in frag_idx_tuples if tuple_contains_mapnum(frag_map, t, c_mapnum))

    # Report original atom indices (exclude dummy atoms, which have mapnum=0)
    amine_atoms_1based = sorted([
        frag_map.GetAtomWithIdx(i).GetAtomMapNum()
        for i in n_tuple
        if frag_map.GetAtomWithIdx(i).GetAtomMapNum() != 0
    ])
    aldehyde_atoms_1based = sorted([
        frag_map.GetAtomWithIdx(i).GetAtomMapNum()
        for i in c_tuple
        if frag_map.GetAtomWithIdx(i).GetAtomMapNum() != 0
    ])

    # Get fragment Mol objects for drawing
    frag_mols_map = Chem.GetMolFrags(frag_map, asMols=True, sanitizeFrags=True)

    def mol_contains_mapnum(fm, mapnum):
        return any(a.GetAtomMapNum() == mapnum for a in fm.GetAtoms())

    amine_mol = next(fm for fm in frag_mols_map if mol_contains_mapnum(fm, n_mapnum))
    aldehyde_mol = next(fm for fm in frag_mols_map if mol_contains_mapnum(fm, c_mapnum))

    # Clear atom-map numbers for nicer drawings
    for fm in (amine_mol, aldehyde_mol):
        for a in fm.GetAtoms():
            a.SetAtomMapNum(0)
        rdDepictor.Compute2DCoords(fm)

    '''
    # ---------- 5) Print results ----------
    print("=== 识别到的亚胺键 (C=N) ===")
    print(f"Bond index (RDKit, 0-based): {bond_idx}")
    print(f"CH 侧碳原子: Atom {c_idx+1} (1-based), total H on carbon = {c_h}")
    print(f"N 原子: Atom {n_idx+1} (1-based)")

    print("\n=== 氨基单元 (N侧, 含N) 原子编号(1-based) ===")
    print(amine_atoms_1based)

    print("\n=== 醛基单元 (CH侧, 含CH) 原子编号(1-based) ===")
    print(aldehyde_atoms_1based)
    '''
    return [i-1 for i in aldehyde_atoms_1based],[i-1 for i in amine_atoms_1based] # aldehyde_atoms_1based,amine_atoms_1based

import re
import math
from collections import deque
from typing import Optional
import pandas as pd

_LINE_RE = re.compile(
    r"^\s*(\d+)\s*\(\s*([A-Za-z]{1,3})\s*\)\s*"
    r"Hole:\s*([+\-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[Ee][+\-]?\d+)?)\s*%\s*"
    r"Electron:\s*([+\-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[Ee][+\-]?\d+)?)\s*%\s*"
    r"(?:Overlap:\s*([+\-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[Ee][+\-]?\d+)?)\s*%\s*)?"
    r"(?:Diff\.\s*:\s*([+\-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[Ee][+\-]?\d+)?)\s*%\s*)?$"
)

def _to_pct_or_nan(x: Optional[str], *, abs_limit: float = 1e6) -> float:
    """
    解析百分比字符串，允许负值。
    - 解析失败 / 非有限值 -> NaN
    - |值| 过大（默认 > 1e6）认为异常 -> NaN
    """
    if x is None:
        return float("nan")
    try:
        v = float(x)
    except Exception:
        return float("nan")

    if not math.isfinite(v):
        return float("nan")

    if abs(v) > abs_limit:
        return float("nan")

    return v


def read_atom_hole_electron_contributions(
    txt_path: str,
    occurrence: str = "last",
    abs_limit: float = 1e6,
) -> pd.DataFrame:
    """
    读取 txt 中每个原子的 hole/electron 贡献百分比（允许负值）。

    参数
    - txt_path: txt 文件路径
    - occurrence: "first" 或 "last"，若同名标题出现多次默认取最后一次
    - abs_limit: 绝对值阈值，超过认为异常 -> NaN（默认 1e6）

    返回 DataFrame:
      atom_index (1-based), element, hole_pct, electron_pct, overlap_pct, diff_pct
    """
    header = "Contribution of each atom to hole and electron:"

    with open(txt_path, "r", encoding="utf-8", errors="replace") as f:
        lines = f.readlines()

    header_pos = [i for i, line in enumerate(lines) if header in line]
    if not header_pos:
        raise ValueError(f'未找到标题行: "{header}"')

    start_i = header_pos[0] if occurrence == "first" else header_pos[-1]

    rows = []
    started = False

    for line in lines[start_i + 1:]:
        m = _LINE_RE.match(line)
        if m:
            started = True
            atom_idx = int(m.group(1))
            elem = m.group(2).strip()

            hole = _to_pct_or_nan(m.group(3), abs_limit=abs_limit)
            elec = _to_pct_or_nan(m.group(4), abs_limit=abs_limit)
            overlap = _to_pct_or_nan(m.group(5), abs_limit=abs_limit)
            diff = _to_pct_or_nan(m.group(6), abs_limit=abs_limit)

            rows.append({
                "atom_index": atom_idx,
                "element": elem,
                "hole_pct": hole,
                "electron_pct": elec,
                "overlap_pct": overlap,
                "diff_pct": diff,
            })
        else:
            if started:
                break

    if not rows:
        raise ValueError("找到了标题行，但其后没有成功解析到任何原子贡献行（格式可能不同）。")

    return pd.DataFrame(rows).sort_values("atom_index").reset_index(drop=True)


# 用法：
print('pfxnam,ald_hole_pct,ami_hole_pct,ald_electron_pct,ami_electron_pct')
import os,glob
allmol=glob.glob('*.mol')
for mol in allmol:
    pfxnam=mol.split('.')[0]
    #pfxnam='dimer_from_ald-4_ami-2_addH'
    print(pfxnam,end=',')

    mol_path=f'{pfxnam}.mol'
    txt_path=f'{pfxnam}.he.txt'
    df = read_atom_hole_electron_contributions(txt_path, abs_limit=1e6)
    # print(df)

    hole_pct, electron_pct = list(df['hole_pct']), list(df['electron_pct'])
    #a = [1, 2, 3]
    ald_set,ami_set=cut_dimer(mol_path)
    # To select multiple elements by indices in a list 'hole_pct', use a list comprehension or operator.itemgetter:
    from operator import itemgetter
    ald_hole_pct = list(itemgetter(*ald_set)(hole_pct))
    ami_hole_pct = list(itemgetter(*ami_set)(hole_pct))
    ald_electron_pct = list(itemgetter(*ald_set)(electron_pct))
    ami_electron_pct = list(itemgetter(*ami_set)(electron_pct))
    print(round(sum(ald_hole_pct),2),round(sum(ami_hole_pct),2),round(sum(ald_electron_pct),2),round(sum(ami_electron_pct),2),sep=',')


