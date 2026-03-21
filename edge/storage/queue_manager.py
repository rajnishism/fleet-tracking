"""
queue_manager.py
Tracks which GPS records have not yet been synced to the cloud.
"""

import logging

from storage.local_db import get_connection

logger = logging.getLogger(__name__)


def get_unsynced_records(limit: int = 50) -> list[dict]:
    """Retrieve up to `limit` records that haven't been sent to the cloud."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT * FROM gps_records WHERE synced = 0 ORDER BY id ASC LIMIT ?",
        (limit,),
    )
    rows = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return rows


def delete_after_sync(record_ids: list[int]):
    """Delete a batch of records after they have been successfully synced to the cloud."""
    if not record_ids:
        return
    conn = get_connection()
    cursor = conn.cursor()
    placeholders = ",".join("?" for _ in record_ids)
    cursor.execute(
        f"DELETE FROM gps_records WHERE id IN ({placeholders})",
        record_ids,
    )
    conn.commit()
    conn.close()
    logger.debug(f"Deleted {len(record_ids)} synced records from local storage")


def get_queue_size() -> int:
    """Return the number of unsynced records."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM gps_records WHERE synced = 0")
    count = cursor.fetchone()[0]
    conn.close()
    return count
