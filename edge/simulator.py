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
# Handle primary haul road
route_list = _route_data.get("haul_road", [])
if len(route_list) > 0 and isinstance(route_list[0], list) and (len(route_list[0]) > 0 and isinstance(route_list[0][0], dict)):
    route_list = route_list[0]

HAUL_ROAD = []
for pt in route_list:
    if isinstance(pt, dict):
        HAUL_ROAD.append((float(pt.get("lat", 0.0)), float(pt.get("lon", 0.0))))
    else:
        HAUL_ROAD.append((float(pt[0]), float(pt[1])))

# Parse additional polygons (dummy, actual, etc.)
def parse_polygon(poly_data):
    if len(poly_data) > 0 and isinstance(poly_data[0], list) and (len(poly_data[0]) > 0 and isinstance(poly_data[0][0], dict)):
        poly_data = poly_data[0]
    result = []
    for pt in poly_data:
        if isinstance(pt, dict):
            result.append((float(pt.get("lat", 0.0)), float(pt.get("lon", 0.0))))
        else:
            result.append((float(pt[0]), float(pt[1])))
    return result

DUMMY_ROAD = parse_polygon(_route_data.get("DUMMY_ROAD", _route_data.get("dummy", [])))
ACTUAL_ROAD = parse_polygon(_route_data.get("actual", []))

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


def generate_truck_data(vehicle_id: str, scenario: str = "idle", interval_sec: float = 2.0) -> Generator[dict, None, None]:
    """Continuously yield realistic, physics-based GPS data for a mining truck."""
    logger.info(f"Simulator starting (scenario: {scenario})")
    path = _build_dense_path(DUMMY_ROAD, resolution_m=1.0)
    
    idx_float = 0.0
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

        # 2. Physics-based Acceleration / Braking
        accel_rate = 1.2  # km/h per tick (heavy machinery)
        brake_rate = 2.5  # km/h per tick 
        
        if current_speed < target_speed:
            current_speed += min(accel_rate, target_speed - current_speed)
        elif current_speed > target_speed:
            current_speed -= min(brake_rate, current_speed - target_speed)
            
        current_speed = max(0.0, current_speed)

        # 3. Calculate True Map Traversal Distance (d = v * t)
        distance_m = (current_speed * 1000.0 / 3600.0) * interval_sec
        
        # Move forward using exact floats (since dense path is 1 meter resolution)
        idx_float += distance_m
        
        # Sub-meter coordinate interpolation for ultra-smooth calculation in main.py
        idx = int(idx_float) % max(1, len(path))
        next_idx = (idx + 1) % max(1, len(path))
        fraction = idx_float - int(idx_float)
        
        lat1, lon1 = path[idx]
        lat2, lon2 = path[next_idx]
        lat = lat1 + fraction * (lat2 - lat1)
        lon = lon1 + fraction * (lon2 - lon1)

        # 4. Apply Deviations and Noise
        if status == "deviated":
            # Expand deviation over time
            dev_factor = min(((tick % 300) - 220) / 80.0, 1.0) if scenario == "mixed" else 1.0
            lat += dev_factor * 0.003
            lon += dev_factor * 0.003
            
        # Tiny real-world GPS multipath jitter (toned down from before)
        lat += random.uniform(-0.000001, 0.000001)
        lon += random.uniform(-0.000001, 0.000001)
        
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
