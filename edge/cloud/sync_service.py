"""
sync_service.py
Background service that syncs locally stored GPS data to the cloud.

Retries unsent records from the queue manager on a periodic interval.
"""

import time
import logging
import json

from storage.queue_manager import get_unsynced_records, delete_after_sync
from cloud.api_client import send_to_backend

logger = logging.getLogger(__name__)


def sync_loop(interval_sec: float = 10.0):
    """
    Continuously attempt to sync unsynced records to the cloud.

    Should be run in a separate daemon thread.
    """
    logger.info(f"Sync service started (interval: {interval_sec}s)")
    while True:
        try:
            records = get_unsynced_records(limit=50)
            if records:
                synced_ids = []
                for record in records:
                    # Reconstruct payload from DB record
                    payload = {
                        "vehicle_id": record["vehicle_id"],
                        "latitude": record["latitude"],
                        "longitude": record["longitude"],
                        "speed_kmh": record["speed_kmh"],
                        "timestamp": record["timestamp"],
                        "distance_from_route_m": record["distance_from_route_m"],
                        "distance_step_m": record.get("distance_step_m", 0.0),
                        "fuel_consumed_liters": record.get("fuel_consumed_liters", 0.0),
                        "alerts": json.loads(record["alerts"]) if record["alerts"] else [],
                    }
                    if send_to_backend(payload):
                        synced_ids.append(record["id"])
                    else:
                        # Stop syncing rest of queue if backend is down to avoid spam
                        break

                if synced_ids:
                    delete_after_sync(synced_ids)
                    logger.info(f"Synced and deleted {len(synced_ids)} records from local database")
        except Exception as e:
            logger.error(f"Sync error: {e}")

        time.sleep(interval_sec)
