"""
distance_speed.py
Distance and speed calculations between GPS points.
"""

import logging
from utils.haversine import haversine

logger = logging.getLogger(__name__)


def calculate_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Return distance in metres between two GPS coordinates."""
    return haversine(lat1, lon1, lat2, lon2)


def calculate_speed(distance_m: float, time_delta_sec: float) -> float:
    """Return speed in km/h given distance (metres) and time (seconds)."""
    if time_delta_sec <= 0:
        return 0.0
    return (distance_m / time_delta_sec) * 3.6


def calculate_acceleration(
    speed_current_kmh: float,
    speed_previous_kmh: float,
    time_delta_sec: float,
) -> float:
    """Return acceleration in m/s² given two speeds (km/h) and time delta (sec)."""
    if time_delta_sec <= 0:
        return 0.0
    delta_ms = (speed_current_kmh - speed_previous_kmh) / 3.6  # km/h → m/s
    return delta_ms / time_delta_sec
