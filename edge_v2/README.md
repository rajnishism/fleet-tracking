# edge_v2 — Alternative Edge Logic

Alternative implementation of the Fleet Tracker edge layer.
References and reuses `edge/` for cloud, storage, GPS reader, and config —
only the processing logic and pipeline architecture are different.

---

## What's different from `edge/`

### Architecture

| Concern | `edge/` (v1) | `edge_v2/` (v2) |
|---|---|---|
| Per-vehicle state | Bare local variables (`idle_start_time`, `stop_start_count`, `speed_history`) | `VehicleState` dataclass per vehicle, stored in a dict keyed by `vehicle_id` |
| Multi-vehicle support | One thread per vehicle, manually configured | Single pipeline thread drains a shared queue; new vehicles are auto-registered on first fix |
| Simulator output | Single generator for one vehicle | Multi-vehicle threaded simulator → shared `queue.Queue` |
| GPS input | Raw coordinates used directly | Kalman-filtered before motion calculations |

---

### Module-level differences

#### `utils/filters.py`
- **v1** — two independent 1D Kalman filters (one per axis) + moving average.
- **v2** — `GPSKalmanFilter2D`: 4-state filter `[lat, lon, vel_lat, vel_lon]`.
  Velocity is part of the state, so the prediction step extrapolates position
  using the truck's current heading — physically correct for a moving vehicle.
  Also adds `exponential_moving_average()` for lightweight streaming smoothing.

#### `processing/distance_speed.py`
- **v1** — plain `haversine()` + `distance/time × 3.6`, returns bare floats.
- **v2** — `compute_motion()` returns a `MotionData` named tuple:
  `(distance_m, speed_kmh, bearing_deg, acceleration_ms2)`.
  Bearing (0–360° compass heading) is forwarded to the dashboard for
  directional truck icons. Acceleration feeds the physics fuel model.

#### `processing/route_deviation.py`
- **v1** — stateless `check_deviation()` scans all segments every call; one
  severity level.
- **v2** — `RouteTracker` class tracks forward progress (furthest segment index
  reached). Prevents the truck from snapping back to an earlier segment it
  already passed. Two severity levels: `WARNING` (>50 m) and `CRITICAL` (>100 m).
  Wrong-direction detection fires a `WRONG_DIRECTION` alert after 3 consecutive
  backward-progress readings.

#### `processing/idle_detection.py`
- **v1** — binary: `speed < 2 km/h → "idle"`. Prone to flapping at borderline speeds.
- **v2** — `IdleDetector` hysteresis state machine:
  - Enter idle: speed < 2 km/h for **3 consecutive** readings.
  - Exit idle: speed > 5 km/h for **2 consecutive** readings.
  - Classifies idle as `FULL_STOP` (speed ≈ 0) vs `CRAWL` (slow but non-zero).

#### `processing/fuel_model.py`
- **v1** — linear heuristic `rate = 10 + speed/5` L/h; anomaly via stop-start
  count and speed variance.
- **v2** — physics model:
  ```
  F_roll    = C_rr × m × g             (rolling resistance)
  F_inertia = m × a                     (inertial force)
  P_shaft   = (F_roll + F_inertia) × v / η_drivetrain
  rate(L/h) = P_shaft(kW) × BSFC / ρ_diesel
  ```
  `FuelAnomalyDetector` compares instantaneous rate against an EMA baseline —
  fires when `rate > 2 × EMA`. Also exposes `fuel_efficiency_l_per_tonne_km()`
  as an operational KPI metric.

#### `simulator.py`
- **v1** — single vehicle generator.
- **v2** — reads a `"vehicles": [...]` list from `vehicle_config.json`; one
  daemon thread per vehicle pushes into a shared `queue.Queue`. Falls back to
  v1-style single-vehicle config automatically.
  Adds **Gaussian GPS noise** (σ ≈ 3 m) to exercise the Kalman filter.

---

## Running

```bash
# From the edge_v2 directory
python main.py --mode simulate   # multi-vehicle simulator
python main.py --mode hardware   # real GPS hardware
```

The backend and frontend from `backend/` and `frontend/` work unchanged —
`edge_v2` posts to the same `/api/gps` endpoint.

---

## Multi-vehicle simulator config

Add a `"vehicles"` list to `edge/config/vehicle_config.json`:

```json
{
  "vehicles": [
    { "vehicle_id": "Truck_1", "scenario": "normal" },
    { "vehicle_id": "Truck_2", "scenario": "deviation" },
    { "vehicle_id": "Truck_3", "scenario": "fuel_anomaly" },
    { "vehicle_id": "Truck_4", "scenario": "idle" }
  ]
}
```

Or leave the existing single-vehicle format — `run_multi_simulator()` handles both.

---

## What is reused from `edge/` (unchanged)

| Component | Reason |
|---|---|
| `cloud/api_client.py` | Same HTTP POST interface |
| `cloud/sync_service.py` | Same SQLite retry logic |
| `storage/save_local.py` | Same DB schema |
| `storage/local_db.py` | Same SQLite connection |
| `storage/queue_manager.py` | Same queue table |
| `gps/gps_reader.py` | Same serial reader for hardware mode |
| `config/*.json` | Shared thresholds and route data |
