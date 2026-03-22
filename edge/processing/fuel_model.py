"""
fuel_model.py
Estimates fuel consumption anomalies from driving patterns.
"""

import json
import os
import logging
from typing import Optional

logger = logging.getLogger(__name__)

# Load thresholds from config
_config_path = os.path.join(os.path.dirname(__file__), "..", "config", "system_config.json")
with open(_config_path) as f:
    _config = json.load(f)

FUEL_STOP_START_LIMIT = _config.get("fuel_stop_start_limit", 5)
SPEED_HISTORY_WINDOW = _config.get("speed_history_window", 20)
SPEED_VARIANCE_THRESHOLD = _config.get("speed_variance_threshold", 200)


from processing.load_factor import compute_load_factor, compute_fuel_rate

def calculate_fuel_usage(
    speed_kmh: float, 
    duration_sec: float,
    vmax: float = 80.0,
    is_loaded: int = 1,
    slope: int = 0,
    engine_power_kw: float = 500.0
) -> float:
    """
    Estimate fuel consumption in liters for a given speed and duration.
    Uses the physics-based load factor model to calculate fuel rate.
    
    - Idle (speed < 2.0 km/h): 2.0 L/h
    - Moving: Uses load factor * engine_power * specific_fuel_consumption L/h
    """
    if speed_kmh < 2.0:  # Roughly idle
        consumption_rate_lph = 2.0
    else:
        lf = compute_load_factor(speed_kmh, vmax, is_loaded, slope)
        consumption_rate_lph = compute_fuel_rate(engine_power_kw, lf)
    
    # L/h to L/sec
    consumption_rate_lps = consumption_rate_lph / 3600.0
    return round(consumption_rate_lps * duration_sec, 4)


def check_fuel_anomaly(
    speed_kmh: float,
    speed_history: list[float],
    stop_start_count: int
) -> tuple[int, dict | None]:
    """
    Analyse speed pattern for fuel anomalies based on single vehicle state.

    Args:
        speed_kmh: Current speed
        speed_history: Mutable list of recent speeds (updated in-place).
        stop_start_count: Running count of stop/start events.

    Returns:
        (updated_stop_start_count, alert_dict_or_None)
    """
    speed_history.append(speed_kmh)
    if len(speed_history) > SPEED_HISTORY_WINDOW:
        speed_history.pop(0)

    alert = None

    # Too many stop/starts → high fuel consumption
    if stop_start_count >= FUEL_STOP_START_LIMIT:
        alert = {
            "type": "FUEL_ANOMALY",
            "message": f"High fuel consumption zone detected ({stop_start_count} stop/starts)",
            "stop_start_count": stop_start_count,
        }
        stop_start_count = 0  # reset after alerting

    # High speed variance → erratic driving
    if len(speed_history) >= 10:
        mean_speed = sum(speed_history) / len(speed_history)
        variance = sum((s - mean_speed) ** 2 for s in speed_history) / len(speed_history)
        if variance > SPEED_VARIANCE_THRESHOLD:
            alert = {
                "type": "FUEL_ANOMALY",
                "message": f"Erratic driving detected (speed variance={variance:.1f})",
                "speed_variance": round(variance, 2),
            }

    return stop_start_count, alert
