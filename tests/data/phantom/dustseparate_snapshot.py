"""Stub data for reading Phantom snapshots."""

import numpy as np

array_name_map = {
    'divv': 'velocity_divergence',
    'dt': 'timestep',
    'dustfrac': 'dust_to_gas_ratio',
    'h': 'smoothing_length',
    'tstop': 'stopping_time',
    'vxyz': 'velocity',
    'xyz': 'position',
}

mean_array_values = {
    'dt': 27.693,
    'dustfrac': 0.004310665694734535,
    'h': 14.473696,
    'tstop': 426.2011872672413,
}

std_array_values = {
    'vxyz': 0.09247972116933928,
    'xyz': 52.5885856475364,
}

properties = {
    'adiabatic_index': 1.0,
    'dust_method': 'dust as separate sets of particles',
    'equation_of_state': 'locally isothermal disc',
    'grain_density': np.array([3000.0]),
    'grain_size': np.array([0.01]),
    'smoothing_length_factor': 1.0,
    'time': 0.0,
}