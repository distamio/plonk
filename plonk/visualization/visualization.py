"""The Visualization class.

This class contains methods for visualizing smoothed particle
hydrodynamics simulation data.
"""

from copy import copy
from typing import Any, Dict, Optional, Tuple

import matplotlib as mpl
import matplotlib.pyplot as plt
import numpy as np
from mpl_toolkits.axes_grid1 import make_axes_locatable
from numpy import ndarray
from scipy.interpolate import RectBivariateSpline
from skimage import transform

from .interpolation import scalar_interpolation, vector_interpolation
from ..dump.dump import Dump

_plot_render = True
_plot_contour = False
_contour_color = 'black'
_contour_format = '%.2g'
_norm = 'linear'
_cmap = 'gist_heat'
_polar_coordinates = False
_number_of_pixels = (512, 512)
_plot_stream = False
_vector_color = 'black'
_vector_scale = None
_vector_scale_units = None
_normalize_vectors = False
_number_of_arrows = (25, 25)


class Visualization:
    """Visualize scalar and vector smoothed particle hydrodynamics data.

    Visualize SPH data as a particle plot, a rendered image, a vector
    plot, or a combination. The x, y coordinates are the particle
    Cartesian coordinates, corresponding to the x and y axes of the
    plot.

    Pass in options for scalar plots, vector plots, and for
    interpolation via the 'scalar_options', 'vector_options', and
    'interpolation_options' dictionaries.

    Parameters
    ----------
    scalar_data, optional
        The 1d array (N,) of scalar data to visualize.
    vector_data, optional
        The 2d array (N, 2) of vector data to visualize.
    x_coordinate
        The x-position on the particles, where x is the required plot
        x-axis.
    y_coordinate
        The y-position on the particles, where y is the required plot
        y-axis.
    z_coordinate, optional
        The z-position on the particles, where z is the depth-axis for
        the required plot.
    extent
        The range in the x- and y-direction as (xmin, xmax, ymin, ymax).
    particle_mass
        The particle mass for each particle.
    smoothing_length
        The smoothing length for each particle.
    axis, optional
        A matplotlib axis handle.
    scalar_options, optional
        A dictionary of options for scalar plots.
    vector_options, optional
        A dictionary of options for vector plots.
    interpolation_options, optional
        A dictionary of options for interpolation.
    """

    def __init__(
        self,
        *,
        scalar_data: Optional[ndarray] = None,
        vector_data: Optional[ndarray] = None,
        x_coordinate: ndarray,
        y_coordinate: ndarray,
        z_coordinate: Optional[ndarray] = None,
        extent: Tuple[float, float, float, float],
        particle_mass: ndarray,
        smoothing_length: ndarray,
        axis: Optional[Any] = None,
        scalar_options: Dict[str, Any] = None,
        vector_options: Dict[str, Any] = None,
        interpolation_options: Dict[str, Any] = None,
    ):

        self.fig: Any = None
        self.axis: Any = None
        self.scalar: Dict[str, Any] = {
            'image': None,
            'contours': None,
            'colorbar': None,
            'data': None,
        }
        self.vector: Dict[str, Any] = {'quiver': None, 'streamplot': None, 'data': None}

        _scalar_options = copy(scalar_options)
        _vector_options = copy(vector_options)
        _interpolation_options = copy(interpolation_options)

        if axis is None:
            self.fig, self.axis = plt.subplots()
        else:
            self.fig = axis.get_figure()
            self.axis = axis

        if scalar_data is None and vector_data is None:
            self._particle_plot(
                x_coordinate=x_coordinate,
                y_coordinate=y_coordinate,
                smoothing_length=smoothing_length,
                axis=self.axis,
            )

        if scalar_data is not None:
            self._scalar_plot(
                data=scalar_data,
                x_coordinate=x_coordinate,
                y_coordinate=y_coordinate,
                z_coordinate=z_coordinate,
                particle_mass=particle_mass,
                smoothing_length=smoothing_length,
                extent=extent,
                fig=self.fig,
                axis=self.axis,
                plot_options=_scalar_options,
                interpolation_options=_interpolation_options,
            )
            if not np.allclose(self.scalar['extent'], extent):
                new_extent = self.scalar['extent']

        if vector_data is not None:
            self._vector_plot(
                data=vector_data,
                x_coordinate=x_coordinate,
                y_coordinate=y_coordinate,
                z_coordinate=z_coordinate,
                particle_mass=particle_mass,
                smoothing_length=smoothing_length,
                extent=extent,
                axis=self.axis,
                plot_options=_vector_options,
                interpolation_options=_interpolation_options,
            )
            try:
                if not np.allclose(self.vector['extent'], new_extent):
                    raise ValueError('scalar and vector plot have different extent')
            except NameError:
                pass

        try:
            extent = new_extent
        except NameError:
            pass
        self.axis.set_xlim(*extent[:2])
        self.axis.set_ylim(*extent[2:])

        self.axis.set_aspect('equal')

    def _particle_plot(
        self,
        x_coordinate: ndarray,
        y_coordinate: ndarray,
        smoothing_length: ndarray,
        axis: Any,
    ):

        axis.plot(
            x_coordinate[smoothing_length > 0],
            y_coordinate[smoothing_length > 0],
            'k.',
            markersize=0.5,
        )
        return

    def _scalar_plot(
        self,
        *,
        data: ndarray,
        x_coordinate: ndarray,
        y_coordinate: ndarray,
        z_coordinate: Optional[ndarray] = None,
        particle_mass: ndarray,
        smoothing_length: ndarray,
        extent: Tuple[float, float, float, float],
        axis: Any,
        fig: Any,
        plot_options: Dict[str, Any] = None,
        interpolation_options: Dict[str, Any] = None,
    ):

        if plot_options is None:
            plot_options = {}

        plot_render = plot_options.pop('plot_render', _plot_render)
        plot_contour = plot_options.pop('plot_contour', _plot_contour)
        colors = plot_options.pop('contour_color', _contour_color)
        fmt = plot_options.pop('contour_format', _contour_format)
        norm_str = plot_options.pop('norm', _norm)
        cmap = plot_options.pop('cmap', _cmap)
        polar_coordinates = plot_options.pop('polar_coordinates', _polar_coordinates)

        if len(plot_options) > 0:
            raise ValueError(f'plot_options: {list(plot_options.keys())} not available')

        if interpolation_options is None:
            interpolation_options = {}

        number_of_pixels = interpolation_options.pop(
            'number_of_pixels', _number_of_pixels
        )

        data = scalar_interpolation(
            data=data,
            x_position=x_coordinate,
            y_position=y_coordinate,
            z_position=z_coordinate,
            extent=extent,
            smoothing_length=smoothing_length,
            particle_mass=particle_mass,
            number_of_pixels=number_of_pixels,
            **interpolation_options,
        )

        if polar_coordinates:
            if not np.allclose(extent[1] - extent[0], extent[3] - extent[2]):
                raise ValueError('Bad polar plot: x and y have different scales')
            radius_pix = 0.5 * data.shape[0]
            data = transform.warp_polar(data, radius=radius_pix)

            radius = 0.5 * (extent[1] - extent[0])
            extent = (0, radius, 0, 2 * np.pi)

            x_grid = np.linspace(*extent[:2], data.shape[0])
            y_grid = np.linspace(*extent[2:], data.shape[1])
            spl = RectBivariateSpline(x_grid, y_grid, data)
            x_regrid = np.linspace(extent[0], extent[1], number_of_pixels[0])
            y_regrid = np.linspace(extent[2], extent[3], number_of_pixels[1])
            data = spl(x_regrid, y_regrid)

        image = None
        colorbar = None
        if plot_render:
            if norm_str.lower() in ('linear', 'lin'):
                norm = mpl.colors.Normalize()
            elif norm_str.lower() in ('logarithic', 'logarithm', 'log', 'log10'):
                norm = mpl.colors.LogNorm()
            else:
                raise ValueError('Cannot determine normalization for colorbar')

            image = axis.imshow(
                data, origin='lower', norm=norm, extent=extent, cmap=cmap
            )

            divider = make_axes_locatable(axis)
            cax = divider.append_axes("right", size="5%", pad=0.05)
            colorbar = fig.colorbar(image, cax)

        contour = None
        if plot_contour:
            n_interp_x, n_interp_y = data.shape
            X, Y = np.meshgrid(
                np.linspace(*extent[:2], n_interp_x),
                np.linspace(*extent[2:], n_interp_y),
            )

            contour = axis.contour(X, Y, data, colors=colors)
            contour.clabel(inline=True, fmt=fmt, fontsize=8)

        self.scalar['image'] = image
        self.scalar['contours'] = contour
        self.scalar['colorbar'] = colorbar
        self.scalar['data'] = data
        self.scalar['extent'] = extent
        return

    def _vector_plot(
        self,
        *,
        data: ndarray,
        x_coordinate: ndarray,
        y_coordinate: ndarray,
        z_coordinate: Optional[ndarray] = None,
        particle_mass: ndarray,
        smoothing_length: ndarray,
        extent: Tuple[float, float, float, float],
        axis: Any,
        plot_options: Dict[str, Any] = None,
        interpolation_options: Dict[str, Any] = None,
    ):

        if plot_options is None:
            plot_options = {}

        plot_stream = plot_options.pop('plot_stream', _plot_stream)
        color = plot_options.pop('vector_color', _vector_color)
        scale = plot_options.pop('vector_scale', _vector_scale)
        scale_units = plot_options.pop('vector_scale_units', _vector_scale_units)
        normalize_vectors = plot_options.pop('normalize_vectors', _normalize_vectors)
        number_of_arrows = plot_options.pop('number_of_arrows', _number_of_arrows)

        if len(plot_options) > 0:
            raise ValueError(f'plot_options: {list(plot_options.keys())} not available')

        if interpolation_options is None:
            interpolation_options = {}

        number_of_pixels = interpolation_options.pop(
            'number_of_pixels', _number_of_pixels
        )

        data = vector_interpolation(
            x_data=data[:, 0],
            y_data=data[:, 1],
            x_position=x_coordinate,
            y_position=y_coordinate,
            z_position=z_coordinate,
            extent=extent,
            smoothing_length=smoothing_length,
            particle_mass=particle_mass,
            number_of_pixels=number_of_pixels,
            **interpolation_options,
        )

        n_interp_x, n_interp_y = data[0].shape
        X, Y = np.meshgrid(
            np.linspace(*extent[:2], n_interp_x), np.linspace(*extent[2:], n_interp_y)
        )
        U, V = data[0], data[1]

        quiver, streamplot = None, None
        if not plot_stream:
            n_x, n_y = number_of_arrows[0], number_of_arrows[1]
            stride_x = int(n_interp_x / n_x)
            stride_y = int(n_interp_y / n_y)
            X = X[::stride_y, ::stride_x]
            Y = Y[::stride_y, ::stride_x]
            U = U[::stride_y, ::stride_x]
            V = V[::stride_y, ::stride_x]
            if normalize_vectors:
                norm = np.hypot(U, V)
                U /= norm
                V /= norm
            quiver = axis.quiver(
                X, Y, U, V, scale=scale, scale_units=scale_units, color=color
            )

        else:
            streamplot = axis.streamplot(X, Y, U, V, color=color)

        self.vector['quiver'] = quiver
        self.vector['streamplot'] = streamplot
        self.vector['data'] = data
        self.vector['extent'] = extent
        return

    def __repr__(self):
        """Dunder repr method."""
        return '<plonk.Visualization>'


def render(
    dump: Dump,
    quantity: str,
    extent: Optional[Tuple[float, float, float, float]] = None,
    scalar_options: Optional[Dict[Any, Any]] = None,
    interpolation_options: Optional[Dict[Any, Any]] = None,
) -> Visualization:
    """Produce a rendered image of a quantity on the dump.

    Parameters
    ----------
    dump
        The dump file containing the quantity.
    quantity
        The quantity to render, as a string.
    extent
        The xy extent of the image as (xmin, xmax, ymin, ymax), by
        default None.
    scalar_options
        Options passed to the scalar rendering function, by default
        None.
    interpolation_options
        Options passed to the interpolation function, by default None.

    Returns
    -------
    Visualization
        The Visualization object for the rendered image.
    """
    if scalar_options is None:
        scalar_options = {}
    if interpolation_options is None:
        interpolation_options = {}

    polar = False
    if scalar_options.get('polar_coordinates'):
        polar = True

    need_z = False
    if interpolation_options.get('cross_section') is not None:
        need_z = True

    if quantity is None:
        quantity = 'density'

    if quantity in ('rho', 'density'):
        scalar_data = dump.density
    elif quantity in ('vx', 'velocity_x'):
        scalar_data = dump.particles.arrays['vxyz'][:, 0]
    elif quantity in ('vy', 'velocity_y'):
        scalar_data = dump.particles.arrays['vxyz'][:, 1]
    elif quantity in ('vz', 'velocity_z'):
        scalar_data = dump.particles.arrays['vxyz'][:, 2]
    else:
        raise ValueError(
            'Cannot determine quantity to render. See Visualization for more details.'
        )

    position = dump.particles.arrays['xyz'][:]
    smoothing_length = dump.particles.arrays['h'][:]
    particle_mass = dump.mass

    minimum_xy = np.percentile(position[:, :2], 1, axis=0)
    maximum_xy = np.percentile(position[:, :2], 99, axis=0)
    if extent is None:
        extent = (minimum_xy[0], maximum_xy[0]) + (minimum_xy[1], maximum_xy[1])
        if polar:
            # extent must be square for polar plots
            extent = (
                max(minimum_xy),
                min(maximum_xy),
                max(minimum_xy),
                min(maximum_xy),
            )

    x_coordinate = position[:, 0]
    y_coordinate = position[:, 1]
    z_coordinate = None
    if need_z:
        z_coordinate = position[:, 2]

    viz = Visualization(
        scalar_data=scalar_data,
        x_coordinate=x_coordinate,
        y_coordinate=y_coordinate,
        z_coordinate=z_coordinate,
        extent=extent,
        particle_mass=particle_mass,
        smoothing_length=smoothing_length,
        scalar_options=scalar_options,
        interpolation_options=interpolation_options,
    )

    if polar:
        viz.axis.set_aspect('auto')

    return viz
