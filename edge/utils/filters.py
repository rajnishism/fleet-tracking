"""
filters.py
Signal filtering utilities for GPS data smoothing.
"""

import logging

logger = logging.getLogger(__name__)


def moving_average(value: float, buffer: list[float], window_size: int = 5) -> float:
    """Add a new value to the buffer and return the smoothed result."""
    buffer.append(value)
    if len(buffer) > window_size:
        buffer.pop(0)
    return sum(buffer) / len(buffer)


def kalman_filter_1d(
    measurement: float, 
    estimate: float | None, 
    error_estimate: float, 
    process_variance: float = 1e-5, 
    measurement_variance: float = 1e-3
) -> tuple[float, float]:
    """
    Simple 1D Kalman filter for GPS coordinate smoothing.
    Returns (new_estimate, new_error_estimate).
    """
    if estimate is None:
        return measurement, measurement_variance

    # Prediction step
    prediction = estimate
    prediction_error = error_estimate + process_variance

    # Update step
    kalman_gain = prediction_error / (prediction_error + measurement_variance)
    new_estimate = prediction + kalman_gain * (measurement - prediction)
    new_error_estimate = (1 - kalman_gain) * prediction_error

    return new_estimate, new_error_estimate
