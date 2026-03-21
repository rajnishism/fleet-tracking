"""
save_local.py
Save processed GPS data to the local SQLite database.
"""

import json
import logging

from storage.local_db import get_connection

logger = logging.getLogger(__name__)


def save_gps_record(data: dict) -> int:
    """
    Insert a processed GPS record into the local database.

    Returns the row ID of the inserted record.
    """
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        INSERT INTO gps_records (vehicle_id, latitude, longitude, speed_kmh,
                                  timestamp, distance_from_route_m, distance_step_m, 
                                  fuel_consumed_liters, alerts, synced)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 0)
        """,
        (
            data.get("vehicle_id"),
            data.get("latitude"),
            data.get("longitude"),
            data.get("speed_kmh"),
            data.get("timestamp"),
            data.get("distance_from_route_m"),
            data.get("distance_step_m"),
            data.get("fuel_consumed_liters"),
            json.dumps(data.get("alerts", [])),
        ),
    )
    conn.commit()
    row_id = cursor.lastrowid
    conn.close()
    return row_id
