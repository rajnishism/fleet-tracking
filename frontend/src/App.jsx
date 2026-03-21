// App.jsx – Fleet Tracking Dashboard root component

import { useState } from "react";
import MapView from "./components/MapView";
import VehiclePanel from "./components/VehiclePanel";
import { useFleetData } from "./hooks/useFleetData";
import "./index.css";

export default function App() {
  const { vehicleList, alerts, alertCount, connected } = useFleetData();
  const [activeVehicle, setActiveVehicle] = useState(null);

  const displayVehicles = activeVehicle
    ? vehicleList.filter((v) => v.vehicleId === activeVehicle)
    : vehicleList;

  return (
    <div className="app-layout">
      {/* Header */}
      <header className="header">
        <div className="header-logo">⛏️</div>
        <div>
          <div className="header-title">Fleet<span>Tracker</span></div>
        </div>
        <div className="header-right">
          <div className="header-stat">
            <strong>{vehicleList.length}</strong> Vehicles
          </div>
          <div className="header-stat">
            <strong style={{ color: alertCount > 0 ? "#ef4444" : "#22c55e" }}>
              {alertCount}
            </strong>{" "}
            Alerts
          </div>
          <div style={{ display: "flex", alignItems: "center", gap: "6px", fontSize: "12px", color: "var(--text-sec)" }}>
            <div
              className="status-dot"
              style={{ background: connected ? "var(--success)" : "#ef4444", boxShadow: `0 0 8px ${connected ? "var(--success)" : "#ef4444"}` }}
            />
            {connected ? "Live" : "Connecting…"}
          </div>
        </div>
      </header>

      {/* Left sidebar */}
      <VehiclePanel
        vehicleList={vehicleList}
        alerts={alerts}
        activeVehicle={activeVehicle}
        setActiveVehicle={setActiveVehicle}
      />

      {/* Leaflet + OSM map */}
      <MapView vehicles={displayVehicles} />
    </div>
  );
}
