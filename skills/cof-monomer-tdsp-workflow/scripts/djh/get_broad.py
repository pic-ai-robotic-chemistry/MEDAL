#!/usr/bin/env python
# coding: utf-8
# %%
import scipy
import pandas as pd
import numpy as np

import math
import matplotlib.pyplot as plt
from scipy.special import wofz



def Gauss(x,A,xc,fwhm):
    c=2*math.sqrt(2*math.log(2))
    sigma=fwhm/c # FWHM=2*sigma*(2ln2)**0.5
    y= A*np.exp(-(x-xc)**2/(2*sigma**2))
    return y

def Lorentz(x,A,xc,fwhm):
    y = A*0.25*fwhm**2/((x-xc)**2 + 0.25*fwhm**2)
    return y

def pVoigt(x,A,xc,fwhm):
    return 0.5*Gauss(x,A,xc,fwhm)+0.5*Lorentz(x,A,xc,fwhm)

# 不靠谱，慎用
def Voigt(x, y0, amp, pos, fwhm, shape = 1):
    tmp = 1/wofz(np.zeros((len(x))) + 1j*np.sqrt(np.log(2.0))*shape).real
    return y0+tmp*amp*wofz(2*np.sqrt(np.log(2.0))*(x-pos)/fwhm+1j*np.sqrt(np.log(2.0))*shape).real

def get_broad(
    peak_sites,peak_intenses,half_width=0.2,
    xmin=0,xmax=21.22,grid_num=1000,
    function='Gauss'
    ):
    x=np.arange(grid_num,dtype='float32')
    x*=(xmax-xmin)/grid_num
    x+=xmin
    y=np.zeros(grid_num)
    for site,amp in zip(peak_sites,peak_intenses):
        if function=='pVoigt':
            y+=pVoigt(x,amp,site,half_width)
        if function=='Gauss':
            y+=Gauss(x,amp,site,half_width)
        if function=='Lorentz':
            y+=Lorentz(x,amp,site,half_width)

    return x,y