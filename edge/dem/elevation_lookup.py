"""
elevation_lookup.py
Lookup elevation at a given lat/lon from the loaded DEM.
"""

import logging
from typing import Optional

from dem.dem_loader import load_dem

logger = logging.getLogger(__name__)


def get_elevation(lat: float, lon: float) -> Optional[float]:
    """
    Return the elevation (metres) at the given GPS coordinate.

    Returns None if the DEM is not loaded or the point is outside the raster.
    """
    dataset = load_dem()
    if dataset is None:
        return None

    try:
        # Convert lat/lon to raster row/col
        row, col = dataset.index(lon, lat)
        if 0 <= row < dataset.height and 0 <= col < dataset.width:
            elevation = dataset.read(1)[row, col]
            # Filter nodata values
            nodata = dataset.nodata
            if nodata is not None and elevation == nodata:
                return None
            return float(elevation)
    except Exception as e:
        logger.debug(f"Elevation lookup failed for ({lat}, {lon}): {e}")

    return None
