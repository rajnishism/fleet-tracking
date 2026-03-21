"""
main.py
Main orchestrator for the Fleet Tracker edge system.

Reads GPS data (real or simulated), processes it through the modular pipeline
(route deviation, idle detection, fuel monitoring), saves locally, and sends
to the cloud backend.

Usage:
  python main.py --mode simulate          # Use simulator (no hardware)
  python main.py --mode hardware          # Use real GPS modules
"""

import argparse
import json
import os
import sys
import threading
import logging
import time
from datetime import datetime

# Add edge directory to path so subpackage imports work
# pylint: disable=wrong-import-position
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from processing.route_deviation import check_deviation
from processing.idle_detection import check_idle_status, IDLE_THRESHOLD_SEC
from processing.fuel_model import check_fuel_anomaly, calculate_fuel_usage
from processing.distance_speed import calculate_distance, calculate_speed
from cloud.api_client import send_to_backend
from cloud.sync_service import sync_loop
from storage.save_local import save_gps_record
from storage.queue_manager import delete_after_sync

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

# Load system config
_config_path = os.path.join(os.path.dirname(__file__), "config", "system_config.json")
with open(_config_path, encoding="utf-8") as config_file:
    SYS_CONFIG = json.load(config_file)

SEND_INTERVAL_SEC = float(os.getenv("SEND_INTERVAL", SYS_CONFIG.get("send_interval_sec", 2)))


# ─── Processing pipeline ─────────────────────────────────────────────────────

def process(
    gps_data: dict, 
    last_point: dict | None,
    idle_start_time: float | None, 
    stop_start_count: int, 
    speed_history: list[float]
) -> tuple[dict, dict, float | None, int]:
    """
    Run a single GPS data point through the full processing pipeline.
    Returns (enriched_data, current_point, new_idle_start_time, new_stop_start_count).
    """
    lat   = float(gps_data["latitude"])
    lon   = float(gps_data["longitude"])
    timestamp_str = str(gps_data["timestamp"])
    
    # Simple timestamp parsing (assuming ISO format YYYY-MM-DDTHH:MM:SSZ)
    try:
        now_ts = datetime.fromisoformat(timestamp_str.replace("Z", "+00:00")).timestamp()
    except ValueError:
        now_ts = time.time()

    alerts = []
    distance_step_m = 0.0
    speed_kmh = float(gps_data.get("speed_kmh", 0.0))
    duration_sec = 0.0

    if last_point:
        last_lat = last_point["latitude"]
        last_lon = last_point["longitude"]
        last_ts = last_point["timestamp"]
        
        duration_sec = now_ts - last_ts
        if duration_sec > 0:
            distance_step_m = calculate_distance(last_lat, last_lon, lat, lon)
            # Calculate speed unless it's already provided and reliable
            # Here we prefer calculated speed to follow requested pipeline
            speed_kmh = calculate_speed(distance_step_m, duration_sec)

    # 1. Route deviation check
    dist_from_route, deviation_alert = check_deviation(lat, lon)
    if deviation_alert:
        alerts.append(deviation_alert)
        logger.warning("ROUTE_DEVIATION: %.0fm from route", dist_from_route)

    # 2. Idle detection
    idle_status = check_idle_status(speed_kmh)
    idle_alert = None

    if idle_status == "idle":
        if idle_start_time is None:
            idle_start_time = now_ts
        idle_duration = now_ts - idle_start_time
        if idle_duration >= IDLE_THRESHOLD_SEC:
            idle_alert = {
                "type": "IDLE",
                "message": f"Vehicle idle for {int(idle_duration // 60)} min {int(idle_duration % 60)} sec",
                "idle_seconds": round(idle_duration),
            }
    else:
        # Vehicle was stopped and is now moving – record stop/start event
        if idle_start_time is not None:
            stop_start_count += 1
            logger.info("Stop/start count: %d", stop_start_count)
        idle_start_time = None

    if idle_alert:
        alerts.append(idle_alert)
        logger.warning("IDLE: %s", idle_alert['message'])

    # 3. Fuel estimation and anomaly detection
    stop_start_count, fuel_alert = check_fuel_anomaly(speed_kmh, speed_history, stop_start_count)
    if fuel_alert:
        alerts.append(fuel_alert)
        logger.warning("FUEL_ANOMALY: %s", fuel_alert['message'])
    
    fuel_consumed = calculate_fuel_usage(speed_kmh, duration_sec)

    enriched = {
        **gps_data,
        "speed_kmh": float(f"{float(speed_kmh):.2f}"),
        "distance_step_m": float(f"{float(distance_step_m):.2f}"),
        "fuel_consumed_liters": fuel_consumed,
        "distance_from_route_m": float(f"{float(dist_from_route):.1f}"),  # type: ignore
        "alerts": alerts,
    }
    
    current_point = {
        "latitude": lat,
        "longitude": lon,
        "timestamp": now_ts
    }
    
    return enriched, current_point, idle_start_time, stop_start_count


# ─── Data Pipeline Thread ────────────────────────────────────────────────────

def run_pipeline(generator):
    """Main worker pulling data: read → process → save → send."""
    logger.info("Pipeline started")
    
    last_point = None
    idle_start_time = None
    stop_start_count = 0
    speed_history = []
    
    for gps_data in generator:
        enriched, last_point, idle_start_time, stop_start_count = process(
            gps_data, 
            last_point,
            idle_start_time, 
            stop_start_count, 
            speed_history
        )

        # Save locally first (offline-safe)
        row_id = save_gps_record(enriched)
        
        # Log what happened
        logger.info(
            "SAVED: %s | Speed: %s km/h | Step: %sm | Fuel: %sL | Dev: %sm | Lat: %s, Lon: %s",
            enriched.get('vehicle_id'),
            enriched.get('speed_kmh'),
            enriched.get('distance_step_m'),
            enriched.get('fuel_consumed_liters'),
            enriched.get('distance_from_route_m'),
            enriched.get('latitude'),
            enriched.get('longitude')
        )

        # Send to cloud immediately. If successful, delete from local DB.
        if send_to_backend(enriched):
            delete_after_sync([row_id])


# ─── Entry point ──────────────────────────────────────────────────────────────

def main():
    """Main entry point for starting the edge client."""
    parser = argparse.ArgumentParser(description="Fleet Tracker Edge Client")
    parser.add_argument(
        "--mode",
        choices=["simulate", "hardware"],
        default="simulate",
        help="Data source mode",
    )
    args = parser.parse_args()

    # Ensure tables exist
    from storage.local_db import init_db
    init_db()
    
    # Start background sync service (retries unsent records)
    sync_thread = threading.Thread(target=sync_loop, kwargs={"interval_sec": 10.0}, daemon=True)
    sync_thread.start()

    if args.mode == "simulate":
        from simulator import run_simulator
        gen = run_simulator(interval_sec=SEND_INTERVAL_SEC)
        
        t = threading.Thread(
            target=run_pipeline,
            args=(gen,),
            daemon=True,
        )
        t.start()

    elif args.mode == "hardware":
        from gps.gps_reader import read_gps_data

        # Load vehicle config
        vehicle_config_path = os.path.join(os.path.dirname(__file__), "config", "vehicle_config.json")
        with open(vehicle_config_path, encoding="utf-8") as vehicle_file:
            vehicle_config = json.load(vehicle_file)

        v = vehicle_config.get("vehicle", {})
        port = os.getenv("GPS_PORT", v.get("gps_port", "/dev/ttyUSB0"))
        
        gen = read_gps_data(port=port, vehicle_id=v.get("vehicle_id", "Truck_1"))
        t = threading.Thread(
            target=run_pipeline,
            args=(gen,),
            daemon=True,
        )
        t.start()

    logger.info("Edge client running. Press Ctrl+C to stop.")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        logger.info("Shutting down.")


if __name__ == "__main__":
    main()
