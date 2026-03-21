# ⛏️ Fleet Tracker – GPS-Based Mining Vehicle Monitor

A real-time GPS monitoring system for mining haul trucks. Detects route deviations, excessive idling, and simulated fuel anomalies. Built with a Raspberry Pi edge layer, Express + Socket.io backend, and Leaflet + OpenStreetMap dashboard.

---

## 📐 Architecture

```
GPS Modules → Raspberry Pi (Edge) → HTTP API → Express Backend → SQLite DB
              ↕ Local SQLite                          ↓
              (offline buffer)              Socket.io (real-time)
                                                      ↓
                                      Leaflet + OSM React Dashboard
```

---

## ✨ New Features

- **Topographical Elevation Integration**: The Node backend automatically fetches precise altitude readings from the open-source **Open-Elevation API** upon GPS data ingest and streams it down via WebSocket.
- **Toggleable Map Tiles**: Switch seamlessly between **OSM**, **Dark Mode**, **Topo**, and **Satellite Map** layers directly from the Leaflet interface control.
- **Advanced Telemetry Dashboard**: The frontend UI now tracks, aggregates, and prominently displays total **Distance Travelled** and **Fuel Consumed**.
- **Live Route Deviation Popups**: Map markers instantly show real-time deviation distances directly in the marker popups.
- **Robust Excel Exporting**: The `export_to_excel.py` script now comprehensively bundles your Topography `elevation`, `fuel_consumed_liters`, and routing metrics into separate formatted sheets!
- **Fast Database Resetting**: Included a `reset_dbs.sh` Bash script to instantly wipe both Edge and Cloud SQLite instances for immediate blank-slate test drives.

---

## 📂 Project Structure

```
Fleet Tracking/
├── edge/                         # Raspberry Pi edge code (Python)
│   ├── gps/
│   │   ├── gps_reader.py         # Serial GPS reader
│   │   └── gps_parser.py         # NMEA sentence parser
│   ├── processing/
│   │   ├── distance_speed.py     # Distance, speed, acceleration
│   │   ├── idle_detection.py     # Idle alert detection
│   │   ├── route_deviation.py    # Route deviation checker
│   │   ├── fuel_model.py         # Fuel anomaly monitor
│   │   └── terrain_analysis.py   # DEM terrain analysis (placeholder)
│   ├── storage/
│   │   ├── local_db.py           # SQLite connection manager
│   │   ├── save_local.py         # Save GPS records locally
│   │   └── queue_manager.py      # Track unsent records
│   ├── cloud/
│   │   ├── api_client.py         # HTTP POST to backend
│   │   └── sync_service.py       # Background retry sync
│   ├── dem/
│   │   ├── dem_loader.py         # GeoTIFF DEM loader
│   │   └── elevation_lookup.py   # Lat/lon → elevation
│   ├── config/
│   │   ├── vehicle_config.json   # Vehicle specs & scenarios
│   │   ├── route_polygon.json    # Haul road waypoints
│   │   └── system_config.json    # Thresholds & parameters
│   ├── utils/
│   │   ├── haversine.py          # Distance helpers
│   │   └── filters.py            # Kalman / moving-average
│   ├── database/
│   │   └── vehicle_data.db       # Auto-created SQLite DB
│   ├── main.py                   # Entry point (hardware or simulate)
│   ├── simulator.py              # GPS simulator (no hardware needed)
│   └── requirements.txt
├── backend/                      # Express.js server
│   ├── server.js                 # Main server + Socket.io
│   ├── routes/api.js             # REST API routes
│   ├── prisma/schema.prisma      # Database schema
│   └── .env                      # Environment config
├── frontend/                     # React + Vite + Leaflet dashboard
│   ├── src/
│   │   ├── App.jsx
│   │   ├── components/
│   │   │   ├── MapView.jsx       # Leaflet + OSM map
│   │   │   └── VehiclePanel.jsx
│   │   └── hooks/useFleetData.js
│   └── .env
├── docs/diagrams.md              # Architecture & wiring diagrams
├── start.sh                      # Launcher script
└── README.md
```

---

## 🚀 Quick Start

### 1. Backend

```bash
cd backend
cp .env .env.local   # edit FRONTEND_URL if needed
npm install
npx prisma generate
npx prisma db push
node server.js
```

### 2. Frontend

```bash
cd frontend
npm install
npm run dev
```

> Open **http://localhost:5173** — uses free OpenStreetMap tiles, no API key needed.

### 3. Edge Simulator (no hardware)

```bash
cd edge
pip install -r requirements.txt
python3 main.py --mode simulate
```

### 4. Real Hardware (Raspberry Pi)

```bash
cd edge
pip install -r requirements.txt
export BACKEND_URL=http://<server-ip>:3001/api/gps
export GPS_PORT_Truck_1=/dev/ttyUSB0
python3 main.py --mode hardware
```

> Vehicle GPS port and scenario is configured in `edge/config/vehicle_config.json`.

---

## 🔌 API Reference

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/gps` | Ingest GPS data from edge |
| GET | `/api/vehicles` | List all vehicles |
| GET | `/api/history/:id` | Location history for a vehicle |
| GET | `/api/alerts` | Recent alerts |

---

## 🧠 Alert Types

| Alert | Trigger |
|-------|---------|
| `ROUTE_DEVIATION` | Vehicle > 50m from defined haul road |
| `IDLE` | Speed ≈ 0 for > 5 minutes |
| `FUEL_ANOMALY` | Erratic speed variance or repeated stop/starts |

> All thresholds are configurable in `edge/config/system_config.json`.

---

## 🗺️ Map Setup

The frontend uses **OpenStreetMap** tiles via **Leaflet** — completely free, no API key required.

---

## 🌍 Deployment

### Backend (Render / Railway)
```bash
# Set environment variables in dashboard:
DATABASE_URL=file:./fleet.db
PORT=3001
FRONTEND_URL=https://your-frontend.vercel.app
```

### Frontend (Vercel / Netlify)
```bash
# Set environment variables:
VITE_BACKEND_URL=https://your-backend.onrender.com
```

---

## 📡 Scaling to 500+ Vehicles

| Concern | Solution |
|---------|----------|
| Database | Migrate from SQLite → PostgreSQL + TimescaleDB |
| Message broker | Switch to MQTT (Mosquitto broker) |
| Real-time | Change Socket.io to topic-based pub/sub |
| Deployment | Containerize with Docker + Kubernetes |

---

## 🔧 Environment Variables

### Backend (`backend/.env`)
```
PORT=3001
DATABASE_URL="file:./fleet.db"
FRONTEND_URL=http://localhost:5173
```

### Frontend (`frontend/.env`)
```
VITE_BACKEND_URL=http://localhost:3001
```

### Edge (`edge/.env`)
```
BACKEND_URL=http://localhost:3001/api/gps
GPS_PORT_Truck_1=/dev/ttyUSB0
SEND_INTERVAL=2
```

---

## 🔮 Future Scope

The following features and enhancements are planned for future iterations of this project:

1. **Fuel Consumption Model Optimization**: Upgrading the simplistic simulation model by incorporating deeply dynamic variables such as engine data load factor, transmission states, vehicle payloads, and RPM telemetry.
2. **DEM-Based Gradient Analysis**: Implementing Digital Elevation Model (DEM) data to dynamically calculate the gradient between topographical GPS points. This will explicitly track whether a vehicle is traveling uphill or downhill, profoundly impacting accurate fuel anomaly detections.
