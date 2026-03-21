"""
distance_speed.py (v2)
Distance, speed, bearing, and acceleration from Kalman-smoothed GPS points.

vs edge/processing/distance_speed.py (v1):
- Input coordinates are expected to already be Kalman-filtered (done in main.py)
  so haversine distance is computed on cleaner positions, reducing speed spikes
  from GPS jitter.
- Returns a MotionData named tuple instead of bare floats — callers get bearing
  and acceleration without extra function calls.
- Adds bearing() to compute forward azimuth (compass heading, 0–360°), which is
  sent to the dashboard to draw directional truck icons on the map.
- Acceleration (m/s²) is forwarded to the physics fuel model for tractive-effort
  estimation.
"""

import math
import logging
from typing import NamedTuple

from utils.haversine import haversine

logger = logging.getLogger(__name__)


class MotionData(NamedTuple):
    """Rich motion snapshot computed between two consecutive GPS fixes."""
    distance_m: float        # metres travelled since last fix
    speed_kmh: float         # derived speed (km/h)
    bearing_deg: float       # forward azimuth 0–360°, clockwise from north
    acceleration_ms2: float  # positive = speeding up, negative = braking


def bearing(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    Compute the initial forward azimuth (bearing) from point 1 to point 2.

    Returns degrees in the range [0, 360), clockwise from true north.
    """
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    dlam = math.radians(lon2 - lon1)

    x = math.sin(dlam) * math.cos(phi2)
    y = math.cos(phi1) * math.sin(phi2) - math.sin(phi1) * math.cos(phi2) * math.cos(dlam)
    return (math.degrees(math.atan2(x, y)) + 360.0) % 360.0


def compute_motion(
    lat: float,
    lon: float,
    last_lat: float,
    last_lon: float,
    duration_sec: float,
    prev_speed_kmh: float = 0.0,
) -> MotionData:
    """
    Compute distance, speed, bearing, and acceleration between two GPS fixes.

    Both position pairs should already be Kalman-filtered before being passed
    here (filtering happens in VehicleState.update() in main.py).

    Args:
        lat, lon:           Current filtered position.
        last_lat, last_lon: Previous filtered position.
        duration_sec:       Elapsed time between fixes (seconds).
        prev_speed_kmh:     Speed at the previous fix (for acceleration calc).

    Returns:
        MotionData named tuple.
    """
    if duration_sec <= 0:
        return MotionData(0.0, 0.0, 0.0, 0.0)

    dist_m    = haversine(last_lat, last_lon, lat, lon)
    speed_kmh = (dist_m / duration_sec) * 3.6
    hdg       = bearing(last_lat, last_lon, lat, lon)

    # Δv (m/s) / Δt (s) = acceleration (m/s²)
    delta_v_ms = (speed_kmh - prev_speed_kmh) / 3.6
    accel_ms2  = delta_v_ms / duration_sec

    return MotionData(
        distance_m      = round(dist_m,    3),
        speed_kmh       = round(speed_kmh, 3),
        bearing_deg     = round(hdg,        1),
        acceleration_ms2= round(accel_ms2,  4),
    )
