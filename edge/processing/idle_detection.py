"""
idle_detection.py
Detects when a vehicle has been idle (speed ≈ 0) for too long.
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

IDLE_SPEED_KMH = _config.get("idle_speed_kmh", 2.0)
IDLE_THRESHOLD_SEC = _config.get("idle_threshold_sec", 300)


def check_idle_status(speed_kmh: float) -> str:
    """Return 'idle' if vehicle speed is below idle threshold, else 'moving'."""
    return "idle" if speed_kmh < IDLE_SPEED_KMH else "moving"
