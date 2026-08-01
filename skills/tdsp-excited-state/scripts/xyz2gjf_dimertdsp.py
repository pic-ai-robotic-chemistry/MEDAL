#!/usr/bin/env python 
import sys
xyznam=sys.argv[1]
nproc='16' #
mem='20gb'  #
job='tdsp'
chrg='0'
spin='1'
 
if job=='opt':
    key1='#p cam-b3lyp/def2svpp em=gd3bj nosymm opt freq '
if job=='tdsp':
    key1='#p PBE1PBE/def2SVP nosymm td(nstates=5,root=1) iop(9/40=4) '
# PBE1PBE

xyzf=open(xyznam)
xyz=xyzf.readlines()
xyzf.close()
 
gjf=open(xyznam[:-3]+'gjf','w')
gjf.write('%nproc='+nproc+'\n')
gjf.write('%mem='+mem+'\n')
gjf.write('%chk='+xyznam[:-3]+'chk\n')
gjf.write(key1+'\n')
gjf.write('\ntitle\n\n'+chrg+' '+spin+'\n')
for x in xyz[2:]:
    gjf.write(x)
gjf.write('\n'*2)                                                    

