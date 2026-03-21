# System Architecture & Hardware Diagrams

## System Architecture

```mermaid
graph TD
    subgraph Vehicle_Edge_Device [Raspberry Pi - Vehicle]
        GPS[GPS Module] -- NMEA Data --> Parser[gps/gps_parser]
        Parser --> Reader[gps/gps_reader]
        Reader --> Pipeline[Processing Pipeline]

        subgraph Processing [processing/]
            Pipeline --> RD[route_deviation]
            Pipeline --> ID[idle_detection]
            Pipeline --> FM[fuel_model]
        end

        Pipeline -- Enriched Data --> SaveLocal[storage/save_local]
        SaveLocal --> LocalDB[(database/vehicle_data.db)]
        Pipeline --> CloudSend[cloud/api_client]
        LocalDB --> QueueMgr[storage/queue_manager]
        QueueMgr --> SyncSvc[cloud/sync_service]
    end

    subgraph Cloud_Infrastructure [Backend Server]
        CloudSend -- POST /api/gps --> API[Express API]
        SyncSvc -- Retry Unsent --> API
        API --> DB[(SQLite / PostgreSQL)]
        API --> WS[Socket.io Server]
    end

    subgraph Monitoring_Dashboard [Frontend]
        WS -- Real-time Updates --> Dashboard[React + Leaflet + OSM]
        Dashboard -- View Alerts/Paths --> User[Fleet Manager]
    end
```

## Edge Module Architecture

```mermaid
graph LR
    subgraph Config [config/]
        VC[vehicle_config.json]
        RP[route_polygon.json]
        SC[system_config.json]
    end

    subgraph GPS [gps/]
        GR[gps_reader.py]
        GP[gps_parser.py]
    end

    subgraph Proc [processing/]
        DS[distance_speed.py]
        ID[idle_detection.py]
        RD[route_deviation.py]
        FM[fuel_model.py]
        TA[terrain_analysis.py]
    end

    subgraph Utils [utils/]
        HV[haversine.py]
        FL[filters.py]
    end

    subgraph Storage [storage/]
        LDB[local_db.py]
        SL[save_local.py]
        QM[queue_manager.py]
    end

    subgraph Cloud [cloud/]
        AC[api_client.py]
        SS[sync_service.py]
    end

    SC --> ID & FM & RD & AC
    RP --> RD
    VC --> GR

    HV --> DS & RD
    GP --> GR
    LDB --> SL & QM
    QM --> SS
    AC --> SS
```

## Data Flow

```mermaid
sequenceDiagram
    participant GPS as GPS Module
    participant Parser as gps_parser
    participant Main as main.py
    participant RD as route_deviation
    participant ID as idle_detection
    participant FM as fuel_model
    participant DB as Local SQLite
    participant Cloud as api_client
    participant Sync as sync_service
    participant Backend as Express API

    GPS->>Parser: NMEA sentence
    Parser->>Main: {lat, lon, speed, timestamp}
    Main->>RD: check_deviation(lat, lon)
    Main->>ID: update(speed, time)
    Main->>FM: update(speed, stop_starts)
    Main->>DB: save_gps_record(enriched)
    Main->>Cloud: send_to_backend(enriched)
    Cloud-->>Backend: POST /api/gps
    Note over Sync: Runs in background thread
    Sync->>DB: get_unsynced_records()
    Sync->>Cloud: retry send
    Cloud-->>Backend: POST /api/gps
    Sync->>DB: mark_synced()
```

## Hardware Wiring Diagram

```mermaid
graph LR
    RPI[Raspberry Pi]
    GPS1[GPS Module A - UART0]
    GPS2[GPS Module B - USB/UART1]
    Power[5V Power Supply]

    Power --> RPI
    GPS1 -- TX/RX --> RPI
    GPS2 -- USB --> RPI
    GPS1 -- VCC/GND --> Power
    GPS2 -- VCC/GND --> Power
```

### Components Table

| Component | Purpose | Pins/Interface |
|-----------|---------|----------------|
| Raspberry Pi 4 | Edge Computing | - |
| NEO-6M GPS (x2) | Location Tracking | UART (GPIO 14, 15) / USB |
| Breadboard/Wires | Connections | - |
| Power Bank/Adapter| Power | 5V 3A |
