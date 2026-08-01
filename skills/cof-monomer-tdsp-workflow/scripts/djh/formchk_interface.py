#!/usr/bin/env python                                                                              
import numpy as np
import scipy
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


class FormchkInterface:

    def __init__(self, file_path):
        self.file_path = file_path
        self.natm = NotImplemented
        self.nao = NotImplemented
        self.nmo = NotImplemented
        self.initialization()

    def initialization(self):
        self.natm = int(self.key_to_value("Number of atoms"))
        self.nao = int(self.key_to_value("Number of basis functions"))
        self.nmo = int(self.key_to_value("Number of independent functions"))
        self.nele_a=int(self.key_to_value('Number of alpha electrons'))
        self.nele_b=int(self.key_to_value('Number of beta electrons'))

    def key_to_value(self, key, file_path=None):
        if file_path is None:
            file_path = self.file_path
        flag_read = False
        expect_size = -1
        vec = []
        with open(file_path, "r") as file:
            for l in file:
                if l[:len(key)] == key:
                    try:
                        expect_size = int(l[len(key):].split()[2])
                        flag_read = True
                        continue
                    except IndexError:
                        try:
                            return float(l[len(key):].split()[1])
                        except IndexError:
                            continue
                if flag_read:
                    try:
                        vec += [float(i) for i in l.split()]
                    except ValueError:
                        break
        if len(vec) != expect_size:
            raise ValueError("Number of expected size is not consistent with read-in size!")
        return np.array(vec)

    def total_energy(self, file_path=None):
        if file_path is None:
            file_path = self.file_path
        return self.key_to_value("Total Energy", file_path)

    def scf_energy(self, file_path=None):
        if file_path is None:
            file_path = self.file_path
        return self.key_to_value("SCF Energy", file_path)

    def grad(self, file_path=None):
        if file_path is None:
            file_path = self.file_path
        return self.key_to_value("Cartesian Gradient", file_path).reshape((self.natm, 3))

    def dipole(self, file_path=None):
        if file_path is None:
            file_path = self.file_path
        return self.key_to_value("Dipole Moment", file_path)

    @staticmethod
    def tril_to_symm(tril: np.ndarray):
        dim = int(np.floor(np.sqrt(tril.size * 2)))
        if dim * (dim + 1) / 2 != tril.size:
            raise ValueError("Size " + str(tril.size) + " is probably not a valid lower-triangle matrix.")
        indices_tuple = np.tril_indices(dim)
        iterator = zip(*indices_tuple)
        symm = np.empty((dim, dim))
        for it, (row, col) in enumerate(iterator):
            symm[row, col] = tril[it]
            symm[col, row] = tril[it]
        return symm

    def hessian(self, file_path=None):
        if file_path is None:
            file_path = self.file_path
        return self.tril_to_symm(self.key_to_value("Cartesian Force Constants", file_path))

    def polarizability(self, file_path=None):
        if file_path is None:
            file_path = self.file_path
        # two space after `Polarizability' is to avoid `Polarizability Derivative'
        return self.tril_to_symm(self.key_to_value("Polarizability  ", file_path))

    def dipolederiv(self, file_path=None):
        if file_path is None:
            file_path = self.file_path
        return self.key_to_value("Dipole Derivatives", file_path).reshape(-1, 3)
    def atom_types(self, file_path=None):
        if file_path is None:
            file_path = self.file_path
        return np.array(self.key_to_value("Atomic numbers", file_path),dtype=int)
    def atom_mass(self, file_path=None):
        if file_path is None:
            file_path = self.file_path
        return self.key_to_value("Real atomic weights", file_path)
    def atom_coords(self,file_path=None):# in angstrom
        if file_path is None:
            file_path = self.file_path
        return (self.key_to_value("Current cartesian coordinates",file_path)/1.88972613).reshape(-1,3)
    def dis_mat(self,file_path=None):
        if file_path is None:
            file_path = self.file_path
        return scipy.spatial.distance_matrix(self.atom_coords(),self.atom_coords())
#        return (self.key_to_value("Current cartesian coordinates",file_path)/1.88972613).reshape(-1,3)
        
    def atom_elements(self,file_path=None):
        return [elements[i] for i in self.atom_types()]
    def orbital_energies(self,file_path=None):
        if file_path is None:
            file_path = self.file_path
        alpha_orbital_energies=self.key_to_value("Alpha Orbital Energies", file_path)
        try:
            beta_orbital_energies=self.key_to_value("Beta Orbital Energies", file_path)
        except Exception as e:
            beta_orbital_energies=alpha_orbital_energies.copy()
        return alpha_orbital_energies,beta_orbital_energies
    def homo(self,file_path=None):
        if file_path is None:
            file_path = self.file_path
        alpha_orbital_energies,beta_orbital_energies=self.orbital_energies(file_path)
        return alpha_orbital_energies[self.nele_a-1],beta_orbital_energies[self.nele_b-1]
    def lumo(self,file_path=None):
        if file_path is None:
            file_path = self.file_path
        alpha_orbital_energies,beta_orbital_energies=self.orbital_energies(file_path)
        return alpha_orbital_energies[self.nele_a],beta_orbital_energies[self.nele_b]
    def gap(self,file_path=None):
        if file_path is None:
            file_path = self.file_path
        homo_a,homo_b=self.homo(file_path)
        lumo_a,lumo_b=self.lumo(file_path)
        return lumo_a-homo_a,lumo_b-homo_b
            

