#!/usr/bin/env python
# coding: utf-8

# In[1]:


#from os import system as ss
import os,sys,re,glob
import shutil
from pathlib import Path
import numpy as np
from subprocess import getstatusoutput as gs
import scipy
import numpy as np
# This is the library for some important functions


def _resolve_mwfn():
    """Resolve the Multiwfn executable for the current platform."""
    if sys.platform == 'darwin':
        workspace_multiwfn = (
            Path.home()
            / '.openclaw'
            / 'workspace'
            / 'skills'
            / 'multiwfn-mac'
            / 'multiwfn'
            / 'multiwfn'
        )
        if workspace_multiwfn.exists():
            return str(workspace_multiwfn)
        fallback = shutil.which('multiwfn') or shutil.which('Multiwfn')
        if fallback:
            return fallback
        raise FileNotFoundError(
            f'Multiwfn executable not found for macOS. Expected: {workspace_multiwfn}'
        )
    if os.name == 'posix':
        return 'Multiwfn'
    return 'Multiwfn.exe'


mwfn = _resolve_mwfn()
    

'''
windows下使用
进入Windows的“高级系统设置”- “高级”- “环境变量”，将Multiwfn.exe所在目录加入到Path变量里，
并且新建一个Multiwfnpath变量，将变量值设为settings.ini的所在目录。
之后在cmd里，无论当前处在哪个目录，也都可以通过输入Multiwfn命令启动了。
但是尽量不要windows下使用!
'''


# In[2]:


class logfile():
    def __init__(self,lognam):
        # 名称
        self.lognam=lognam
        self.pfxnam=lognam.split('.')[0]
        
        # 电荷，自旋，坐标，元素，基态能量，原子间距
        self.charge,self.multi,self.allcoords,self.atomtypes,self.ground_state_energies=self.read_allframes_fromlog()
        self.current_xyz=self.allcoords[-1]
        #self.current_ground_state_energy=self.ground_state_energies[-1]
        self.dis_mat=np.linalg.norm(self.current_xyz[:,None,:]-self.current_xyz[None,:,:],axis=-1)

    def read_allframes_fromlog(self):
        # This for reading xyz coordinates and charge/multi/atom types/energies
        atomtypes=[]
        with open(self.lognam) as log:
            lg=log.readlines()
            c=-4
            read=False
            frameid=-1
            allcoords=[]
            ground_state_energies=[]
            for n,i in enumerate(lg):            
                if 'SCF Done' in i:
                    ground_state_energies.append(float(i.split( )[4]))
                if 'Multiplicity' in i:
                    i=i.split('Multiplicity')
                    charge=int(i[0].split('=')[-1].split( )[-1])
                    multi=int(i[-1].split('=')[-1].split( )[-1])
                if 'Coordinates (Angstroms)' in i:
                    c=n
                if n==c+3:
                    read=True
                    coords=[]
                if read:
                    if '----' in i:
                        read=False
                        coords=np.array(coords,dtype='float').reshape(-1,3)
                        allcoords.append(coords)
                    else:
                        i=i.split( )
                        coords+=i[-3:]
                        atomtypes.append(i[1])
        atomtypes=atomtypes[:len(allcoords[0])]
        return charge,multi,allcoords,atomtypes,ground_state_energies

    def dipole(self):
        read=False
        with open(self.lognam) as log:
            lg=log.readlines()
            dip_xyz=[]
            for i in lg:
                if read:
                    if len(dip_xyz)==0:
                        i=i.split( )
                        dip_xyz=np.array([i[1],i[3],i[5]],dtype=float)
                    else:
                        break
                if 'Dipole moment (field-independent basis, Debye):' in i:
                    read=True
        return dip_xyz
        
# In[3]:

class fchkfile():
    def __init__(self,fchknam):
        self.fchknam=fchknam
        self.pfxnam=fchknam.split('.fch')[0]
        self.atomtypes,self.current_xyz,self.charge,self.multi,self.current_ground_state_energy=self.fchk_xyz()
        self.electron_num,self.electron_alpha_num,self.electron_beta_num,self.orbital_alpha_energies,self.orbital_beta_energies=self.orbital_energies()
        self.homo=(self.orbital_alpha_energies[self.electron_alpha_num-1],self.orbital_beta_energies[self.electron_beta_num-1])
        self.lumo=(self.orbital_alpha_energies[self.electron_alpha_num],self.orbital_beta_energies[self.electron_beta_num])
        self.gap=(self.orbital_alpha_energies[self.electron_alpha_num]-self.orbital_alpha_energies[self.electron_alpha_num-1],self.orbital_beta_energies[self.electron_beta_num]-self.orbital_beta_energies[self.electron_beta_num-1])
        self.dismat=scipy.spatial.distance_matrix(self.current_xyz,self.current_xyz)

    
    def fchk_xyz(self):
        scf_energy=np.NAN # fchk文件中可能没有scf能量结果
        with open(self.fchknam) as f:
            readatom=False
            readcoord=False
            allelements=[]
            allxyzs=[]
            for n,i in enumerate(f.readlines()):  
                if 'Multiplicity' in i:
                    multi=int(i.split( )[-1])
                if 'Charge ' in i:
                    charge=int(i.split( )[-1])
                if readatom and 'N=' in i:
                    readatom=False
                if readatom:
                    allelements+=i.split( )
                if 'Atomic numbers' in i:
                    readatom=True
                if readcoord:
                    if '  I' in i or '=' in i: # 2024.01.16
                        readcoord=False
                if readcoord:
                    allxyzs+=i.split( )
                if 'cartesian coordinates' in i:
                    readcoord=True
                if 'SCF Energy' in i:
                    i=i.split( )
                    scf_energy=float(i[-1])


        #allelements=[elements[int(j)] for j in allelements]
        allxyzs=np.array(allxyzs,dtype='float64').reshape((-1,3))/1.8897259886 # To Angstrong

        return allelements,allxyzs,charge,multi,scf_energy
    def orbital_energies(self):
        orbital_alpha_energies=[]
        orbital_beta_energies=[]
        reada=0
        readb=0
        with open(self.fchknam) as f:
            for i in f.readlines():
                if 'Number of electrons' in i:
                    electron_num=int(i.split( )[-1])
                if 'Number of alpha electrons' in i:
                    electron_alpha_num=int(i.split( )[-1])
                if 'Number of beta electrons' in i:
                    electron_beta_num=int(i.split( )[-1])
                if reada:
                    if '.' in i:
                        i=i.split( )
                        orbital_alpha_energies+=i
                    else:
                        reada=0
                if 'Alpha Orbital Energies' in i:
                    reada+=1
                if readb:
                    if '.' in i:
                        i=i.split( )
                        orbital_beta_energies+=i
                    else:
                        readb=0
                        break
                if 'Beta Orbital Energies' in i:
                    readb+=1
            if orbital_beta_energies==[]:
                orbital_beta_energies=orbital_alpha_energies
        orbital_alpha_energies,orbital_beta_energies=np.array(orbital_alpha_energies,dtype=float),np.array(orbital_beta_energies,dtype=float)
        return electron_num,electron_alpha_num,electron_beta_num,orbital_alpha_energies,orbital_beta_energies



# 用Multiwfn波函数对fchk做分析

class Mwfn():
    def __init__(self,input_file,vip=0):
        self.pfxnam=input_file.split('.')[0]
        self.fchknam=self.pfxnam+'.fchk'
        self.lognam=self.pfxnam+'.log'
        self.input_file=input_file


    def PES_curve(self,fwhm,shift,start=0.0,end=21.22):
        '''
        Draw the PES. A shift ( VIP add HOMO energy,in eV) must be given.
        use .fchk as input_file
        '''
        # start,end and full width at half maximum (in eV) should also be given.
        step=0.5
        curv=str(start)+','+str(end)+','+str(step)
        randnum=str(np.random.randint(1000000))
        comtxt=open(randnum+'com','w')
        comtxt.write('10\n12\n4\n'+curv+'\n6\n'+str(fwhm)+'\n3\n'+str(shift)+'\n-1\n0\n-10\nq')
        comtxt.close()
        
        os.system(mwfn+' '+self.input_file+' < '+randnum+'com'+' > tem'+randnum)
        # Column 1: Shifted binding energy (eV)
        # Column 2: PES strength              
        os.rename('PES_curve.txt',self.input_file[:-5]+randnum+'_PES_curve.txt')
        os.remove('PES_line.txt')
        curve_line=np.loadtxt(self.input_file[:-5]+randnum+'_PES_curve.txt')[:,-1]
        os.remove(self.input_file[:-5]+randnum+'_PES_curve.txt')
        os.remove('tem'+randnum)
        os.remove(randnum+'com')
        return curve_line

    def get_mole_polar(self):
        '''
        计算分子的极化率
        需要一个做完频率分析的log文件作为输入
        '''
        randnum=str(np.random.randint(1000000))
        comtxt=open(randnum+'com','w')
        comtxt.write('24\n1\n2\n0\n0\nq')
        comtxt.close()
        os.system(f'"{mwfn}" "{self.input_file}" < {randnum}com > tem{randnum}')
        result=open('tem'+randnum)
        for i in result.readlines():
            if 'Isotropic average polarizability: ' in i:
                polar=float(i.split( )[-1])
        result.close()
        os.remove('tem'+randnum)
        os.remove(randnum+'com')
        return polar

    def primary_mayer_bond_order(self):
        """
        Calculate the mayer bond order 
        Return the bond order matrix
        Only > 0.05 will be considered
        """
        randnum=str(np.random.randint(1000000))
        comtxt=open(randnum+'com','w')
        comtxt.write('9\n1\ny\n0\nq') # 换成给Multiwfn的命令
        comtxt.close()
        os.system(mwfn+' '+self.input_file+' < '+randnum+'com'+' > tem'+randnum)

        bdo=open('tem'+randnum)
        allinfo=[]
        totalval=[]
        freeval=[]
        read=0
        read2=0
        for b in bdo.readlines():
            if 'Atoms:' in b:
                atomnum=int(b.split( )[1][:-1])
            if read==1:
                if '#' in b:
                    b1=b.split('(')
                    a1=b1[0].split( )[-1]
                    a2=b1[1].split( )[-1]#.split(')')[0]
                    bd=b.split( )[-1]
                    allinfo.append(a1+' '+a2+' '+bd)
                else:
                    read+=1
            if 'Bond orders with absolute value' in b:
                read+=1
            if read2:
                if 'Atom' in b:
                    b=b.split( )
                    tval=float(b[-2])
                    fval=float(b[-1])
                    totalval.append(tval)
                    freeval.append(fval)
            if 'Total valences and free valences defined by Mayer:' in b:
                read2+=1
        bdo.close()
        bondmat=np.zeros((atomnum,atomnum))
        for i in allinfo:
            i=i.split( )
            bondmat[int(i[0])-1][int(i[1])-1]=i[-1]
        bondmat+=bondmat.T
        totalval=np.array(totalval)
        freeval=np.array(freeval)
        os.remove('tem'+randnum)
        os.remove(randnum+'com')
        return bondmat,totalval,freeval

    def get_interatomic_conn(self):
        '''
        Get the interatomic connectivity matrix
        More details are available on: chapter 3.100.9 in Multiwfn 3.8(dev) manual
        support fchk files only now
        '''
        randnum=str(np.random.randint(1000000))
        comtxt=open(randnum+'com','w')
        comtxt.write('100\n9\n0.05\nn\n0\nq') # 换成给Multiwfn的命令
        comtxt.close()
        os.system(mwfn+' '+self.input_file+' < '+randnum+'com'+' > tem'+randnum)
        #result=open('tem'+randnum)

        fchk=open(self.input_file)
        f=fchk.readlines()
        for i in f:
            if 'Atomic numbers' in i:
                natom=int(i.split( )[-1])
        fchk.close()
        inter_atom_conn=np.zeros((natom,natom))
        with open('tem'+randnum) as bnd:
            for i in bnd.readlines():
                if '---' in i:
                    i=i.split( )
                    val=float(i[4])
                    atom1=int(''.join([x for x in i[0] if x.isdigit() ]))
                    atom2=int(''.join([x for x in i[2] if x.isdigit() ]))
                    inter_atom_conn[atom1-1][atom2-1]=val
        inter_atom_conn+=inter_atom_conn.T
        #result.close()
        os.remove('tem'+randnum)
        os.remove(randnum+'com')
        return inter_atom_conn

    def mpp(self):
        '''
        计算 molecular planarity parameter(MPP)/span of deviation from plane(SDP)
        '''
        com='\'100 21 MPP a n q 0 q\''
        com=com.replace(' ','\n')
        os.system('echo -e '+com+' | Multiwfn '+self.input_file+' > '+self.input_file.split('.')[0]+'.mpp')
        out=open(self.input_file.split('.')[0]+'.mpp')
        for i in out:
            if 'Molecular planarity parameter' in i:
                mpp=float(i.split( )[-2])
            if 'Span of deviation from plane' in i:
                sdp=float(i.split( )[-2])
        return mpp,sdp

    def get_hirsh_char(self):
        '''
        计算hirshfeld电荷
        '''
        randnum=str(np.random.randint(1000000))
        comtxt=open(randnum+'com','w')
        comtxt.write('7\n1\n1\nn\n0\nq') # 换成给Multiwfn的命令
        comtxt.close()
        os.system(mwfn+' '+self.input_file+' < '+randnum+'com'+' > tem'+randnum)
        #result=open('tem'+randnum)

        char=open('tem'+randnum)
        chg=char.readlines()
        char.close()
        allcha=[]
        for c in chg:
            if 'Atom' in c and '):' in c:
                c=c.split( )
                allcha.append(c[-1])
        allcha=np.array(allcha,dtype='float64')
        #result.close()
        os.remove('tem'+randnum)
        os.remove(randnum+'com')
        return allcha

    def read_GIPF(self):
        '''
        require a fchk file for input
        Read GIPF desciptors, more on http://sobereva.com/159
        '''
        outnam=self.input_file.split('.')[0]+'.gipf'
        if outnam in glob.glob('*.*'):
            pass
        else:
            os.system('echo -e \'12\n0\n-1\n-1\nq\' | Multiwfn '+self.input_file+'> '+outnam)
        outn=open(outnam)
        out=outn.readlines()
        outn.close()
        for o in out:
            if 'Volume:' in o:
                volume=np.float64(o.split( )[1])
            if 'Estimated density' in o:
                density=np.float64(o.split( )[-2])
            if 'Minimal value:' in o:
                o=o.split( )
                min_val,max_val=np.float64(o[2]),np.float64(o[-2])
            if 'Overall surface area: ' in o:
                o=o.split( )
                overall_surf_area=np.float64(o[3])
            if 'Positive surface area:' in o:
                o=o.split( )
                pos_surf_area=np.float64(o[3])
            if 'Negative surface area:' in o:
                o=o.split( )
                neg_surf_area=np.float64(o[3])
            if 'Overall average value: ' in o:
                o=o.split( )
                overall_aver_area=np.float64(o[3])
            if 'Positive average value:' in o:
                o=o.split( )
                pos_aver_area=np.float64(o[3])
            if 'Negative average value:' in o:
                o=o.split( )
                neg_aver_area=np.float64(o[3])
            if 'Overall variance' in o:
                o=o.split( )
                overall_var=np.float64(o[3])
            if 'Positive variance:' in o:
                o=o.split( )
                pos_var=np.float64(o[2])
            if 'Negative variance:' in o:
                o=o.split( )
                neg_var=np.float64(o[2])
            if 'Balance of charges (nu):' in o:
                o=o.split( )
                bal_char=np.float64(o[-1])
            if 'Internal charge separation' in o:
                o=o.split( )
                inter_char_sep=np.float64(o[4])     
            if 'Molecular polarity index' in o:
                o=o.split( )
                mole_polar_index=np.float64(o[4])
            if 'Nonpolar surface area' in o:
                o=o.split( )
                nonpol_surf_area=np.float64(o[7])
            if 'Polar surface area' in o:
                o=o.split( )
                pol_surf_area=np.float64(o[7])
#        ss('rm '+outnam)
        return volume,density,min_val,max_val,overall_surf_area,pos_surf_area,neg_surf_area,overall_aver_area,pos_aver_area,neg_aver_area,overall_var,pos_var,neg_var,bal_char,inter_char_sep,mole_polar_index,nonpol_surf_area,pol_surf_area

   

# In[ ]:





# In[ ]:





# In[ ]:





# In[ ]:





# In[ ]:


# %%
elements=[ 'X','H' ,'He','Li','Be','B' ,  'C' ,'N' ,'O' ,'F' ,'Ne',
           'Na','Mg','Al','Si','P' ,  'S' ,'Cl','Ar','K' ,'Ca',
           'Sc','Ti','V' ,'Cr','Mn',  'Fe','Co','Ni','Cu','Zn',
           'Ga','Ge','As','Se','Br',  'Kr','Rb','Sr','Y' ,'Zr',
           'Nb','Mo','Tc','Ru','Rh',  'Pd','Ag','Cd','In','Sn',
           'Sb','Te','I' ,'Xe','Cs',  'Ba','La','Ce','Pr','Nd',
           'Pm','Sm','Eu','Gd','Tb',  'Dy','Ho','Er','Tm','Yb',
           'Lu','Hf','Ta','W' ,'Re',  'Os','Ir','Pt','Au','Hg',
           'Tl','Pb','Bi','Po','At',  'Rn','Fr','Ra','Ac','Th',
           'Pa','U' ,'Np','Pu','Am',  'Cm','Bk','Cf','Es','Fm',
           'Md','No','Lr','Rf','Db',  'Sg','Bh','Hs','Mt','Ds',
           'Rg', 'Uub','Uut','Uuq','Uup',  'Uuh']

non_metal_elements=['H','He','B','C','N','O','F','Ne','Si','P','S','Cl','Ar','As','Se','Br','Kr','Te','I','Xe','At','Rn']

# %%
## Atomic radius
# Definition from: doi: 10.1039/b801115j
# Atom 1-96 are defined 
all_radius=[0.31, 0.28, 1.28, 0.96, 0.84, 0.76, 0.71, 0.66, 0.57, 0.58, 1.66, 1.41, 1.21, 1.11, 1.07, 1.05, 1.02, 1.06, 2.03, 1.76, 1.7, 1.6, 1.53, 1.39, 1.39, 1.32, 1.26, 1.24, 1.32, 1.22, 1.22, 1.2, 1.19, 1.2, 1.2, 1.16, 2.2, 1.95, 1.9, 1.75, 1.64, 1.54, 1.47, 1.46, 1.42, 1.39, 1.45, 1.44, 1.42, 1.39, 1.39, 1.38, 1.39, 1.4, 2.44, 2.15, 2.07, 2.04, 2.03, 2.01, 1.99, 1.98, 1.98, 1.96, 1.94, 1.92, 1.92, 1.89, 1.9, 1.87, 1.87, 1.75, 1.7, 1.62, 1.51, 1.44, 1.41, 1.36, 1.36, 1.32, 1.45, 1.46, 1.48, 1.4, 1.5, 1.5, 2.6, 2.21, 2.15, 2.06, 2.0, 1.96, 1.9, 1.87, 1.8, 1.69]
atom_radius=dict(zip(elements[1:97],all_radius))
valence_elenum=[1,2,1,2,3,4,5,6,7,8,1,2,3,4,5,6,7,8,1,2,3,4,5,6,7,8,9,10,11,12,3,4,5,6,7,8,1,2,3,4,5,6,7,8,9,10,11,12,3,4,5,6,7,8,1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,4,5,6,7,8,9,10,11,12,3,4,5,6,7,8,1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,4,5,6,7,8,9]
'''
A hartree is a unit of energy used in molecular orbital calculations. 
A hartree is equal to 2625.5 kJ/mol, 627.5 kcal/mol, 27.211 eV, and 219474.6 cm-1.
'''


# In[ ]:


def calc_dis(xyzs1,xyzs2):
    """
    Calculate the distance matrix of two coordinates
    xyz1 and xyz2 are arrays which contains xyz coordinates
    """
    #r_abt=xyzs1[:,None,:]-xyzs2[None,:,:]
    #r_ab=np.linalg.norm(r_abt,axis=-1)
    from scipy.spatial import distance_matrix
    return distance_matrix(xyzs1,xyzs2)
    

def set_to_origin(a):
    """
    a should be (3, npoints) numpy arrays with
    coordinates as columns::

        (x1  x2   x3   ... xN
         y1  y2   y3   ... yN
         z1  z2   z3   ... zN)
    """

    # Move the Coordinates of system A to geometric center
    ori=np.mean(a,axis=1)
    a_set=a.T-ori
    # The output are given as :
    return a_set.T,ori


# %%



def rotation_matrix_from_points(m0, m1):
    """Returns a rigid transformation/rotation matrix that minimizes the
    RMSD between two set of points.
    
    m0 and m1 should be (3, npoints) numpy arrays with
    coordinates as columns::

        (x1  x2   x3   ... xN
         y1  y2   y3   ... yN
         z1  z2   z3   ... zN)

    The centeroids should be set to origin prior to
    computing the rotation matrix.

    The rotation matrix is computed using quaternion
    algebra as detailed in::
        
        Melander et al. J. Chem. Theory Comput., 2015, 11,1055
    """

    # compute the rotation quaternion
    v0 = np.copy(m0)
    v1 = np.copy(m1)

    R11, R22, R33 = np.sum(v0 * v1, axis=1)
    R12, R23, R31 = np.sum(v0 * np.roll(v1, -1, axis=0), axis=1)
    R13, R21, R32 = np.sum(v0 * np.roll(v1, -2, axis=0), axis=1)

    f = [[R11 + R22 + R33, R23 - R32, R31 - R13, R12 - R21],
         [R23 - R32, R11 - R22 - R33, R12 + R21, R13 + R31],
         [R31 - R13, R12 + R21, -R11 + R22 - R33, R23 + R32],
         [R12 - R21, R13 + R31, R23 + R32, -R11 - R22 + R33]]

    F = np.array(f)

    w, V = np.linalg.eigh(F)
    # eigenvector corresponding to the most
    # positive eigenvalue
    q = V[:, np.argmax(w)]

    # Rotation matrix from the quaternion q

    R = quaternion_to_matrix(q)

    return R
def quaternion_to_matrix(q):
    """Returns a rotation matrix.
    
    Computed from a unit quaternion Input a numpy array.
    """

    q0, q1, q2, q3 = q
    R_q = [[q0**2 + q1**2 - q2**2 - q3**2,
            2 * (q1 * q2 - q0 * q3),
            2 * (q1 * q3 + q0 * q2)],
           [2 * (q1 * q2 + q0 * q3),
            q0**2 - q1**2 + q2**2 - q3**2,
            2 * (q2 * q3 - q0 * q1)],
           [2 * (q1 * q3 - q0 * q2),
            2 * (q2 * q3 + q0 * q1),
            q0**2 - q1**2 - q2**2 + q3**2]]
    return np.array(R_q)


# %%


def calc_rmsd(coord1,coord2):
    """Return the rmsd value, move vector(to origin point), rotation matrix
     coord1 and coord2 should be as numpy arrays given in:
     [[x1 y1 z1 
     x2 y2 z2
     x3 y3 z3
     .......
     xn yn zn]]
    """
    # for note:
    if coord1.shape[-1]==3:
        pass
    else:
        print('The coordinates of coord1 is wrong! It should be a n*3 numpy array.')
    if coord2.shape[-1]==3:
        pass
    else:
        print('The coordinates of coord2 is wrong! It should be a n*3 numpy array.')
    a1=coord1.T
    a2=coord2.T
    a1,move_1=set_to_origin(a1)
    a2,move_2=set_to_origin(a2)
    # move1,move2: the geometric center of the coord1 and coord2 points
    rotmat=rotation_matrix_from_points(a1,a2)
    a1=a1.T
    rotmat=rotmat.T
    natoms=a1.shape[0]

    rmsd_value=np.sqrt(np.sum((np.dot(a1, rotmat)-a2.T)**2)/natoms)
    # coord1-move_1 and multiply rotmat can get close to: coord2-move_2
    return rotmat,move_1,move_2,rmsd_value

