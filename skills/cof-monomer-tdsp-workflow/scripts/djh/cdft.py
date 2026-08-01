#!/usr/bin/env python3
import os,glob,subprocess,sys
from pathlib import Path
import numpy as np

def runcdft(fchknam):
    '''
    Get the conceptual DFT descriptors 
    fchk file, N-1 , N+1 fchk files are requiredd
    More on http://sobereva.com/484
    This dunction cannot run parallelly (due to output file)
    The descriptor list (eV):
    condensed Fukui functions(plus, minus, 0):  cfuk_plus,cfuk_minus,cfuk_0
    condensed dual descriptors: cdd
    condensed local electrophilicity/nucleophilicity: cele_ph,cnuc_ph
    condensed local softnesses (Hartree*e, plus,minus,0): c_soft_plus,c_soft_minus,c_soft_0
    Vertical IP: vip
    Vertical IP: vea,mull_ele_neg,hardness,softness
    '''
    pfchk=fchknam[:-5]+'+1.fchk'
    mfchk=fchknam[:-5]+'-1.fchk'
    outnam=fchknam[:-5]+'_CDFT.txt'
    if outnam in next(os.walk('.'))[-1]:
        return

    skill_root = Path(__file__).resolve().parents[3] / 'multiwfn-mac'
    helper_script = skill_root / 'scripts' / 'calc_cdft.py'
    multiwfn_bin = skill_root / 'multiwfn' / 'multiwfn'
    if not helper_script.exists():
        raise FileNotFoundError(f'Multiwfn CDFT helper not found: {helper_script}')

    cmd = [sys.executable, str(helper_script), fchknam, pfchk, mfchk, '--output', outnam]
    if multiwfn_bin.exists():
        cmd.extend(['--multiwfn', str(multiwfn_bin)])
    subprocess.run(cmd, check=True)

# run CDFT
'''
alllog=glob.glob('*.log')
allfchk=[i.split('.')[0]+'.fchk' for i in alllog]
print(allfchk)
for fchknam in allfchk:
    runcdft(fchknam)

'''
def read_CDFT(fchknam):
    c=open(fchknam[:-5]+'_CDFT.txt')
    cdft=c.readlines()
    c.close()
    hirsh_char_0=[]
    hirsh_char_p=[]
    hirsh_char_m=[]

    cfuk_plus=[]
    cfuk_minus=[]
    cfuk_0=[]
    cdd=[]
    
    cele_ph=[]
    cnuc_ph=[]
    
    c_soft_plus=[]
    c_soft_minus=[]
    c_soft_0=[]

    vip=None
    vea=None
    mull_ele_neg=None
    hardness=None
    softness=None

    readfc=0
    readen=0
    readsoft=0
    for i in cdft:
        if readfc:
            if '(' not in i:
                readfc-=1
            else:
                i=i.split( )
                hirsh_char_0.append(i[-7])
                hirsh_char_p.append(i[-6])
                hirsh_char_m.append(i[-5])
                cfuk_minus.append(i[-4])
                cfuk_plus.append(i[-3])
                cfuk_0.append(i[-2])
                cdd.append(i[-1])
        if 'f-       f+       f0      CDD' in i:
            readfc+=1
        if readen:
            if '(' not in i:
                readen-=1
            else:
                i=i.split( )
                cele_ph.append(i[-2])
                cnuc_ph.append(i[-1])
        if 'Atom              Electrophilicity          Nucleophilicity' in i:
            readen+=1
        if readsoft:
            if '(' not in i:
                readsoft-=1
            else:
                i=i.split( )
                c_soft_plus.append(i[-4])
                c_soft_minus.append(i[-5])
                c_soft_0.append(i[-3])
        if 's-          s+          s0        s+/s-       s-/s+' in i:
            readsoft+=1
        if 'vertical IP:' in i or 'First vertical IP:' in i:
            vip=np.float64(i.split( )[-2])
        if 'vertical EA:' in i or 'First vertical EA:' in i:
            vea=np.float64(i.split( )[-2])
        if 'Mulliken electronegativity' in i:
            mull_ele_neg=np.float64(i.split( )[-2])
        if 'Hardness' in i:
            hardness=np.float64(i.split( )[-2])
        if 'Softness:' in i:
            softness=np.float64(i.split( )[-2])
    
    hirsh_char_0=np.array(hirsh_char_0,dtype='float64')
    hirsh_char_p=np.array(hirsh_char_p,dtype='float64')
    hirsh_char_m=np.array(hirsh_char_m,dtype='float64')

    cfuk_plus=np.array(cfuk_plus,dtype='float64')
    cfuk_minus=np.array(cfuk_minus,dtype='float64')
    cfuk_0=np.array(cfuk_0,dtype='float64')
    cdd=np.array(cdd,dtype='float64')
    
    cele_ph=np.array(cele_ph,dtype='float64')
    cnuc_ph=np.array(cnuc_ph,dtype='float64')
    
    c_soft_plus=np.array(c_soft_plus,dtype='float64')
    c_soft_minus=np.array(c_soft_minus,dtype='float64')
    c_soft_0=np.array(c_soft_0,dtype='float64')

    missing=[]
    if vip is None:
        missing.append('vip')
    if vea is None:
        missing.append('vea')
    if mull_ele_neg is None:
        missing.append('mull_ele_neg')
    if hardness is None:
        missing.append('hardness')
    if softness is None:
        missing.append('softness')
    if missing:
        raise ValueError(f'Missing scalar CDFT fields in {fchknam[:-5]}_CDFT.txt: {", ".join(missing)}')
                                                   
    return hirsh_char_0,hirsh_char_p,hirsh_char_m,cfuk_plus,cfuk_minus,cfuk_0,cdd,cele_ph,cnuc_ph,c_soft_plus,c_soft_minus,c_soft_0,vip,vea,mull_ele_neg,hardness,softness



