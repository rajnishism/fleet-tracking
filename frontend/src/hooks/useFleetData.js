// useFleetData.js
// Custom hook: manages real-time GPS data via Socket.io and REST API

import { useState, useEffect, useRef } from "react";
import { io } from "socket.io-client";

const BACKEND = import.meta.env.VITE_BACKEND_URL || "http://localhost:3001";
const MAX_HISTORY_POINTS = 200;

export function useFleetData() {
    const [vehicles, setVehicles] = useState({});   // { vehicleId: { ...latest state, path: [] } }
    const [alerts, setAlerts] = useState([]);        // last N alerts, newest first
    const [connected, setConnected] = useState(false);
    const socketRef = useRef(null);

    // Load initial history on mount
    useEffect(() => {
        async function loadInitialData() {
            try {
                const vRes = await fetch(`${BACKEND}/api/vehicles`);
                const vehicleList = await vRes.json();

                const state = {};
                for (const v of vehicleList) {
                    const hRes = await fetch(`${BACKEND}/api/history/${v.vehicleId}?limit=200`);
                    const history = await hRes.json();

                    let total_distance_m = 0;
                    let total_fuel_l = 0;
                    for (const h of history) {
                        total_distance_m += h.distanceStepM || 0;
                        total_fuel_l += h.fuelConsumedLiters || 0;
                    }

                    const latest = history[history.length - 1] || {};
                    state[v.vehicleId] = {
                        vehicleId: v.vehicleId,
                        latitude: latest.latitude || 0,
                        longitude: latest.longitude || 0,
                        speed_kmh: latest.speedKmh || 0,
                        timestamp: latest.timestamp || "",
                        distance_from_route_m: latest.distFromRouteM || 0,
                        distance_step_m: latest.distanceStepM || 0,
                        fuel_consumed_liters: latest.fuelConsumedLiters || 0,
                        total_distance_m,
                        total_fuel_l,
                        path: history.map((h) => [h.longitude, h.latitude]),
                        alerts: [],
                    };
                }
                setVehicles(state);

                const aRes = await fetch(`${BACKEND}/api/alerts?limit=50`);
                const alertList = await aRes.json();
                setAlerts(alertList);
            } catch (e) {
                console.warn("Initial data load failed:", e.message);
            }
        }
        loadInitialData();
    }, []);

    // Socket.io real-time updates
    useEffect(() => {
        const socket = io(BACKEND, { transports: ["websocket"] });
        socketRef.current = socket;

        socket.on("connect", () => setConnected(true));
        socket.on("disconnect", () => setConnected(false));

        socket.on("gps_update", (data) => {
            const { vehicle_id, latitude, longitude, speed_kmh, timestamp, distance_from_route_m, distance_step_m, fuel_consumed_liters, alerts: newAlerts } = data;

            setVehicles((prev) => {
                const existing = prev[vehicle_id] || { path: [], alerts: [] };
                const newPath = [...existing.path, [longitude, latitude]].slice(-MAX_HISTORY_POINTS);
                return {
                    ...prev,
                    [vehicle_id]: {
                        ...existing,
                        vehicleId: vehicle_id,
                        latitude,
                        longitude,
                        speed_kmh,
                        timestamp,
                        distance_from_route_m,
                        distance_step_m,
                        fuel_consumed_liters,
                        total_distance_m: (existing.total_distance_m || 0) + (distance_step_m || 0),
                        total_fuel_l: (existing.total_fuel_l || 0) + (fuel_consumed_liters || 0),
                        path: newPath,
                        alerts: newAlerts,
                    },
                };
            });

            if (newAlerts && newAlerts.length > 0) {
                setAlerts((prev) =>
                    [
                        ...newAlerts.map((a) => ({ ...a, vehicleId: vehicle_id, timestamp: new Date().toISOString() })),
                        ...prev,
                    ].slice(0, 100)
                );
            }
        });

        return () => socket.disconnect();
    }, []);

    const vehicleList = Object.values(vehicles);
    const alertCount = alerts.length;

    return { vehicles, vehicleList, alerts, alertCount, connected };
}
