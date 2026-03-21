"""
local_db.py
SQLite database connection manager for offline GPS data storage.
"""

import sqlite3
import os
import logging

logger = logging.getLogger(__name__)

DB_DIR = os.path.join(os.path.dirname(__file__), "..", "database")
DB_PATH = os.path.join(DB_DIR, "vehicle_data.db")

# Ensure database directory exists
os.makedirs(DB_DIR, exist_ok=True)


def get_connection() -> sqlite3.Connection:
    """Return a SQLite connection to the local vehicle database."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """Create tables if they don't exist."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS gps_records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            vehicle_id TEXT NOT NULL,
            latitude REAL NOT NULL,
            longitude REAL NOT NULL,
            speed_kmh REAL,
            timestamp TEXT,
            distance_from_route_m REAL,
            distance_step_m REAL,
            fuel_consumed_liters REAL,
            alerts TEXT,
            synced INTEGER DEFAULT 0,
            created_at TEXT DEFAULT (datetime('now'))
        )
    """)

    conn.commit()
    conn.close()
    logger.info(f"Database initialised at {DB_PATH}")


# Auto-initialise on import
init_db()
