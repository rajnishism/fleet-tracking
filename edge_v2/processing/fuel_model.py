"""
fuel_model.py (v2)
Physics-based fuel consumption model using tractive-effort estimation.

vs edge/processing/fuel_model.py (v1):
- v1 uses a linear heuristic: rate = 10 + speed/5  L/h, anomaly via stop-start
  count and speed variance.
- v2 estimates mechanical shaft power from first principles:
    F_roll   = C_rr × m × g          (rolling resistance, mine haul road)
    F_inertia = m × a                 (inertia force during acceleration)
    P_shaft  = (F_roll + F_inertia) × v / η_drivetrain
  Then converts shaft power to fuel rate via BSFC (brake-specific fuel
  consumption), a standard diesel engine parameter:
    fuel_rate (L/h) = P_shaft (kW) × BSFC (kg/kWh) / ρ_diesel (kg/L)
- Anomaly detection uses an EMA baseline instead of stop-start counting:
    FuelAnomalyDetector fires when instantaneous rate > EMA × ANOMALY_RATIO.
  This catches sudden spikes (hard acceleration, engine fault) without needing
  to count stop-start events.
- Adds fuel_efficiency_l_per_tonne_km() — an operational KPI metric that the
  backend can persist and trend over shift periods.
"""

import json
import os
import logging
from typing import Optional

logger = logging.getLogger(__name__)

# ─── Config ───────────────────────────────────────────────────────────────────
_config_dir = os.path.join(os.path.dirname(__file__), "..", "..", "edge", "config")

with open(os.path.join(_config_dir, "system_config.json")) as f:
    _sys = json.load(f)

with open(os.path.join(_config_dir, "vehicle_config.json")) as f:
    _veh = json.load(f).get("vehicle", {})

# ─── Vehicle / engine constants ───────────────────────────────────────────────

# Loaded mass estimate: payload + empty truck body (~1.5× payload)
TRUCK_MASS_KG    = _veh.get("max_payload_tonnes", 50) * 1000 * 1.5

FUEL_CAPACITY_L  = _veh.get("fuel_capacity_liters", 500)
PAYLOAD_TONNES   = _veh.get("max_payload_tonnes", 50)

C_RR             = 0.02     # Rolling resistance coefficient (compacted mine road)
G                = 9.81     # m/s²
ETA_DRIVETRAIN   = 0.85     # Mechanical efficiency of driveline (typical haul truck)
BSFC_KG_KWH      = 0.22     # Brake-specific fuel consumption — diesel engine at load
DIESEL_DENSITY   = 0.832    # kg/L
MIN_IDLE_POWER_KW = 5.0     # Minimum engine power (cooling fan, hydraulics, A/C)

# ─── Anomaly thresholds ───────────────────────────────────────────────────────

EMA_ALPHA               = 0.1   # EMA smoothing factor for baseline rate
ANOMALY_RATIO_THRESHOLD = 2.0   # Instantaneous > 2× EMA baseline → anomaly
MIN_ANOMALY_RATE_LPH    = 5.0   # Don't alert on tiny absolute rates (e.g. idle)


# ─── Physics model ────────────────────────────────────────────────────────────

def _rolling_resistance_power_w(speed_ms: float) -> float:
    """Shaft power required to overcome rolling resistance at constant speed (W)."""
    return C_RR * TRUCK_MASS_KG * G * speed_ms  # P = F_roll × v


def _inertial_power_w(acceleration_ms2: float, speed_ms: float) -> float:
    """
    Shaft power absorbed by vehicle inertia (W).
    Positive during acceleration; negative (regenerative) during braking —
    we clamp to 0 since conventional trucks cannot recover braking energy.
    """
    return max(0.0, TRUCK_MASS_KG * acceleration_ms2 * speed_ms)


def calculate_fuel_rate_lph(
    speed_kmh: float,
    acceleration_ms2: float = 0.0,
) -> float:
    """
    Estimate instantaneous fuel consumption rate in L/h.

    Uses rolling resistance + inertial force to compute required shaft power,
    then converts to fuel rate via BSFC.

    Args:
        speed_kmh:        Current speed in km/h.
        acceleration_ms2: Current acceleration in m/s² (from MotionData).
    """
    speed_ms = speed_kmh / 3.6

    if speed_ms < 0.1:
        # Engine idling: only aux loads (fan, hydraulic pump, A/C)
        power_kw = MIN_IDLE_POWER_KW
    else:
        p_roll   = _rolling_resistance_power_w(speed_ms)
        p_inert  = _inertial_power_w(acceleration_ms2, speed_ms)
        shaft_kw = (p_roll + p_inert) / ETA_DRIVETRAIN / 1000.0
        power_kw = max(MIN_IDLE_POWER_KW, shaft_kw)

    # BSFC: kg fuel per kWh of mechanical work → convert to L/h
    fuel_rate_kgh = power_kw * BSFC_KG_KWH
    return fuel_rate_kgh / DIESEL_DENSITY


def calculate_fuel_usage(
    speed_kmh: float,
    duration_sec: float,
    acceleration_ms2: float = 0.0,
) -> float:
    """Return litres consumed over a time step."""
    if duration_sec <= 0:
        return 0.0
    rate_lph = calculate_fuel_rate_lph(speed_kmh, acceleration_ms2)
    return round(rate_lph * (duration_sec / 3600.0), 4)


def fuel_efficiency_l_per_tonne_km(
    fuel_l: float,
    distance_km: float,
) -> Optional[float]:
    """
    L/tonne-km efficiency metric for haul-cycle benchmarking.

    Uses the vehicle's configured payload. Returns None when distance is zero
    (e.g. first reading, or stationary truck).
    """
    if PAYLOAD_TONNES <= 0 or distance_km <= 0:
        return None
    return round(fuel_l / (PAYLOAD_TONNES * distance_km), 4)


# ─── Anomaly detector ─────────────────────────────────────────────────────────

class FuelAnomalyDetector:
    """
    Stateful EMA-based fuel consumption anomaly detector.

    vs v1 (stop-start count + speed variance):
    - Directly compares the physics-derived instantaneous fuel rate against a
      smoothed baseline.  A sudden spike — e.g. from hard acceleration uphill or
      an engine running rough — is caught immediately rather than needing several
      stop-start cycles to accumulate.

    Instantiate one FuelAnomalyDetector per vehicle in VehicleState (main.py).
    """

    def __init__(self) -> None:
        self._ema_rate_lph: Optional[float] = None

    def update(
        self,
        speed_kmh: float,
        acceleration_ms2: float = 0.0,
    ) -> Optional[dict]:
        """
        Feed current speed and acceleration; returns an alert dict or None.
        """
        rate = calculate_fuel_rate_lph(speed_kmh, acceleration_ms2)

        if self._ema_rate_lph is None:
            self._ema_rate_lph = rate
            return None

        alert: Optional[dict] = None

        if (
            rate > self._ema_rate_lph * ANOMALY_RATIO_THRESHOLD
            and rate > MIN_ANOMALY_RATE_LPH
        ):
            alert = {
                "type":          "FUEL_ANOMALY",
                "message": (
                    f"Fuel rate spike: {rate:.1f} L/h "
                    f"vs baseline {self._ema_rate_lph:.1f} L/h"
                ),
                "rate_lph":     round(rate, 2),
                "ema_rate_lph": round(self._ema_rate_lph, 2),
            }

        # Update EMA baseline regardless of whether an alert fired
        self._ema_rate_lph = (
            EMA_ALPHA * rate + (1.0 - EMA_ALPHA) * self._ema_rate_lph
        )
        return alert
