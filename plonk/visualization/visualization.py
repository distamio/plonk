"""
This module contains the Visualization class.

This class contains methods for visualizing smoothed particle
hydrodynamics simulations.
"""

import functools
import warnings

import matplotlib.colors as colors
import matplotlib.pyplot as plt
import numpy as np
import sympy
from mpl_toolkits.axes_grid1 import make_axes_locatable

from ..core.constants import constants
from ..core.particles import I_GAS
from ..core.units import is_dimension_same
from ..core.utils import normalize_vector, rotate_vector_arbitrary_axis
from .interpolation import scalar_interpolation, vector_interpolation
from .options import PlotOptions


class Visualization:
    """
    Visualize a dump as a particle plot, a rendered plot, a
    vector plot, or a combination.

    Parameters
    ----------
    dump : Dump object
        The plonk.Dump object to visualize.
    render : str or 1d numpy.ndarray, default ``None``
        Scalar quantity to render. If str, render must be a quantity on
        the particles, or a symbolic str that Sympy can interpret.
        Alternatively render can be a 1d array of values on the
        particles.
    vector : str or 3d numpy.ndarray, default ``None``
        Vector quantity to be represented as arrows or stream
        function. If str, vector must be a quantity on
        the particles, or a symbolic str that Sympy can interpret.
        Alternatively render can be a 2d array of 3d values on the
        particles.

    Other Parameters
    ----------------
    particle_type : int, default I_GAS
        Particle type to plot, as an int.
    particle_types : collection (list, tuple) of int
        Particle types to plot, as a collection of int.

    extent : list or tuple of float (len=4), default ``None``
        Specify the x and y image range as [xmin, xmax, ymin, ymax].
    size : float
        Specify the x and y image range as [-size, size, -size, size].

    rotation_axis : list of float (len=3), default ``None``
        A 3-dimensional vector specifying an axis around which to
        rotate the reference frame. Must also specify
        ``rotation_angle``.
    rotation_angle : float, default ``None``
        An angle (radians) to rotate the reference frame around a
        ``rotation_axis``.
    position_angle : float, default ``None``
        An angle (radians) East of North specifying an axis around
        which to incline the reference frame as specified by
        ``inclination``.
    inclination : float, default ``None``
        An angle (radians) of inclination specified relative to a
        ``position_angle``.

    units : Units, default None
        A plonk.Units object with the units to convert to.
    integrated_z : float
        A length scale for the integrated z direction in projection
        plots.

    render_scale : str, default 'linear'
        Render scale options include: 'log', 'linear'.
    render_min : float, default None
        Minimum value of the rendered quantity.
    render_max : float, default None
        Maximum value of the rendered quantity.
    render_fraction_max : float, default None
        Maximum value of the rendered quantity specified as a
        fraction of the maximum in the data.

    stream : bool, default False
        If true, plot vector plots as stream functions.
    stride : int, default 25
        Striding through vector interpolation for vector plots.
    vector_color : str, default None
        Color of vector field as arrows or streamfunction.

    axis : Axes, default None
        Matplotlib Axes object to plot to.
    colorbar : bool, default True
        If true, plot colorbar.
    colormap : str, default 'gist_heat'
        Specify the colormap.
    figure : Figure, default None
        Matplotlib Figure to add Axes to.
    font_family : str, default 'sans-serif'
        Font family style for axes title, label, etc.
    font_size : int, default 12
        Font size for axes title, label, etc.
    render_label : str
        Label for colorbar for rendered figures.
    title : str, default None
        Plot title.

    accelerate : bool, default False
        Use accelerated interpolation.
    cross_section : bool, default False
        If true, plot a cross section rather than column density
        with slice position specified by ``slice_position``.
    density_weighted : bool, default False
        Use density weighted interpolation.
    normalize : bool, default False
        Use normalized interpolation.
    number_pixels : list of float (len=2), default (512, 512)
        The number of pixels in the horizontal and vertical
        directions, like [npixx, npixy], for interpolation. This
        determines the resolution of the image.
    observer_distance : float, default None
        Distance of observer to screen.
    opacity : bool, default False
        Use opacity rendering.
    perspective : bool, default False
        Use 3D perspective rendering.
    slice_position : float, 0.0
        Position of the cross sectional slice.

    Examples
    --------
    Rendering scalar fields.
    >>> viz = plonk.Visualization(dump, render='density')
    >>> viz = plonk.Visualization(
    ...     dump,
    ...     render='sqrt(vx**2 + vy**2) - sqrt(G*M/R)'
    ...     )
    >>> viz = plonk.Visualization(dump, render=some_numpy_array)

    Plotting vector fields.
    >>> viz = plonk.Visualization(dump, vector='velocity')
    >>> viz = plonk.Visualization(dump, render=some_numpy_array)

    Rotate frame around arbitrary vector.
    >>> viz.rotate_frame(vector=[1, 0, 0], angle=np.pi/2)

    Set image window size.
    >>> viz.set_image_size([-150, 150, -150, 150])

    Set particle type.
    >>> I_DUST = 7
    >>> viz.set_particle_type(I_DUST)

    Set rendered quantity range.
    >>> viz.set_render_range(vmin=0, vmax=1e-7)
    """

    def __init__(self, dump, render=None, vector=None, **kwargs):

        self._options = PlotOptions()
        options_labels = self._options.__dataclass_fields__.keys()
        for options in options_labels:
            sub_options = getattr(self._options, options)
            for key in dict(kwargs):
                if key in getattr(sub_options, '__dataclass_fields__'):
                    setattr(sub_options, key, kwargs.pop(key))

        self._extent = kwargs.pop('extent', None)
        self._size = kwargs.pop('size', None)

        self._render_fraction_max = kwargs.pop('render_fraction_max', None)

        self._position_angle = kwargs.pop('position_angle', None)
        self._inclination = kwargs.pop('inclination', None)

        self._initialized = False

        self._dump = dump
        self._particles = dump.particles
        self._sinks = dump.sinks
        self._header = dump.header
        self._units = dump.units

        self.axis = self._options.figure.axis
        self.figure = self._options.figure.figure
        if self.axis is None and self.figure is None:
            plt.clf()
            self.figure = plt.gcf()
        if self.axis is None:
            self.axis = self.figure.gca()
        if self.figure is None:
            self.figure = self.axis.get_figure()

        self._render = None
        self._vector = None
        self._plot_particles = False
        self._plot_render = False
        self._plot_vector = False
        if render is None and vector is None:
            self._plot_particles = True
        if render is not None:
            self._render = render
            self._plot_render = True
        if vector is not None:
            self._vector = vector
            self._plot_vector = True

        self._available_particle_types = set(
            np.unique(self._particles.arrays['itype'][:])
        )
        particle_type = kwargs.pop('particle_type', None)
        particle_types = kwargs.pop('particle_types', None)
        if particle_types is None and particle_type is not None:
            particle_types = particle_type
        self.set_particle_type(particle_types)

        if kwargs:
            for key in kwargs:
                warnings.warn(f'Unknown keyword argument: {key}', UserWarning)

        self.set_units(self._options.units.units, self._options.units.integrated_z)
        self._init_frame_rotation()
        self._init_image_size()
        self._make_plot()

        self._initialized = True

    def _rotate(func):
        """
        Decorator to compute quantity under frame rotation. Should only
        be applied to vector quantities.
        """

        @functools.wraps(func)
        def wrapper_rotate(*args, **kwargs):
            if args[0]._rotate_frame:
                value = rotate_vector_arbitrary_axis(
                    func(*args, **kwargs),
                    args[0]._options.rotation.rotation_axis,
                    args[0]._options.rotation.rotation_angle,
                )
            else:
                value = func(*args, **kwargs)
            return value

        return wrapper_rotate

    def _mask(func):
        """Decorator to apply particle mask to quantities."""

        @functools.wraps(func)
        def wrapper_mask(*args, **kwargs):
            if args[0]._particle_mask is not None:
                value = func(*args, **kwargs)[args[0]._particle_mask]
            else:
                value = func(*args, **kwargs)
            return value

        return wrapper_mask

    def _unit_conversion(dimension):
        """Decorator to apply unit conversion quantities."""

        def decorator_unit_conversion(func):
            @functools.wraps(func)
            def wrapper_unit_conversion(*args, **kwargs):
                if args[0]._new_units is not None:
                    value = args[0]._units.convert_quantity_to_new_units(
                        func(*args, **kwargs), dimension, args[0]._new_units
                    )
                else:
                    value = func(*args, **kwargs)
                return value

            return wrapper_unit_conversion

        return decorator_unit_conversion

    @_mask
    def _particle_quantity(self, quantity):
        """Reference a particle quantity by str."""
        if self._new_units is not None:
            dimension = self._particles.dimensions[quantity]
            for u in self._new_units.units._fields:
                if is_dimension_same(u, dimension):
                    dimension = u
            return self._units.convert_quantity_to_new_units(
                self._particles.arrays[quantity], dimension, self._new_units
            )
        return self._particles.arrays[quantity]

    @_mask
    def _extra_quantity(self, quantity):
        """Reference a particle extra quantity by str."""
        if self._new_units is not None:
            dimension = self._dump.extra_quantity(quantity)[1]
            for u in self._new_units.units._fields:
                if is_dimension_same(u, dimension):
                    dimension = u
            return self._units.convert_quantity_to_new_units(
                self._dump.extra_quantity(quantity)[0], dimension, self._new_units
            )
        return self._dump.extra_quantity(quantity)[0]

    @property
    def _interpolation_weights(self):
        """Interpolation weights."""
        if self._options.interpolation.density_weighted:
            return np.array(self._particle_mass / self._h ** 2)
        return np.full_like(self._h, 1 / self._header['hfact'])

    @property
    @_unit_conversion(dimension='M')
    @_mask
    def _particle_mass(self):
        """Particle masses."""
        return self._dump.mass

    @property
    @_rotate
    @_unit_conversion(dimension='L')
    @_mask
    def _xyz(self):
        """Particle positions."""
        return self._particles.arrays['xyz'][:]

    @property
    @_unit_conversion(dimension='L')
    @_mask
    def _h(self):
        """Particle smoothing lengths."""
        return self._particles.arrays['h'][:]

    @property
    @_unit_conversion(dimension='density')
    @_mask
    def _density(self):
        """Particle density."""
        return self._dump.density

    @property
    @_rotate
    @_unit_conversion(dimension='velocity')
    @_mask
    def _vxyz(self):
        """Particle velocities."""
        return self._particles.arrays['vxyz'][:]

    def _x(self):
        return self._xyz[:, 0]

    def _y(self):
        return self._xyz[:, 1]

    def _z(self):
        return self._xyz[:, 2]

    def _vx(self):
        return self._vxyz[:, 0]

    def _vy(self):
        return self._vxyz[:, 1]

    def _vz(self):
        return self._vxyz[:, 2]

    @_unit_conversion(dimension='L')
    @_mask
    def _R(self):
        return self._dump.extra_quantity('R')

    @_unit_conversion(dimension='L')
    @_mask
    def _r(self):
        return self._dump.extra_quantity('r')

    @_unit_conversion(dimension='L^3 M^-1 T^-2')
    def _G(self):
        return constants.gravitational_constant / (
            self._units.units.L ** 3 / self._units.units.M / self._units.units.T ** 2
        )

    @_unit_conversion(dimension='M')
    def _M(self):
        # TODO: assuming sink particle 0 is star
        warnings.warn('Assuming sink particle 0 is the central object')
        return self._sinks.arrays['m'][0]

    def _make_plot(self):

        if self._plot_render:
            self._render_image()

        if self._plot_vector:
            self._vector_image()

        if self._plot_particles:
            self._particle_scatter_plot()

        self._set_axis()
        self.set_axis_labels()
        self.set_title()

    def set_units(self, units, integrated_z=None):
        """
        Set units.

        Parameters
        ----------
        units : plonk.Units
            The new units to plot with.
        integrated_z : float, optional
            A length scale for the integrated z direction in projection
            plots.
        """
        self._new_units = units
        self._options.units.integrated_z = integrated_z
        if self._initialized:
            self._make_plot()

    def set_render_scale(self, render_scale=None):
        """
        Set render scale.

        Parameters
        ----------
        render_scale : str
            A string representing the render color scale, e.g.
            'linear' or 'log'.
        """

        if render_scale is None:
            render_scale = 'linear'

        if render_scale == 'log':
            norm = colors.SymLogNorm(1e-1 * self._options.render.render_max, clip=True)
        elif render_scale == 'linear':
            norm = colors.Normalize(
                vmin=self._options.render.render_min,
                vmax=self._options.render.render_max,
                clip=True,
            )
        else:
            raise ValueError("Unknown color render_scale: " + render_scale)

        self._norm = norm
        self._render_scale = render_scale

        if self._initialized:
            self.image.set_norm(norm)
            self._make_colorbar()

    def set_colormap(self, cmap):
        """
        Set colormap.

        Parameters
        ----------
        cmap : str
            Colormap from Matplotlib.
        """
        self._options.figure.colormap = cmap
        self.image.set_cmap(cmap)

    def set_render_range(self, vmin=None, vmax=None):
        """
        Set render range for colorbar.

        Parameters
        ----------
        vmin : float
            Minimum for the render colorbar.
        vmax : float
            Maximum for the render colorbar.
        """
        if vmin is not None and vmax is not None:
            self.image.set_clim(vmin=vmin, vmax=vmax)
            self._options.render.render_min = vmin
            self._options.render.render_max = vmax
        if vmin is not None:
            self.image.set_clim(vmin=vmin)
            self._options.render.render_min = vmin
        if vmax is not None:
            self.image.set_clim(vmax=vmax)
            self._options.render.render_max = vmax

    def set_particle_type(self, particle_types):
        """
        Set particle type(s) to visualize.

        Parameters
        ----------
        particle_types : int or container of ints
            Integer or container of integers representing the particle
            type.
        """

        if particle_types is None:
            particle_types = I_GAS

        if isinstance(particle_types, int):
            particle_types = set((particle_types,))
        elif isinstance(particle_types, (list, set, tuple)):
            particle_types = set(particle_types)

        if not particle_types.issubset(self._available_particle_types):
            print(f'Some of particle type {particle_types} not available')
            return

        if hasattr(self, '_particle_types'):
            if particle_types == self._particle_types:
                print(f'Particle types {particle_types} already plotted')
                return

        self._particle_types = particle_types
        self._particle_mask = np.logical_or.reduce(
            [self._particles.arrays['itype'][:] == i for i in particle_types]
        )

        if self._initialized:
            self._make_plot()

    def set_image_size(self, extent=None, size=None):
        """
        Set image size.

        Parameters
        ----------
        extent : list or numpy.ndarray
            Extent is the image size: [xmin, xmax, ymin, ymax].
        size : float
            Extent specified by a single value:
            [-size, size, -size, size].
        """

        if extent is not None:
            if np.all(extent == self._extent):
                print(f'Image window size already = {extent}')
                return
            self._extent = tuple(extent)
            if self._initialized:
                self._make_plot()
            return

        if size is not None:
            if np.all(size == np.abs(self._extent)):
                print(
                    'Image window size already = ' f'(-{size}, {size}, -{size}, {size})'
                )
                return
            self._extent = (-size, size, -size, size)
            if self._initialized:
                self._make_plot()
            return

    def _init_image_size(self):

        if self._extent is not None:
            if len(self._extent) != 4:
                raise ValueError('Extent must be like (xmin, xmax, ymin, ymax)')
        elif self._size is not None:
            self._extent = (-self._size, self._size, -self._size, self._size)
        else:
            _min = self._xyz[:, 0:2].min(axis=0)
            _max = self._xyz[:, 0:2].max(axis=0)
            self._extent = (_min[0], _max[0], _min[1], _max[1])

    def _render_image(self):

        self._render_label = self._options.figure.render_label
        if isinstance(self._render, str):
            if self._render_label is None:
                self._render_label = self._render
            scalars = list()
            [
                scalars.extend(item[:-1])
                for item in self._dump.available_extra_quantities
                if item[2] == 'scalar'
            ]
            if self._render in ['rho', 'dens', 'density']:
                render_data = self._density
            elif self._render == 'x':
                render_data = self._x()
            elif self._render == 'y':
                render_data = self._y()
            elif self._render == 'z':
                render_data = self._z()
            elif self._render == 'vx':
                render_data = self._vx()
            elif self._render == 'vy':
                render_data = self._vy()
            elif self._render == 'vz':
                render_data = self._vz()
            elif self._render in scalars:
                render_data = self._extra_quantity(self._render)
            elif self._render in self._particles.fields:
                render_data = self._particle_quantity(self._render)
                if render_data.ndim != 1:
                    raise ValueError(f'{self._render} is not scalar')
            else:
                symbol_dictionary = {
                    'x': self._x,
                    'y': self._y,
                    'z': self._z,
                    'vx': self._vx,
                    'vy': self._vy,
                    'vz': self._vz,
                    'G': self._G,
                    'M': self._M,
                    'R': self._R,
                    'r': self._r,
                }
                symbols = sympy.sympify(self._render).free_symbols
                symbols_as_str = set([str(s) for s in symbols])
                if not symbols_as_str.issubset(set(symbol_dictionary.keys())):
                    raise ValueError(f'Cannot interpret expression: {self._render}')
                f = sympy.utilities.lambdify(symbols, self._render, 'numpy')
                args = tuple(
                    [symbol_dictionary[key]() for key in [str(s) for s in symbols]]
                )
                render_data = f(*args)

        elif isinstance(self._render, np.ndarray):
            if self._render.ndim != 1:
                raise ValueError('Render array must be 1d')
            render_data = self._render
            if self._render_label is None:
                self._render_label = None

        else:
            raise ValueError('Cannot determine scalar data')

        if self._render_label is not None:
            print(f'Rendering scalar field "{self._render_label}" using Splash')
        else:
            print(f'Rendering scalar field using Splash')

        image_data = scalar_interpolation(
            self._xyz,
            self._h,
            self._interpolation_weights,
            render_data,
            self._particle_mass,
            self._extent[:2],
            self._extent[2:],
            **self._options.interpolation.__dict__,
            **self._options.units.__dict__,
        )

        self._render_image_matplotlib(image_data)

    def _render_image_matplotlib(self, image_data):

        if self._options.render.render_max is None:
            self._options.render.render_max = image_data.max()
        if self._render_fraction_max is not None:
            self._options.render.render_max = (
                image_data.max() * self._render_fraction_max
            )
        if self._options.render.render_min is None:
            self._options.render.render_min = image_data.min()

        self.set_render_scale(self._options.render.render_scale)

        self._cmap = self._options.figure.colormap

        self.image = self.axis.imshow(
            image_data,
            norm=self._norm,
            origin='lower',
            extent=self._extent,
            cmap=self._cmap,
        )

        self._cax = self._options.figure.cbar_axis
        if not hasattr(self, 'colorbar'):
            if self._options.figure.colorbar:
                self._make_colorbar()
            else:
                self.colorbar = None
        else:
            self._make_colorbar()

    def _make_colorbar(self):
        if hasattr(self, 'colorbar'):
            if self.colorbar is not None:
                self.colorbar.remove()
        if self._cax is None:
            divider = make_axes_locatable(self.axis)
            cax = divider.append_axes("right", size="5%", pad=0.05)
            self.colorbar = self.figure.colorbar(self.image, cax)
        else:
            self.colorbar = self._cax.colorbar(self.image)
        if self._render_label is not None:
            try:
                self.colorbar.set_label_text(self._render_label)
            except AttributeError:
                self.colorbar.set_label(self._render_label)

    def _vector_image(self):

        if isinstance(self._vector, str):
            self._vector_label = self._vector
            vectors = list()
            [
                vectors.extend(item[:-1])
                for item in self._dump.available_extra_quantities
                if item[2] == 'vector'
            ]
            if self._vector in ['v', 'vel', 'velocity']:
                try:
                    vector_data = self._vxyz
                except Exception:
                    raise ValueError('Velocity not available in dump')
            elif self._vector in vectors:
                vector_data = self._extra_quantity(self._vector)
            else:
                try:
                    vector_data = self._particle_quantity(self._vector)
                    if vector_data.ndim != 2 and vector_data.shape[1] != 3:
                        raise ValueError(
                            f'{self._vector} does not have correct dimensions'
                        )
                except Exception:
                    raise ValueError(
                        f'Cannot determine vector quantity: {self._vector}'
                    )
        elif isinstance(self._vector, np.ndarray):
            if self._vector.ndim != 2:
                raise ValueError(f'{self._vector} is not 2-dimensional')
            if self._vector.shape[1] != 3:
                raise ValueError('Vector array must have shape (npart, 3)')
            vector_data = self._vector
            self._vector_label = None

        else:
            raise ValueError('Cannot determine vector data')

        if self._vector_label is not None:
            print(f'Plotting vector field "{self._vector_label}" using Splash')
        else:
            print(f'Plotting vector field using Splash')

        vector_data = vector_interpolation(
            self._xyz,
            self._h,
            self._interpolation_weights,
            vector_data,
            self._extent[:2],
            self._extent[2:],
            **self._options.interpolation.__dict__,
            **self._options.units.__dict__,
        )

        self._render_vector_matplotlib(vector_data)

    def _render_vector_matplotlib(self, vector_data):

        xvector_data = vector_data[0]
        yvector_data = vector_data[1]
        _xrange, _yrange = self._extent[:2], self._extent[2:]
        X, Y = np.meshgrid(
            np.linspace(*_xrange, len(xvector_data)),
            np.linspace(*_yrange, len(yvector_data)),
        )

        vector_color = self._options.vector.vector_color
        if self._render:
            vector_color = 'white'
        stride = self._options.vector.stride

        self.stream = None
        self.quiver = None
        if self._options.vector.stream:
            self.stream = self.axis.streamplot(
                X[::stride, ::stride],
                Y[::stride, ::stride],
                xvector_data[::stride, ::stride],
                yvector_data[::stride, ::stride],
                color=vector_color,
            )
        else:
            self.quiver = self.axis.quiver(
                X[::stride, ::stride],
                Y[::stride, ::stride],
                xvector_data[::stride, ::stride],
                yvector_data[::stride, ::stride],
                color=vector_color,
            )

        self.axis.set_aspect('equal', 'box')

    def _particle_scatter_plot(self):
        marker_size = 0.01
        self.axis.scatter(self._x(), self._y(), s=marker_size, c='k')
        self.axis.set_aspect('equal', 'box')

    def _init_frame_rotation(self):
        rotation_axis = self._options.rotation.rotation_axis
        rotation_angle = self._options.rotation.rotation_angle
        position_angle = self._position_angle
        inclination = self._inclination
        self._rotate_frame = False

        if (rotation_axis is not None or rotation_angle is not None) and (
            position_angle is not None and inclination is not None
        ):
            raise ValueError(
                'Cannot set rotation_axis/rotation_angle and '
                ' position_angle/inclination at the same time'
            )

        if rotation_axis is not None:
            if rotation_angle is not None:
                self._rotate_frame = True
                rotation_axis = normalize_vector(rotation_axis)
            else:
                raise ValueError('Must specify rotation_angle')
            if isinstance(rotation_axis, list):
                rotation_axis = np.array(rotation_axis)
            rotation_axis = normalize_vector(rotation_axis)

        if rotation_angle is not None and rotation_axis is None:
            raise ValueError('Must specify rotation_axis')

        if position_angle is not None:
            if inclination is not None:
                self._rotate_frame = True
                rotation_angle = inclination
                rotation_axis = np.array(
                    [np.cos(position_angle), np.sin(position_angle), 0]
                )
            else:
                raise ValueError('Must specify inclination')

        if inclination is not None and position_angle is None:
            raise ValueError('Must specify position_angle')

        self._options.rotation.rotation_axis = rotation_axis
        self._options.rotation.rotation_angle = rotation_angle

        if self._rotate_frame:
            self.rotate_frame(rotation_axis, rotation_angle)

    def rotate_frame(self, axis, angle):
        """
        Rotate viewing frame.

        Specify an axis of rotation and an angle to rotate. This
        rotation is a tranformation on the original frame specified
        in the data.

        Parameters
        ----------
        axis : list or numpy.ndarray
            Rotation axis for frame rotation as a vector [x, y, z].
        angle : float
            Rotation angle in radians for frame rotation.
        """

        if (
            self._options.rotation.rotation_axis is not None
            and self._options.rotation.rotation_angle is not None
        ):
            if (
                np.all(np.array(axis) == self._options.rotation.rotation_axis)
                and angle == self._options.rotation.rotation_angle
            ):
                print(f'Frame already has the specified rotation')
                return

        if axis is not None and angle is not None:
            self._options.rotation.rotation_axis = axis
            self._options.rotation.rotation_angle = angle
            self._rotate_frame = True
        else:
            raise ValueError('Must specify by axis and angle for rotation')

        print(
            f'Rotating {angle*180/np.pi:.0f} deg around '
            f'[{axis[0]:.2f},'
            f' {axis[1]:.2f},'
            f' {axis[2]:.2f}]'
        )

        if self._initialized:
            self._make_plot()

    def _set_axis(self):

        self.axis.set_xlim(self._extent[0], self._extent[1])
        self.axis.set_ylim(self._extent[2], self._extent[3])

    def set_axis_labels(self, xlabel=None, ylabel=None):
        """
        Set axis labels.

        Parameters
        ----------
        xlabel : str
            Label for the x axis.
        ylabel : str
            Label for the y axis.
        """

        if not self._rotate_frame:
            self.axis.set_xlabel('x')
            self.axis.set_ylabel('y')

        if xlabel is not None:
            self.axis.set_xlabel(xlabel)
        if ylabel is not None:
            self.axis.set_ylabel(ylabel)

    def set_title(self, title=None):
        """
        Set title.

        Parameters
        ----------
        title : str
            Figure title.
        """

        if title is None:
            title = self._options.figure.title

        if title is not None:
            self.axis.set_title(title)

    def options_todict(self):
        return {key: value.__dict__ for key, value in self._options.__dict__.items()}


class VisualizationIterator:
    """
    Iterator over Visualization object.

    Parameters
    ----------
    dumps : list of Dump
        A list of plonk.Dump objects to visualize.
    **kwargs
        The keyword arguments to pass to Visualization.

    Examples
    --------
    Go forwards and backwards through visualizations.

    >>> viz_iter = VisualizationIterator(
    ...     dumps=sim.dumps, render=render,
    ...     )
    >>> viz_iter.next()
    >>> viz_iter.previous()
    """

    def __init__(self, dumps, **kwargs):
        self._dumps = dumps
        self._len = len(dumps)
        self._where = 0
        self.options = kwargs
        self.visualization = Visualization(dump=dumps[0], **kwargs)
        self._forwards = self._viz_iter(dumps[1:])
        self._backwards = None

    def _viz_iter(self, dumps):
        for dump in dumps:
            yield Visualization(dump=dump, **self.options)

    def next(self):
        if self._where < self._len - 1:
            self.visualization = self._forwards.__next__()
            self._where += 1
            self._forwards = self._viz_iter(self._dumps[self._where + 1 :])
            self._backwards = self._viz_iter(self._dumps[self._where - 1 :: -1])
        else:
            print('At the end.')

    def previous(self):
        if self._where > 0:
            self.visualization = self._backwards.__next__()
            self._where -= 1
            self._forwards = self._viz_iter(self._dumps[self._where + 1 :])
            self._backwards = self._viz_iter(self._dumps[self._where - 1 :: -1])
        else:
            print('At the start.')
