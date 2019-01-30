'''
particles.py

Daniel Mentiplay, 2019.
'''

import numpy as np

class Particles:
    '''
    Generic SPH particles.
    '''

    def __init__(self):

        #--- Number of particles

        self.number = 0

        #--- Mass of particles

        self.mass = 0

        #--- Positions

        self.position = None

        #--- Velocities

        self.velocity = None

        #--- Smoothing lengths

        self.smoothingLength = None

class Gas(Particles):
    '''
    Gas particles.
    '''

    def __init__(self):
        super().__init__()

        #--- Dust fractions

        self.dustFrac = None

class Dust(Particles):
    '''
    Dust particles.
    '''

def density_from_smoothing_length(smoothingLength, particleMass, hfact=1.2):
    '''
    Calculate density from particle mass and smoothing length.
    '''

    return particleMass * (hfact/np.abs(smoothingLength))**3
