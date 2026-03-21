"""
main.py (v2)
Multi-vehicle edge pipeline using per-vehicle state objects and a shared queue.

vs edge/main.py (v1):
- v1 spins up one pipeline thread per vehicle and tracks idle_start_time,
  stop_start_count, speed_history as bare local variables inside run_pipeline().
- v2 introduces VehicleState — a dataclass that holds all stateful processing
  objects (Kalman filter, RouteTracker, IdleDetector, FuelAnomalyDetector) for
  one vehicle.  A single pipeline thread drains a shared queue; per-vehicle state
  is looked up from a dict keyed by vehicle_id.  This means:
    • New vehicles are registered automatically on first fix — no config change.
    • The pipeline never needs to know how many vehicles exist in advance.
    • State is isolated: a crash for Truck_2 cannot corrupt Truck_1's counters.
- Kalman-filters raw GPS before passing coordinates to motion/route calculations.
- Passes acceleration from MotionData to the physics fuel model.
- Enriched records include two new fields: bearing_deg and total_distance_m.
- Cloud/storage imports are pulled directly from edge/ to avoid duplication.

Usage:
    python main.py --mode simulate    # uses edge_v2/simulator.py (multi-vehicle)
    python main.py --mode hardware    # reads from real GPS module
"""

import argparse
import json
import os
import sys
import threading
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

# ─── Path setup ───────────────────────────────────────────────────────────────
# Add edge_v2 root so local imports resolve.
_THIS_DIR  = os.path.dirname(os.path.abspath(__file__))
_EDGE_DIR  = os.path.join(_THIS_DIR, "..", "edge")

sys.path.insert(0, _THIS_DIR)
sys.path.insert(1, _EDGE_DIR)   # Re-use cloud/ and storage/ from v1 unchanged

# ─── v2 processing modules ────────────────────────────────────────────────────
from processing.distance_speed import compute_motion
from processing.route_deviation import RouteTracker
from processing.idle_detection import IdleDetector
from processing.fuel_model import FuelAnomalyDetector, calculate_fuel_usage
from utils.filters import GPSKalmanFilter2D

# ─── v1 cloud / storage (re-used, no duplication) ────────────────────────────
from cloud.api_client import send_to_backend
from cloud.sync_service import sync_loop
from storage.save_local import save_gps_record

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

# ─── Config ───────────────────────────────────────────────────────────────────
_config_path = os.path.join(_EDGE_DIR, "config", "system_config.json")
with open(_config_path) as f:
    SYS_CONFIG = json.load(f)

SEND_INTERVAL_SEC = float(
    os.getenv("SEND_INTERVAL", SYS_CONFIG.get("send_interval_sec", 2))
)


# ─── Per-vehicle state ────────────────────────────────────────────────────────

@dataclass
class VehicleState:
    """
    All stateful processing objects for a single vehicle, bundled together.

    vs v1 (loose local variables in run_pipeline()):
    One instance per vehicle_id.  Stored in _vehicle_registry dict so the
    single pipeline thread can process any vehicle without prior configuration.
    """
    vehicle_id: str

    # Kalman filter smooths raw GPS before distance/speed calculation
    kalman: GPSKalmanFilter2D = field(default_factory=GPSKalmanFilter2D)

    # Processing modules (v2 stateful objects replacing v1 loose variables)
    route_tracker:   RouteTracker        = field(default_factory=RouteTracker)
    idle_detector:   IdleDetector        = field(default_factory=IdleDetector)
    fuel_detector:   FuelAnomalyDetector = field(default_factory=FuelAnomalyDetector)

    # Kinematic history
    last_lat:        Optional[float] = None
    last_lon:        Optional[float] = None
    last_ts:         Optional[float] = None
    prev_speed_kmh:  float = 0.0
    total_distance_m: float = 0.0


# Global vehicle registry: vehicle_id → VehicleState
_registry: dict[str, VehicleState] = {}


def _get_state(vehicle_id: str) -> VehicleState:
    """Return existing state or create a new one for a first-seen vehicle."""
    if vehicle_id not in _registry:
        _registry[vehicle_id] = VehicleState(vehicle_id=vehicle_id)
        logger.info(f"Registered new vehicle: {vehicle_id}")
    return _registry[vehicle_id]


# ─── Processing pipeline ─────────────────────────────────────────────────────

def process(gps_data: dict) -> dict:
    """
    Run one GPS fix through the full v2 pipeline for its vehicle.

    Pipeline steps:
      1. Kalman-filter raw lat/lon  →  filtered position
      2. compute_motion()           →  distance, speed, bearing, acceleration
      3. RouteTracker.check()       →  deviation + wrong-direction alerts
      4. IdleDetector.update()      →  hysteresis idle alert
      5. FuelAnomalyDetector.update() → EMA spike alert
      6. calculate_fuel_usage()     →  physics-based litres consumed
    """
    vid       = gps_data["vehicle_id"]
    raw_lat   = gps_data["latitude"]
    raw_lon   = gps_data["longitude"]
    ts_str    = gps_data["timestamp"]

    try:
        now_ts = datetime.fromisoformat(ts_str.replace("Z", "+00:00")).timestamp()
    except Exception:
        now_ts = time.time()

    state  = _get_state(vid)
    alerts = []

    # 1. Kalman filter — smooth noisy GPS fix
    dt = (now_ts - state.last_ts) if state.last_ts is not None else 1.0
    filtered_lat, filtered_lon = state.kalman.update(raw_lat, raw_lon, max(dt, 0.01))

    # 2. Motion metrics (only once we have a previous filtered position)
    distance_m      = 0.0
    speed_kmh       = gps_data.get("speed_kmh", 0.0)
    acceleration_ms2 = 0.0
    bearing_deg      = 0.0

    if state.last_lat is not None and dt > 0:
        motion = compute_motion(
            filtered_lat, filtered_lon,
            state.last_lat, state.last_lon,
            dt,
            prev_speed_kmh=state.prev_speed_kmh,
        )
        distance_m       = motion.distance_m
        speed_kmh        = motion.speed_kmh
        bearing_deg      = motion.bearing_deg
        acceleration_ms2 = motion.acceleration_ms2
        state.total_distance_m += distance_m

    state.prev_speed_kmh = speed_kmh

    # 3. Route deviation (stateful progress tracker)
    dist_from_route, segment_idx, route_alert = state.route_tracker.check(
        filtered_lat, filtered_lon
    )
    if route_alert:
        alerts.append(route_alert)
        logger.warning(f"[{vid}] {route_alert['message']}")

    # 4. Idle detection (hysteresis state machine)
    idle_state, idle_alert = state.idle_detector.update(speed_kmh, now_ts)
    if idle_alert:
        alerts.append(idle_alert)
        logger.warning(f"[{vid}] {idle_alert['message']}")

    # 5. Fuel anomaly (EMA spike detection)
    fuel_alert = state.fuel_detector.update(speed_kmh, acceleration_ms2)
    if fuel_alert:
        alerts.append(fuel_alert)
        logger.warning(f"[{vid}] {fuel_alert['message']}")

    # 6. Fuel consumption (physics model)
    fuel_consumed = calculate_fuel_usage(speed_kmh, dt, acceleration_ms2)

    # Update kinematic state
    state.last_lat = filtered_lat
    state.last_lon = filtered_lon
    state.last_ts  = now_ts

    return {
        **gps_data,
        # Overwrite raw coords with Kalman-filtered values
        "latitude":             round(filtered_lat, 6),
        "longitude":            round(filtered_lon, 6),
        # Motion
        "speed_kmh":            round(speed_kmh, 2),
        "bearing_deg":          round(bearing_deg, 1),
        "acceleration_ms2":     round(acceleration_ms2, 4),
        "distance_step_m":      round(distance_m, 2),
        "total_distance_m":     round(state.total_distance_m, 1),
        # Route
        "distance_from_route_m": round(dist_from_route, 1),
        "route_segment_idx":    segment_idx,
        # Fuel
        "fuel_consumed_liters": fuel_consumed,
        # State
        "idle_state":           idle_state,
        "alerts":               alerts,
    }


# ─── Pipeline worker ──────────────────────────────────────────────────────────

def run_pipeline_from_queue(data_queue: "queue.Queue") -> None:
    """
    Single worker thread: drain the shared queue and process each fix.

    One thread handles all vehicles — per-vehicle state is isolated in
    VehicleState objects, so there are no race conditions between vehicles.
    """
    import queue as _queue
    logger.info("v2 pipeline worker started")

    while True:
        try:
            gps_data = data_queue.get(timeout=5.0)
        except _queue.Empty:
            continue

        try:
            enriched = process(gps_data)
            save_gps_record(enriched)    # Local SQLite (offline-safe, from v1)
            send_to_backend(enriched)    # HTTP POST to Express backend (from v1)
        except Exception as e:
            logger.error(f"Pipeline error for {gps_data.get('vehicle_id')}: {e}")
        finally:
            data_queue.task_done()


# ─── Entry point ──────────────────────────────────────────────────────────────

def main() -> None:
    import queue as _queue

    parser = argparse.ArgumentParser(description="Fleet Tracker Edge Client v2")
    parser.add_argument(
        "--mode",
        choices=["simulate", "hardware"],
        default="simulate",
        help="Data source mode (default: simulate)",
    )
    args = parser.parse_args()

    # Background sync — retries unsynced SQLite records (re-used from v1)
    threading.Thread(
        target=sync_loop,
        kwargs={"interval_sec": 10.0},
        daemon=True,
    ).start()

    if args.mode == "simulate":
        from simulator import run_multi_simulator
        data_queue = run_multi_simulator(interval_sec=SEND_INTERVAL_SEC)

    elif args.mode == "hardware":
        # Hardware mode: single vehicle via serial GPS reader (v1 reader re-used)
        from gps.gps_reader import read_gps_data

        veh_cfg_path = os.path.join(_EDGE_DIR, "config", "vehicle_config.json")
        with open(veh_cfg_path) as f:
            veh_cfg = json.load(f)

        v          = veh_cfg.get("vehicle", {})
        port       = os.getenv("GPS_PORT", v.get("gps_port", "/dev/ttyUSB0"))
        vehicle_id = v.get("vehicle_id", "Truck_1")

        data_queue: "queue.Queue" = _queue.Queue(maxsize=500)

        def _hw_reader():
            for fix in read_gps_data(port=port, vehicle_id=vehicle_id):
                data_queue.put(fix)

        threading.Thread(target=_hw_reader, daemon=True).start()

    # Single pipeline thread handles all vehicles via the shared queue
    threading.Thread(
        target=run_pipeline_from_queue,
        args=(data_queue,),
        daemon=True,
    ).start()

    logger.info("Edge client v2 running. Press Ctrl+C to stop.")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        logger.info("Shutting down.")


if __name__ == "__main__":
    main()
