import os,sys                                                                                   
 
fchknam=sys.argv[1]
 
#def calc_he_contri(fchknam):
#    os.system('echo -e \'18\n1\n\n1\n3\n1\n3\n1\n7\n0\n0\n0\nq\' | Multiwfn '+fchknam+' > '+fch
 
def calc_he_s1(fchknam):
    com='18 1 \n 1 1 2 0 3 2 7 0 0 0 q'
    com=com.replace(' ','\n')
    os.system('echo -e \''+com+'\' |Multiwfn '+fchknam+' > '+fchknam.split('.')[0]+'.he.txt')
calc_he_s1(fchknam)
 
