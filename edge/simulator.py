"""
simulator.py
Simulates GPS data for mining trucks without real hardware.

Vehicle scenarios:
  Truck_1 – follows the haul road normally.

"""

import json
import os
import sys
import time
import random
import logging
from typing import Generator
from utils.haversine import haversine

# Ensure edge root is on the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

# Load haul road from config
_route_path = os.path.join(os.path.dirname(__file__), "config", "route_polygon.json")
with open(_route_path) as f:
    _route_data = json.load(f)
route_list = _route_data.get("haul_road", [])
# Handle case where user accidentally wrapped the array in another array
if len(route_list) > 0 and isinstance(route_list[0], list) and (len(route_list[0]) > 0 and isinstance(route_list[0][0], dict)):
    route_list = route_list[0]

HAUL_ROAD = []
for pt in route_list:
    if isinstance(pt, dict):
        HAUL_ROAD.append((float(pt.get("lat", 0.0)), float(pt.get("lon", 0.0))))
    else:
        HAUL_ROAD.append((float(pt[0]), float(pt[1])))

# Load system config
_config_path = os.path.join(os.path.dirname(__file__), "config", "system_config.json")
with open(_config_path) as f:
    _sys_config = json.load(f)
STEPS_PER_SEGMENT = _sys_config.get("steps_per_segment", 20)


def _build_dense_path(waypoints: list[tuple[float, float]], resolution_m: float = 1.0) -> list[tuple[float, float]]:
    """Interpolate route into a dense 1-meter resolution path for physics-based traversal."""
    if not waypoints:
        return [(0.0, 0.0)]
    path = []
    for i in range(len(waypoints) - 1):
        lat1, lon1 = waypoints[i]
        lat2, lon2 = waypoints[i + 1]
        dist_m = haversine(lat1, lon1, lat2, lon2)
        steps = max(1, int(dist_m / resolution_m))
        for j in range(steps):
            t = j / steps
            path.append((lat1 + t * (lat2 - lat1), lon1 + t * (lon2 - lon1)))
    path.append(waypoints[-1])
    return path


def _now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def generate_truck_data(vehicle_id: str, scenario: str = "mixed", interval_sec: float = 2.0) -> Generator[dict, None, None]:
    """Continuously yield realistic, physics-based GPS data for a mining truck."""
    logger.info(f"Simulator starting (scenario: {scenario})")
    path = _build_dense_path(HAUL_ROAD, resolution_m=1.0)
    
    idx = 0
    current_speed = 0.0
    tick = 0
    
    while True:
        tick += 1
        status = "moving"
        target_speed = 30.0
        
        # 1. Evaluate Timeline / Scenario Goals
        if scenario == "mixed":
            cycle_tick = tick % 300
            if cycle_tick < 100:
                target_speed = 28.0
            elif cycle_tick < 140:
                target_speed = 0.0
                status = "idle"
            elif cycle_tick < 220:
                target_speed = 32.0
            else:
                target_speed = 20.0
                status = "deviated"
        elif scenario == "normal":
            target_speed = 30.0
        elif scenario == "idle":
            target_speed = 0.0
            status = "idle"
        elif scenario == "deviation":
            target_speed = 22.0
            status = "deviated"
        elif scenario == "fuel_anomaly":
            target_speed = 45.0 if (tick % 20 < 10) else 5.0

        # 2. Physics-based Acceleration / Braking
        accel_rate = 1.2  # km/h per tick (heavy machinery)
        brake_rate = 2.5  # km/h per tick 
        
        if current_speed < target_speed:
            current_speed += min(accel_rate, target_speed - current_speed)
        elif current_speed > target_speed:
            current_speed -= min(brake_rate, current_speed - target_speed)
            
        # Engine micro-fluctuations (jitter) when moving
        if current_speed > 0:
            current_speed += random.uniform(-0.6, 0.6)
            
        current_speed = max(0.0, current_speed)

        # 3. Calculate True Map Traversal Distance (d = v * t)
        distance_m = (current_speed * 1000.0 / 3600.0) * interval_sec
        
        # Move forward strictly by however many integer meters traveled
        idx = (idx + int(distance_m)) % max(1, len(path))
        lat, lon = path[idx]

        # 4. Apply Deviations and Noise
        if status == "deviated":
            # Expand deviation over time
            dev_factor = min(((tick % 300) - 220) / 80.0, 1.0) if scenario == "mixed" else 1.0
            lat += dev_factor * 0.003
            lon += dev_factor * 0.003
            
        # Tiny real-world GPS multipath jitter (even when idle)
        lat += random.uniform(-0.00001, 0.00001)
        lon += random.uniform(-0.00001, 0.00001)
        
        data = {
            "vehicle_id": vehicle_id,
            "latitude": round(lat, 6),
            "longitude": round(lon, 6),
            "speed_kmh": round(current_speed, 2),
            "timestamp": _now_iso(),
            "status": status
        }
        
        yield data
        time.sleep(interval_sec)


def run_simulator(interval_sec: float = 2.0):
    vehicle_config_path = os.path.join(os.path.dirname(__file__), "config", "vehicle_config.json")
    with open(vehicle_config_path) as f:
        vehicle_config = json.load(f)

    v = vehicle_config.get("vehicle", {})
    return generate_truck_data(
        vehicle_id=v.get("vehicle_id", "Truck_1"),
        scenario=v.get("scenario", "mixed"),
        interval_sec=interval_sec,
    )


if __name__ == "__main__":
    gen = run_simulator(interval_sec=0.5)
    for _ in range(10):
        print(next(gen))
