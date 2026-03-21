"""
gps_reader.py
Reads raw GPS data from a serial GPS device connected via UART/USB.
"""

import serial
import logging
import time

from gps.gps_parser import parse_gprmc

logger = logging.getLogger(__name__)


from typing import Generator

def read_gps_data(port: str, vehicle_id: str = "truck_unknown", baud: int = 9600) -> Generator[dict, None, None]:
    """Generator: connects to a serial port and yields parsed GPS data dicts as they arrive."""
    logger.info(f"Opening serial port {port}")
    while True:
        try:
            with serial.Serial(port, baud, timeout=1) as ser:
                while True:
                    line = ser.readline().decode("ascii", errors="replace").strip()
                    if line.startswith("$GPRMC"):
                        data = parse_gprmc(line)
                        if data:
                            data["vehicle_id"] = vehicle_id
                            yield data
        except serial.SerialException as e:
            logger.error(f"Serial error: {e}")
            time.sleep(1)
        except Exception as e:
            logger.error(f"Unexpected error: {e}")
            time.sleep(0.5)
