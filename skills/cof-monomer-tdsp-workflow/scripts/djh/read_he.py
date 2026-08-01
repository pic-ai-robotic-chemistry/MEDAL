import os,re
import numpy as np

#input_file='ald-1.fchk'
def read_hole_contri(input_file):
    outnam=input_file.split('.')[0]+'.he.txt'
    out=open(outnam)
    read=False
    hole_contri=[]
    elec_contri=[]
    for i in out:
        if 'Sr index' in i:
            sr=i.split( )[-2]
        if 'D index' in i:
            d_index=i.split( )[-2]
        if 'HDI' in i:
            hdi=float(i.split( )[-1])
        if 'EDI' in i:
            edi=float(i.split( )[-1])
        if read:
            if i.split( )==[]:
                read=False
            else:
                i=i.split('Overlap:')[0]
                i=i.split('Hole:')[1]
                i=i.split('%  Electron:')
#                hole_match = re.search(r'Hole:*', i)
                #electron_match = re.search(r'Electron:*', i)
                #hole_percentage = float(hole_match.group(1)) if hole_match else None
                #electron_percentage = float(electron_match.group(1)) if electron_match else None
                hole_percentage,electron_percentage=float(i[0]),float(i[1].replace('%','')) 
         
                hole_contri.append(hole_percentage)
                elec_contri.append(electron_percentage)
        if 'Contribution of each atom to hole and electron:' in i:
            read=True
    out.close()
    hole_contri,elec_contri=np.array(hole_contri,dtype=float),np.array(elec_contri,dtype=float)
    return sr,d_index,hdi,edi,hole_contri,elec_contri

#read_hole_contri('ami-10')
