"""
idle_detection.py (v2)
Hysteresis-based idle detection with FULL_STOP / CRAWL classification.

vs edge/processing/idle_detection.py (v1):
- v1 uses a single threshold: speed < 2 km/h → "idle".  This causes alert
  flapping when a truck creeps at borderline speed (e.g. 1.9 → 2.1 → 1.8 km/h).
- v2 uses a two-threshold hysteresis band:
    Enter idle : speed drops below IDLE_ENTER_KMH for IDLE_CONFIRM_READINGS
                 consecutive readings.
    Exit idle  : speed rises above IDLE_EXIT_KMH for EXIT_CONFIRM_READINGS
                 consecutive readings.
  The gap between thresholds (2 km/h → 5 km/h) absorbs noisy speed signals.
- Classifies idle into:
    FULL_STOP — speed < FULL_STOP_KMH (≈0); engine idling, vehicle parked.
    CRAWL     — speed ≥ FULL_STOP_KMH but still below IDLE_ENTER_KMH; e.g.
                slow queue movement or loading bay inching.
- State is encapsulated in IdleDetector so main.py needs no manual idle_start_time
  or stop_start_count variables.
"""

import json
import os
import logging
from typing import Optional

logger = logging.getLogger(__name__)

# ─── Config ───────────────────────────────────────────────────────────────────
_config_path = os.path.join(
    os.path.dirname(__file__), "..", "..", "edge", "config", "system_config.json"
)
with open(_config_path) as f:
    _cfg = json.load(f)

IDLE_ENTER_KMH     = _cfg.get("idle_speed_kmh", 2.0)        # Enter idle below this
IDLE_EXIT_KMH      = IDLE_ENTER_KMH * 2.5                   # Exit idle above this (hysteresis gap)
IDLE_THRESHOLD_SEC = _cfg.get("idle_threshold_sec", 300)     # Alert after this many idle seconds

IDLE_CONFIRM_READINGS = 3   # Consecutive low-speed readings needed to confirm idle
EXIT_CONFIRM_READINGS = 2   # Consecutive high-speed readings needed to confirm moving
FULL_STOP_KMH         = 0.5  # Below this = engine-idle parked, not slow-crawl


# ─── State machine ────────────────────────────────────────────────────────────

class IdleDetector:
    """
    Two-threshold hysteresis idle state machine.

    States: MOVING ──► IDLE ──► MOVING  (transitions guarded by consecutive counts)

    Instantiate one IdleDetector per vehicle in VehicleState (main.py).
    """

    def __init__(self) -> None:
        self._state: str              = "MOVING"
        self._low_count: int          = 0   # Consecutive below-ENTER readings
        self._high_count: int         = 0   # Consecutive above-EXIT readings
        self._idle_start_ts: Optional[float] = None

    # ── Public API ────────────────────────────────────────────────────────────

    @property
    def is_idle(self) -> bool:
        return self._state == "IDLE"

    def update(
        self, speed_kmh: float, now_ts: float
    ) -> tuple[str, Optional[dict]]:
        """
        Feed the current speed and wall-clock timestamp.

        Returns:
            (state_label, alert_or_None)

            state_label: 'MOVING' | 'IDLE'
            alert keys : type, idle_class ('FULL_STOP'|'CRAWL'), message,
                         idle_seconds
        """
        self._update_counters(speed_kmh)
        self._transition(speed_kmh, now_ts)
        alert = self._build_alert(speed_kmh, now_ts)
        return self._state, alert

    # ── Internal helpers ──────────────────────────────────────────────────────

    def _update_counters(self, speed_kmh: float) -> None:
        if speed_kmh <= IDLE_ENTER_KMH:
            self._low_count  += 1
            self._high_count  = 0
        elif speed_kmh >= IDLE_EXIT_KMH:
            self._high_count += 1
            self._low_count   = 0
        # Speed in the hysteresis band: neither counter changes.

    def _transition(self, speed_kmh: float, now_ts: float) -> None:
        if self._state == "MOVING":
            if self._low_count >= IDLE_CONFIRM_READINGS:
                self._state          = "IDLE"
                self._idle_start_ts  = now_ts
                idle_class = "FULL_STOP" if speed_kmh < FULL_STOP_KMH else "CRAWL"
                logger.info(f"Idle confirmed ({idle_class}), speed={speed_kmh:.1f} km/h")

        elif self._state == "IDLE":
            if self._high_count >= EXIT_CONFIRM_READINGS:
                self._state          = "MOVING"
                self._idle_start_ts  = None
                self._low_count      = 0
                logger.info("Idle ended — vehicle moving")

    def _build_alert(
        self, speed_kmh: float, now_ts: float
    ) -> Optional[dict]:
        """Return an IDLE alert if threshold duration has been exceeded."""
        if self._state != "IDLE" or self._idle_start_ts is None:
            return None

        idle_duration = now_ts - self._idle_start_ts
        if idle_duration < IDLE_THRESHOLD_SEC:
            return None

        idle_class = "FULL_STOP" if speed_kmh < FULL_STOP_KMH else "CRAWL"
        return {
            "type":         "IDLE",
            "idle_class":   idle_class,
            "message": (
                f"Vehicle {idle_class} for "
                f"{int(idle_duration // 60)} min {int(idle_duration % 60)} sec"
            ),
            "idle_seconds": round(idle_duration),
        }
