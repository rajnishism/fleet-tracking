"""
filters.py (v2)
Extended filtering utilities for GPS and sensor data smoothing.

vs edge/utils/filters.py (v1):
- Replaces the per-axis 1D Kalman filter with GPSKalmanFilter2D, a 4-state filter
  that tracks [lat, lon, vel_lat, vel_lon] so position predictions are physically
  informed by the vehicle's current velocity — not just by measurement noise alone.
- Adds exponential_moving_average (EMA) for lightweight signal smoothing.
- Retains moving_average unchanged for backwards compatibility.
"""

import logging

logger = logging.getLogger(__name__)


# ─── Moving average (unchanged from v1) ──────────────────────────────────────

def moving_average(value: float, buffer: list[float], window_size: int = 5) -> float:
    """Add value to buffer and return the windowed mean."""
    buffer.append(value)
    if len(buffer) > window_size:
        buffer.pop(0)
    return sum(buffer) / len(buffer)


# ─── Exponential moving average (new in v2) ───────────────────────────────────

def exponential_moving_average(
    value: float,
    prev_ema: float | None,
    alpha: float = 0.3,
) -> float:
    """
    EMA: faster to compute than a windowed average; good for streaming sensors.

    alpha controls responsiveness:
      - Higher alpha (e.g. 0.5) reacts quickly but retains more noise.
      - Lower alpha (e.g. 0.1) is smoother but lags sudden changes.
    """
    if prev_ema is None:
        return value
    return alpha * value + (1.0 - alpha) * prev_ema


# ─── 2D GPS Kalman filter (replaces 1D Kalman in v1) ─────────────────────────

class GPSKalmanFilter2D:
    """
    Constant-velocity Kalman filter for GPS position smoothing.

    State vector: [lat, lon, vel_lat, vel_lon]

    vs v1 (two independent 1D Kalman calls):
    - Velocity is part of the state, so the prediction step extrapolates position
      using the estimated heading and speed — physically correct for a moving truck.
    - Cross-axis correlations are ignored (diagonal covariance) which keeps
      computation cheap while still outperforming independent 1D filters on
      curved road sections where lat and lon change together.

    Usage:
        kf = GPSKalmanFilter2D()
        lat_f, lon_f = kf.update(raw_lat, raw_lon, dt_seconds)
    """

    def __init__(
        self,
        process_noise: float = 1e-5,
        measurement_noise: float = 1e-4,
    ):
        self._initialized = False
        self._lat: float = 0.0
        self._lon: float = 0.0
        self._vel_lat: float = 0.0
        self._vel_lon: float = 0.0

        # Diagonal covariance: [P_lat, P_lon, P_vel_lat, P_vel_lon]
        self._P: list[float] = [1e-4, 1e-4, 1.0, 1.0]

        self._Q = process_noise      # Process noise (model uncertainty)
        self._R = measurement_noise  # Measurement noise (GPS accuracy)

    def update(self, lat: float, lon: float, dt: float) -> tuple[float, float]:
        """
        Feed a new raw GPS fix and return (filtered_lat, filtered_lon).

        dt: seconds elapsed since the last call. Use 1.0 for the first call.
        """
        if not self._initialized:
            self._lat = lat
            self._lon = lon
            self._initialized = True
            return lat, lon

        # ── Predict ──────────────────────────────────────────────────────────
        pred_lat = self._lat + self._vel_lat * dt
        pred_lon = self._lon + self._vel_lon * dt

        P_lat    = self._P[0] + self._Q
        P_lon    = self._P[1] + self._Q
        P_vlat   = self._P[2] + self._Q
        P_vlon   = self._P[3] + self._Q

        # ── Update (position measurements only) ──────────────────────────────
        K_lat = P_lat / (P_lat + self._R)
        K_lon = P_lon / (P_lon + self._R)

        new_lat = pred_lat + K_lat * (lat - pred_lat)
        new_lon = pred_lon + K_lon * (lon - pred_lon)

        # Derive velocity from the corrected position delta
        if dt > 0:
            self._vel_lat = (new_lat - self._lat) / dt
            self._vel_lon = (new_lon - self._lon) / dt

        self._lat = new_lat
        self._lon = new_lon
        self._P = [
            (1.0 - K_lat) * P_lat,
            (1.0 - K_lon) * P_lon,
            P_vlat,
            P_vlon,
        ]

        return new_lat, new_lon

    def reset(self) -> None:
        """Reset the filter state (e.g. after a GPS signal gap)."""
        self._initialized = False
        self._vel_lat = 0.0
        self._vel_lon = 0.0
        self._P = [1e-4, 1e-4, 1.0, 1.0]
