"""Functions for visualization."""


import numpy as np


def get_extent_from_percentile(
    snap,
    x: str,
    y: str,
    percentile: float = 99,
    x_center_on: float = None,
    y_center_on: float = None,
    edge_factor: float = None,
):
    """Get extent from percentile.

    Parameters
    ----------
    x
        The "x" coordinate.
    y
        The "x" coordinate.
    percentile : optional
        The percentile used in the calculation. Default is 99.
    x_center_on : optional
        Center on some x-value. Default is None.
    y_center_on : optional
        Center on some y-value. Default is None.
    edge_factor : optional
        Add extra spacing to extent. E.g. to add extra 5%, set this
        value to 0.05. Default is None.

    Returns
    -------
    tuple
        The extent of the box as (xmin, xmax, ymin, ymax).
    """
    pl, pr = (100 - percentile) / 2, percentile + (100 - percentile) / 2
    xlim = np.percentile(snap[x], [pl, pr])
    ylim = np.percentile(snap[y], [pl, pr])

    if x_center_on is not None:
        xlim += x_center_on - xlim.mean()
    if y_center_on is not None:
        ylim += y_center_on - ylim.mean()

    if edge_factor is not None:
        dx = xlim[1] - xlim[0]
        dy = ylim[1] - ylim[0]
        xlim += (-dx * edge_factor, dx * edge_factor)
        ylim += (-dy * edge_factor, dy * edge_factor)
        return (xlim[0], xlim[1], ylim[0], ylim[1])

    return (xlim[0], xlim[1], ylim[0], ylim[1])
