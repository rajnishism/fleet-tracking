"""
route_deviation.py (v2)
Progress-based route corridor with multi-severity alerts and wrong-direction detection.

vs edge/processing/route_deviation.py (v1):
- Stateful RouteTracker class instead of a stateless function.
  - Tracks the furthest segment index the truck has reached (route progress).
  - Searches forward from that index instead of scanning all segments, preventing
    a truck that has passed segment 5 from "snapping back" to a closer segment 1.
- Two severity levels:
    WARNING  — distance > DEVIATION_THRESHOLD_M  (configurable, default 50 m)
    CRITICAL — distance > 2 × DEVIATION_THRESHOLD_M
- Wrong-direction detection: if the nearest segment index falls behind the known
  progress for BACKWARD_CONFIRM_COUNT consecutive readings, a WRONG_DIRECTION
  alert is fired (e.g. truck reversing down a one-way haul road).
"""

import json
import os
import logging
from typing import Optional

from utils.haversine import point_to_segment_distance, haversine

logger = logging.getLogger(__name__)

# ─── Config ───────────────────────────────────────────────────────────────────
_config_dir = os.path.join(os.path.dirname(__file__), "..", "..", "edge", "config")

with open(os.path.join(_config_dir, "system_config.json")) as f:
    _sys = json.load(f)

with open(os.path.join(_config_dir, "route_polygon.json")) as f:
    _route = json.load(f)

DEVIATION_THRESHOLD_M  = _sys.get("deviation_threshold_m", 50.0)
CRITICAL_THRESHOLD_M   = DEVIATION_THRESHOLD_M * 2.0
HAUL_ROAD: list[tuple[float, float]] = [tuple(pt) for pt in _route["haul_road"]]

# Number of consecutive readings with decreasing progress before a WRONG_DIRECTION alert
BACKWARD_CONFIRM_COUNT = 3


# ─── Stateful tracker ─────────────────────────────────────────────────────────

class RouteTracker:
    """
    Per-vehicle route progress tracker.

    Instantiate one RouteTracker per vehicle in VehicleState (main.py).

    vs v1's check_deviation(lat, lon):
    - check() remembers how far along the route the truck has travelled so it
      only considers segments at-or-ahead of the truck's current position.
    - This avoids false "on-route" readings when the truck deviates near an
      earlier part of the road it already passed.
    """

    def __init__(self) -> None:
        self._progress_idx: int = 0   # Furthest segment the truck has reached
        self._backward_count: int = 0  # Consecutive backward-progress readings

    def check(
        self, lat: float, lon: float
    ) -> tuple[float, int, Optional[dict]]:
        """
        Evaluate the vehicle's position against the haul road.

        Returns:
            (distance_from_route_m, nearest_segment_idx, alert_or_None)

        alert types:
            ROUTE_DEVIATION  — off-road (WARNING or CRITICAL severity key)
            WRONG_DIRECTION  — sustained backward travel
        """
        # Allow a small look-back so a truck can reverse a little without
        # immediately triggering wrong-direction (e.g. mine loading bay manoeuvre).
        search_start = max(0, self._progress_idx - 2)

        min_dist    = float("inf")
        nearest_idx = self._progress_idx

        for i in range(search_start, len(HAUL_ROAD) - 1):
            ax, ay = HAUL_ROAD[i]
            bx, by = HAUL_ROAD[i + 1]
            d = point_to_segment_distance(lat, lon, ax, ay, bx, by)
            if d < min_dist:
                min_dist    = d
                nearest_idx = i

        # ── Update forward progress ───────────────────────────────────────────
        if nearest_idx > self._progress_idx:
            self._progress_idx  = nearest_idx
            self._backward_count = 0
        elif nearest_idx < self._progress_idx - 1:
            # More than one segment behind — potential backward travel
            self._backward_count += 1
        else:
            self._backward_count = 0

        # ── Build alert ───────────────────────────────────────────────────────
        alert: Optional[dict] = None

        if self._backward_count >= BACKWARD_CONFIRM_COUNT:
            alert = {
                "type":        "WRONG_DIRECTION",
                "message":     (
                    f"Vehicle travelling backward on haul road "
                    f"(at segment {nearest_idx}, expected ≥{self._progress_idx})"
                ),
                "segment_idx": nearest_idx,
            }
            self._backward_count = 0  # Reset so we don't spam the alert

        elif min_dist > CRITICAL_THRESHOLD_M:
            alert = {
                "type":       "ROUTE_DEVIATION",
                "severity":   "CRITICAL",
                "message":    f"Vehicle {min_dist:.0f}m off haul road — CRITICAL",
                "distance_m": round(min_dist, 1),
            }

        elif min_dist > DEVIATION_THRESHOLD_M:
            alert = {
                "type":       "ROUTE_DEVIATION",
                "severity":   "WARNING",
                "message":    f"Vehicle {min_dist:.0f}m off haul road",
                "distance_m": round(min_dist, 1),
            }

        return min_dist, nearest_idx, alert

    def reset(self) -> None:
        """Reset progress — call if the truck returns to the route start."""
        self._progress_idx   = 0
        self._backward_count = 0
