// MapView.jsx – Leaflet + OpenStreetMap real-time map component

import { useEffect, useRef, useState } from "react";
import L from "leaflet";
import "leaflet/dist/leaflet.css";

// Haul road reference – must match edge/processing.py
// Leaflet coordinate order: [latitude, longitude]
const HAUL_ROAD = [
    [22.57880229756819, 88.36969394973784],
    [22.580833114238516, 88.37058444313118],
    [22.58244421708912, 88.37122423126971],
    [22.582043839780155, 88.3728141842684],
    [22.581754677666694, 88.37428368627724],
    [22.582733377753357, 88.37440413726239],
    [22.585224331768913, 88.37474126398348],
    [22.58998342262089, 88.37499393424264],
    [22.59427579487317, 88.37529713855469],
    [22.594648674166734, 88.37106504472382],
    [22.594872787152596, 88.36955987184024],
    [22.595181081445148, 88.36814666484435],
    [22.595911648349954, 88.36517959745004],
    [22.59195481443612, 88.3640587058087],
    [22.588789175020608, 88.36333339971799],
    [22.58623226236911, 88.36254216041613],
    [22.58586701647988, 88.36583894828505],
    [22.58580615156015, 88.36768516823315],
    [22.582518647732996, 88.3663004847337],
    [22.58124014307117, 88.36564124443777],
    [22.580509595907927, 88.36814666444559],
    [22.57819606891107, 88.36755331070492],
    [22.577769829475486, 88.36939963868906],
    [22.578926645333794, 88.36959735525585]
];

const VEHICLE_COLORS = {
    Truck_1: "#3b82f6",
};

function getColor(vehicleId) {
    return VEHICLE_COLORS[vehicleId] || "#22c55e";
}

function createMarkerIcon(color) {
    return L.divIcon({
        className: "",
        html: `
            <div style="
                width: 36px; height: 36px;
                background: ${color};
                border: 3px solid #fff;
                border-radius: 50% 50% 50% 0;
                transform: rotate(-45deg);
                box-shadow: 0 2px 12px ${color}80;
                display: flex; align-items: center; justify-content: center;
            ">
                <span style="transform: rotate(45deg); font-size: 14px;">🚛</span>
            </div>
        `,
        iconSize: [36, 36],
        iconAnchor: [18, 36],
        popupAnchor: [0, -36],
    });
}

export default function MapView({ vehicles }) {
    const mapContainer = useRef(null);
    const map = useRef(null);
    const markersRef = useRef({});
    const pathLinesRef = useRef({});
    const haulRoadRef = useRef(null);
    const hasInitialCentered = useRef(false);

    // Initialize map once
    useEffect(() => {
        if (map.current) return;

        map.current = L.map(mapContainer.current, {
            center: [22.5737, 88.3650],    // [lat, lng] – Kolkata / mining area
            zoom: 5,
            zoomControl: true,
        });

        const osm = L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', { maxZoom: 19 });
        const dark = L.tileLayer('https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png', { maxZoom: 19 });
        const topo = L.tileLayer('https://{s}.tile.opentopomap.org/{z}/{x}/{y}.png', { maxZoom: 19 });
        const satellite = L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}', { maxZoom: 19 });

        const baseMaps = {
            "Satellite": satellite,
            "Dark": dark,
            "Topo": topo,
            "OSM": osm
        };

        satellite.addTo(map.current); // default view
        L.control.layers(baseMaps).addTo(map.current);

        // Draw reference haul road
        haulRoadRef.current = L.polyline(HAUL_ROAD, {
            color: "#f59e0b",
            weight: 4,
            dashArray: "12 9",
            opacity: 0.8,
        }).addTo(map.current);

        return () => {
            map.current?.remove();
            map.current = null;
        };
    }, []);

    // Update vehicles on map
    useEffect(() => {
        if (!map.current) return;

        for (const v of vehicles) {
            const { vehicleId, latitude, longitude, path, speed_kmh, distance_from_route_m, alerts = [] } = v;
            if (!latitude || !longitude) continue;

            const color = getColor(vehicleId);
            const hasAlert = alerts && alerts.length > 0;

            // ── Path line ──
            const pathCoords = (path || []).map(([lng, lat]) => [lat, lng]);
            if (pathLinesRef.current[vehicleId]) {
                pathLinesRef.current[vehicleId].setLatLngs(pathCoords);
            } else {
                pathLinesRef.current[vehicleId] = L.polyline(pathCoords, {
                    color,
                    weight: 2,
                    opacity: 0.8,
                }).addTo(map.current);
            }

            // ── Marker ──
            if (markersRef.current[vehicleId]) {
                markersRef.current[vehicleId].setLatLng([latitude, longitude]);
                // Update popup content
                markersRef.current[vehicleId].setPopupContent(`
                    <div style="font-family:Inter,sans-serif; padding:4px;">
                        <strong style="color:#1e293b;">${vehicleId}</strong><br/>
                        <span style="color:#64748b; font-size:12px;">Speed: ${speed_kmh?.toFixed(1)} km/h</span><br/>
                        <span style="color:#ef4444; font-size:12px;">Deviation: ${distance_from_route_m?.toFixed(1)} m</span>
                    </div>
                `);
            } else {
                const marker = L.marker([latitude, longitude], {
                    icon: createMarkerIcon(color),
                })
                    .bindPopup(`
                        <div style="font-family:Inter,sans-serif; padding:4px;">
                            <strong style="color:#1e293b;">${vehicleId}</strong><br/>
                            <span style="color:#64748b; font-size:12px;">Speed: ${speed_kmh?.toFixed(1)} km/h</span><br/>
                            <span style="color:#ef4444; font-size:12px;">Deviation: ${distance_from_route_m?.toFixed(1)} m</span>
                        </div>
                    `)
                    .addTo(map.current);
                markersRef.current[vehicleId] = marker;
            }

            // Alert pulse ring
            const el = markersRef.current[vehicleId]?.getElement();
            if (el) {
                const inner = el.querySelector("div");
                if (inner) {
                    inner.style.boxShadow = hasAlert
                        ? `0 0 0 6px rgba(239,68,68,0.3), 0 2px 12px ${color}80`
                        : `0 2px 12px ${color}80`;
                }
            }
        }

        // Fit bounds to all vehicles ONLY on first load so user can pan normally afterwards
        if (!hasInitialCentered.current) {
            const coords = vehicles.filter((v) => v.latitude).map((v) => [v.latitude, v.longitude]);
            if (coords.length > 0) {
                map.current.fitBounds(coords, { padding: [80, 80], maxZoom: 15 });
                hasInitialCentered.current = true;
            }
        }
    }, [vehicles]);

    const handleRecenter = () => {
        if (!map.current) return;
        const coords = vehicles.filter((v) => v.latitude).map((v) => [v.latitude, v.longitude]);
        if (coords.length > 0) {
            map.current.fitBounds(coords, { padding: [80, 80], maxZoom: 15 });
        } else {
            map.current.fitBounds(HAUL_ROAD, { padding: [80, 80], maxZoom: 15 });
        }
    };

    return (
        <div className="map-container" style={{ position: "relative", width: "100%", height: "100%" }}>
            <div ref={mapContainer} style={{ width: "100%", height: "100%" }} />
            <div className="map-legend">
                <div className="legend-title">Legend</div>
                <div className="legend-item"><div className="legend-dot" style={{ background: "#f59e0b" }} />Haul Road</div>
                <div className="legend-item"><div className="legend-dot" style={{ background: "#3b82f6" }} />Truck 1</div>
                <div className="legend-item"><div className="legend-dot" style={{ background: "#a855f7" }} />Truck 2</div>
                <div className="legend-item"><div className="legend-dot" style={{ background: "#ef4444" }} />Alert</div>
            </div>
            
            <button 
                onClick={handleRecenter}
                style={{
                    position: "absolute",
                    bottom: "30px",
                    right: "30px",
                    zIndex: 1000,
                    padding: "10px 16px",
                    backgroundColor: "#1e293b",
                    color: "white",
                    border: "1px solid #334155",
                    borderRadius: "8px",
                    cursor: "pointer",
                    boxShadow: "0 4px 6px -1px rgba(0, 0, 0, 0.5)",
                    fontWeight: "600",
                    display: "flex",
                    alignItems: "center",
                    gap: "6px",
                    transition: "all 0.2s"
                }}
                onMouseOver={(e) => e.target.style.backgroundColor = '#334155'}
                onMouseOut={(e) => e.target.style.backgroundColor = '#1e293b'}
            >
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                    <circle cx="12" cy="12" r="10"></circle>
                    <line x1="12" y1="8" x2="12" y2="12"></line>
                    <line x1="12" y1="16" x2="12.01" y2="16"></line>
                </svg>
                Recenter
            </button>
        </div>
    );
}
