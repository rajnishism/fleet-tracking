"""
simulator.py (v2)
Multi-vehicle GPS simulator with Gaussian positional noise and shared queue output.

vs edge/simulator.py (v1):
- v1 returns a single generator for one truck (configured in vehicle_config.json).
- v2 supports a "vehicles" list inside vehicle_config.json (multiple trucks), each
  running in its own daemon thread and pushing data to a shared queue.
- Falls back to v1-style single-vehicle config so it works without any config changes.
- Adds Gaussian GPS noise (σ ≈ 3 m) to every fix to simulate real receiver jitter,
  which exercises the Kalman filter in processing/distance_speed.py.
- The fuel_anomaly scenario drives harder speed swings (0 ↔ 60 km/h) to trigger
  the physics-based FuelAnomalyDetector more visibly than v1's 0 ↔ 40 km/h.

Usage — add to vehicle_config.json to run multiple trucks:

    {
      "vehicles": [
        { "vehicle_id": "Truck_1", "scenario": "normal" },
        { "vehicle_id": "Truck_2", "scenario": "deviation" },
        { "vehicle_id": "Truck_3", "scenario": "fuel_anomaly" }
      ]
    }

Or keep the existing v1 format untouched — run_multi_simulator() handles both.
"""

import json
import os
import sys
import time
import random
import threading
import queue
import logging
from typing import Optional

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

# ─── Config ───────────────────────────────────────────────────────────────────
_config_dir = os.path.join(os.path.dirname(__file__), "..", "edge", "config")

with open(os.path.join(_config_dir, "route_polygon.json")) as f:
    _route_data = json.load(f)
HAUL_ROAD = [tuple(pt) for pt in _route_data["haul_road"]]

with open(os.path.join(_config_dir, "system_config.json")) as f:
    _sys_config = json.load(f)
STEPS_PER_SEGMENT = _sys_config.get("steps_per_segment", 20)

# Gaussian noise: σ = 0.00003° ≈ 3 m — typical consumer GPS receiver accuracy
GPS_NOISE_STD_DEG: float = 0.00003


# ─── Path helpers ─────────────────────────────────────────────────────────────

def _interpolate_path(
    waypoints: list[tuple[float, float]], steps: int
) -> list[tuple[float, float]]:
    """Linearly interpolate waypoints into a dense point list."""
    path: list[tuple[float, float]] = []
    for i in range(len(waypoints) - 1):
        lat1, lon1 = waypoints[i]
        lat2, lon2 = waypoints[i + 1]
        for j in range(steps):
            t = j / steps
            path.append((lat1 + t * (lat2 - lat1), lon1 + t * (lon2 - lon1)))
    path.append(waypoints[-1])
    return path


def _now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _add_gps_noise(lat: float, lon: float) -> tuple[float, float]:
    """
    Perturb coordinates with Gaussian noise to simulate GPS receiver jitter.
    This is the key addition vs v1 (which uses exact interpolated positions).
    """
    return (
        lat + random.gauss(0.0, GPS_NOISE_STD_DEG),
        lon + random.gauss(0.0, GPS_NOISE_STD_DEG),
    )


# ─── Per-vehicle thread ───────────────────────────────────────────────────────

def _vehicle_thread(
    vehicle_cfg: dict,
    out_queue: "queue.Queue[dict]",
    interval_sec: float,
) -> None:
    """
    Generate GPS fixes for one vehicle and push each fix to the shared queue.
    Runs as a daemon thread — exits when the main process exits.
    """
    vehicle_id = vehicle_cfg.get("vehicle_id", "Truck_Unknown")
    scenario   = vehicle_cfg.get("scenario", "normal")
    logger.info(f"[{vehicle_id}] Simulator thread started (scenario={scenario})")

    path = _interpolate_path(HAUL_ROAD, STEPS_PER_SEGMENT)
    idx  = 0

    while True:
        lat, lon = path[idx % len(path)]
        idx += 1

        # ── Speed by scenario ─────────────────────────────────────────────────
        if scenario == "normal":
            speed = 35.0 + random.uniform(-3.0, 3.0)

        elif scenario == "idle":
            # First half of route: driving; second half: stopped
            speed = 0.0 if idx > len(path) // 2 else 30.0 + random.uniform(-2.0, 2.0)

        elif scenario == "deviation":
            # Gradually drift the truck off the road
            drift = min(idx / len(path), 1.0) * 0.003
            lat  += drift
            speed = 25.0 + random.uniform(-10.0, 10.0)

        elif scenario == "fuel_anomaly":
            # Hard acceleration pattern: 0 ↔ 60 km/h every 4 readings
            # (wider swing than v1's 0 ↔ 40 to better exercise physics model)
            speed = 60.0 if (idx % 4 < 2) else 0.0

        else:
            speed = 30.0

        speed = max(0.0, round(speed, 2))

        # Add GPS noise (v2 addition)
        lat, lon = _add_gps_noise(lat, lon)

        fix = {
            "vehicle_id": vehicle_id,
            "latitude":   round(lat, 6),
            "longitude":  round(lon, 6),
            "speed_kmh":  speed,
            "timestamp":  _now_iso(),
        }

        try:
            out_queue.put(fix, timeout=5.0)
        except queue.Full:
            logger.warning(f"[{vehicle_id}] Output queue full — dropping fix")

        time.sleep(interval_sec)


# ─── Public entry point ───────────────────────────────────────────────────────

def run_multi_simulator(interval_sec: float = 2.0) -> "queue.Queue[dict]":
    """
    Start one daemon thread per vehicle and return the shared data queue.

    Config format detection:
      - If vehicle_config.json has a "vehicles" list  → multi-vehicle (v2 style).
      - If it has a single "vehicle" object            → single-vehicle (v1 style).
    Both formats are handled transparently.
    """
    vehicle_config_path = os.path.join(_config_dir, "vehicle_config.json")
    with open(vehicle_config_path) as f:
        cfg = json.load(f)

    if "vehicles" in cfg:
        vehicles = cfg["vehicles"]
    else:
        vehicles = [cfg.get("vehicle", {})]

    out_queue: "queue.Queue[dict]" = queue.Queue(maxsize=500)

    for v in vehicles:
        t = threading.Thread(
            target=_vehicle_thread,
            args=(v, out_queue, interval_sec),
            daemon=True,
        )
        t.start()

    ids = [v.get("vehicle_id", "?") for v in vehicles]
    logger.info(f"Multi-vehicle simulator running: {ids}")
    return out_queue


# ─── Standalone test ──────────────────────────────────────────────────────────

if __name__ == "__main__":
    q = run_multi_simulator(interval_sec=0.5)
    for _ in range(10):
        print(q.get())
