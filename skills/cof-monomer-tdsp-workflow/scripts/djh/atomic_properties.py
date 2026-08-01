#!/usr/bin/env python
# coding: utf-8

# In[1]:


#!/usr/bin/env python
# coding: utf-8

import pandas as pd
from os import system as ss
import os,sys
import numpy as np
from subprocess import getstatusoutput as gs

# This is the library for functions of extracting atomic properties only
# pubchem_elements.csv is required , downloaded from https://pubchem.ncbi.nlm.nih.gov/periodic-table/electronegativity/


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

##-- atomic radius
# Definition from: doi: 10.1039/b801115j, Covalent Atom 1-96 are defined 
covalent_radius=[0.31, 0.28, 1.28, 0.96, 0.84, 0.76, 0.71, 0.66, 0.57, 0.58, 1.66, 1.41, 1.21, 1.11, 1.07, 1.05, 1.02, 1.06, 2.03, 1.76, 1.7, 1.6, 1.53, 1.39, 1.39, 1.32, 1.26, 1.24, 1.32, 1.22, 1.22, 1.2, 1.19, 1.2, 1.2, 1.16, 2.2, 1.95, 1.9, 1.75, 1.64, 1.54, 1.47, 1.46, 1.42, 1.39, 1.45, 1.44, 1.42, 1.39, 1.39, 1.38, 1.39, 1.4, 2.44, 2.15, 2.07, 2.04, 2.03, 2.01, 1.99, 1.98, 1.98, 1.96, 1.94, 1.92, 1.92, 1.89, 1.9, 1.87, 1.87, 1.75, 1.7, 1.62, 1.51, 1.44, 1.41, 1.36, 1.36, 1.32, 1.45, 1.46, 1.48, 1.4, 1.5, 1.5, 2.6, 2.21, 2.15, 2.06, 2.0, 1.96, 1.9, 1.87, 1.8, 1.69]
covalent_radius=dict(zip(elements[1:97],covalent_radius))

## Pyykko radius
# Definition from: 10.1002/chem.200800987
pyykko_radius=[32,46,
133,102, 85,75,71,63,64,67,
155,139, 126,116,111,103,99,96,
196,171, 148,136,134,122,119,116,111,110,112,118,124,121,121,116,114,117,
210,185, 163,154,147,138,128,125,125,120,128,136,142,140,140,136,133,131,
232,196, 180,163,176,174,173,172,168,169,168,167,166,165,164,170,162, 152,146,137,131,129,122,123,124,133,144,144,151,145,147,142,
223,201, 186,175,169,170,171,172,166,166,168,168,165,167,173,176,161, 157,149,143,141,134,129,128,121,122,136,143,162,175,165,157
]
pyykko_radius=np.array(pyykko_radius,dtype=float)/100

valence_ele_num=[1,2,1,2,3,4,5,6,7,8,1,2,3,4,5,6,7,8,1,2,3,4,5,6,7,8,9,10,11,12,3,4,5,6,7,8,1,2,3,4,5,6,7,8,9,10,11,12,3,4,5,6,7,8,1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,4,5,6,7,8,9,10,11,12,3,4,5,6,7,8,1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,4,5,6,7,8,9]

## Pauling electronegativity
# National Center for Biotechnology Information (2023). Electronegativity in the Periodic Table of Elements. Retrieved February 6, 2023 from https://pubchem.ncbi.nlm.nih.gov/periodic-table/electronegativity.

pub_eles=pd.read_csv('C:/Users/djh/anaconda3/Lib/site-packages/djh/pubchem_elements.csv')

def read_pub_chem(prop):
    arry=pub_eles.loc[:,prop]
    arry=np.array(arry).reshape(1,-1)[0]
    return arry

# Electronegativity
# http://ctcp.massey.ac.nz/index.php?menu=dipole&page=dipole
AtomicMass=read_pub_chem('AtomicMass')
Electronegativity=read_pub_chem('Electronegativity') 
AtomicRadius=read_pub_chem('AtomicRadius')/100
IonizationEnergy=read_pub_chem('IonizationEnergy')
ElectronAffinity=read_pub_chem('ElectronAffinity')
MeltingPoint=read_pub_chem('MeltingPoint')
BoilingPoin=read_pub_chem('BoilingPoint')
Density=read_pub_chem('Density')


# In[2]:


# ä»·çµå­çç»æå¤æ­
val=read_pub_chem('ElectronConfiguration')
# æ»ä»·çµå­æ°ç®
val_split=[v.split(']')[-1] for v in val]
val_total=valence_ele_num
# dçµå­æ°ç®
val_d=[]
for v in val_split[:-10]:
    if 'd' in v:
        vd=(v.split('d')[-1]).split( )[0]
        val_d.append(int(vd))
    else:
        val_d.append(0)
# sçµå­
val_s=[]
for v in val_split[:-10]:
    if 's' in v:
        vs=(v.split('s')[-1]).split( )[0]
        val_s.append(int(vs))
    else:
        val_s.append(0)
# pçµå­
val_p=[]
for v in val_split[:-10]:
    if 'p' in v:
        vp=(v.split('p')[-1]).split( )[0]
        val_p.append(int(vp))
    else:
        val_p.append(0)


# In[3]:


# 周期
period=[]
for v in val:
    if v[:3]=='[He':
        period.append(2)
    elif v[:3]=='[Ne':
        period.append(3)
    elif v[:3]=='[Ar':
        period.append(4)
    elif v[:3]=='[Kr':
        period.append(5)
    elif v[:3]=='[Xe':
        period.append(6)
    elif v[:3]=='[Rn':
        period.append(7)
    else:
        period.append(1)

# 族
group=[0 for i in range(103)]
for i in [1,3,11,19,37,55,87]:
    group[i-1]='1A'
for i in [4,12,20,38,56,88]:
    group[i-1]='2A'
for i in [21,39]+list(range(57,72))+list(range(89,104)):
    group[i-1]='3B'
for i in [22,40,72]:
    group[i-1]='4B'
for i in [23,41,73]:
    group[i-1]='5B'
for i in [24,42,74]:
    group[i-1]='6B'
for i in [25,43,75]:
    group[i-1]='7B'
for i in [26,27,28,44,45,46,76,77,78]:
    group[i-1]='8'
for i in [29,47,79]:
    group[i-1]='1B'
for i in [30,48,80]:
    group[i-1]='2B'
for i in [5,13,31,49,81]:
    group[i-1]='3A'
for i in [6,14,32,50,82]:
    group[i-1]='4A'
for i in [7,15,33,51,83]:
    group[i-1]='5A'
for i in [8,16,34,52,84]:
    group[i-1]='6A'
for i in [9,17,35,53,85]:
    group[i-1]='7A'
for i in [2,10,18,36,54,86]:
    group[i-1]='0'

