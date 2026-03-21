"""
route_deviation.py
Detects when a vehicle strays too far from the designated haul road.
"""

import json
import os
import logging
from typing import Optional

from utils.haversine import point_to_segment_distance, haversine

logger = logging.getLogger(__name__)

# Load config
_config_dir = os.path.join(os.path.dirname(__file__), "..", "config")

with open(os.path.join(_config_dir, "system_config.json")) as f:
    _sys_config = json.load(f)

with open(os.path.join(_config_dir, "route_polygon.json")) as f:
    _route_config = json.load(f)

DEVIATION_THRESHOLD_M = _sys_config.get("deviation_threshold_m", 50.0)
route_list = _route_config.get("haul_road", [])
# Handle edge-case where array is wrapped in a 2D array
if len(route_list) > 0 and isinstance(route_list[0], list) and (len(route_list[0]) > 0 and isinstance(route_list[0][0], dict)):
    route_list = route_list[0]

HAUL_ROAD: list[tuple[float, float]] = []
for pt in route_list:
    if isinstance(pt, dict):
        HAUL_ROAD.append((float(pt.get("lat", 0.0)), float(pt.get("lon", 0.0))))
    else:
        HAUL_ROAD.append((float(pt[0]), float(pt[1])))


def closest_distance_to_route(lat: float, lon: float, route: list[tuple[float, float]]) -> float:
    """Return the minimum distance (metres) from a point to any route segment."""
    if len(route) < 2:
        if not route:
            return float("inf")
        return haversine(lat, lon, route[0][0], route[0][1])

    min_dist = float("inf")
    for i in range(len(route) - 1):
        ax, ay = route[i]
        bx, by = route[i + 1]
        d = point_to_segment_distance(lat, lon, ax, ay, bx, by)
        if d < min_dist:
            min_dist = d
    return min_dist


def check_deviation(lat: float, lon: float) -> tuple[float, Optional[dict]]:
    """
    Check if vehicle position deviates from the haul road.

    Returns:
        (distance_from_route_m, alert_dict_or_None)
    """
    dist = closest_distance_to_route(lat, lon, HAUL_ROAD)
    if dist > DEVIATION_THRESHOLD_M:
        alert = {
            "type": "ROUTE_DEVIATION",
            "message": f"Vehicle {dist:.0f}m off haul road",
            "distance_m": round(dist, 1),
        }
        return dist, alert
    return dist, None
