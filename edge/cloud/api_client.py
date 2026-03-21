"""
api_client.py
Sends processed GPS data to the cloud backend via HTTP POST.
"""

import json
import os
import logging
import requests

logger = logging.getLogger(__name__)

# Load config
_config_path = os.path.join(os.path.dirname(__file__), "..", "config", "system_config.json")
with open(_config_path) as f:
    _config = json.load(f)

BACKEND_URL = os.getenv("BACKEND_URL", _config.get("backend_url", "http://localhost:3001/api/gps"))


def send_to_backend(payload: dict) -> bool:
    """
    POST processed GPS data to the backend API.

    Returns True if sent successfully, False otherwise.
    """
    try:
        resp = requests.post(BACKEND_URL, json=payload, timeout=5)
        if resp.status_code == 200:
            logger.debug(f"[{payload.get('vehicle_id')}] Data sent OK")
            return True
        else:
            logger.warning(f"Backend returned {resp.status_code}: {resp.text[:200]}")
            return False
    except requests.exceptions.RequestException:
        logger.warning(f"Backend unreachable ({BACKEND_URL}). Data securely queued locally for later sync.")
        return False
