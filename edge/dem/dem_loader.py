"""
dem_loader.py
Load a DEM (Digital Elevation Model) GeoTIFF file.

Expects a file at dem/terrain.tif. If rasterio is not installed or the file
is missing, this module gracefully degrades.
"""

import os
import logging

logger = logging.getLogger(__name__)

_DEM_PATH = os.path.join(os.path.dirname(__file__), "terrain.tif")
_dataset = None


def load_dem():
    """Load the DEM dataset. Returns the rasterio dataset or None."""
    global _dataset
    if _dataset is not None:
        return _dataset

    if not os.path.exists(_DEM_PATH):
        logger.warning(f"DEM file not found at {_DEM_PATH} – terrain analysis disabled")
        return None

    try:
        import rasterio
        _dataset = rasterio.open(_DEM_PATH)
        logger.info(f"DEM loaded: {_DEM_PATH} ({_dataset.width}x{_dataset.height})")
        return _dataset
    except ImportError:
        logger.warning("rasterio not installed – terrain analysis disabled")
        return None
    except Exception as e:
        logger.error(f"Failed to load DEM: {e}")
        return None
