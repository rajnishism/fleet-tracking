"""
terrain_analysis.py
DEM-based elevation and slope analysis for vehicle positions.

Requires a DEM GeoTIFF file at dem/terrain.tif.
This module is a placeholder – it will become functional once a DEM file is provided.
"""

import logging
from typing import Optional

logger = logging.getLogger(__name__)

# Optional import: rasterio may not be installed in all environments
try:
    from dem.dem_loader import load_dem
    from dem.elevation_lookup import get_elevation
    _DEM_AVAILABLE = True
except ImportError:
    _DEM_AVAILABLE = False
    logger.info("DEM modules not available – terrain analysis disabled")


def analyse_terrain(lat: float, lon: float) -> Optional[dict]:
    """
    Look up elevation and slope at a GPS position using the DEM.

    Returns:
        dict with 'elevation_m' and 'slope_deg', or None if DEM is unavailable.
    """
    if not _DEM_AVAILABLE:
        return None

    try:
        elevation = get_elevation(lat, lon)
        if elevation is not None:
            return {
                "elevation_m": round(elevation, 1),
            }
    except Exception as e:
        logger.warning(f"Terrain analysis failed: {e}")

    return None
