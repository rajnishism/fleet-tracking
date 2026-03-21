"""
gps_parser.py
Parses NMEA sentences ($GPRMC, $GPGGA) to extract GPS data.
"""

import logging

logger = logging.getLogger(__name__)


def parse_gprmc(sentence: str) -> dict | None:
    """Parse a $GPRMC NMEA sentence.

    Returns a dict with keys: latitude, longitude, speed_kmh, timestamp
    or None if the sentence is invalid or status is Void.
    """
    try:
        parts = sentence.strip().split(",")
        if len(parts) < 10:
            return None

        status = parts[2]
        if status != "A":  # A = Active, V = Void (no fix)
            return None

        raw_time = parts[1]   # HHMMSS.ss
        raw_lat  = parts[3]
        lat_dir  = parts[4]
        raw_lon  = parts[5]
        lon_dir  = parts[6]
        speed_kn = float(parts[7]) if parts[7] else 0.0
        raw_date = parts[9]   # DDMMYY

        latitude  = _nmea_to_decimal(raw_lat, lat_dir)
        longitude = _nmea_to_decimal(raw_lon, lon_dir)
        speed_kmh = speed_kn * 1.852  # knots → km/h

        h, m, s = raw_time[0:2], raw_time[2:4], raw_time[4:6]
        d, mo, y = raw_date[0:2], raw_date[2:4], "20" + raw_date[4:6]
        timestamp = f"{y}-{mo}-{d}T{h}:{m}:{s}Z"

        return {
            "latitude": latitude,
            "longitude": longitude,
            "speed_kmh": round(speed_kmh, 2),
            "timestamp": timestamp,
        }
    except Exception as e:
        logger.warning(f"Failed to parse GPRMC: {e} | Sentence: {sentence}")
        return None


def parse_gpgga(sentence: str) -> dict | None:
    """Parse a $GPGGA NMEA sentence for altitude and fix quality."""
    try:
        parts = sentence.strip().split(",")
        if len(parts) < 10:
            return None
        fix_quality = int(parts[6]) if parts[6] else 0
        if fix_quality == 0:
            return None
        altitude = float(parts[9]) if parts[9] else 0.0
        return {"altitude": altitude, "fix_quality": fix_quality}
    except Exception as e:
        logger.warning(f"Failed to parse GPGGA: {e}")
        return None


def _nmea_to_decimal(raw: str, direction: str) -> float:
    """Convert NMEA coordinate (DDDMM.MMMMM) to decimal degrees."""
    if not raw:
        raise ValueError("Empty coordinate string")
    dot_pos = raw.index(".")
    deg = float(raw[:dot_pos - 2])
    minutes = float(raw[dot_pos - 2:])
    decimal = deg + minutes / 60.0
    if direction in ("S", "W"):
        decimal *= -1
    return round(decimal, 6)
