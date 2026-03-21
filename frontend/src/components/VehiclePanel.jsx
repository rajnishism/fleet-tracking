// VehiclePanel.jsx – Left sidebar with vehicle cards and alert log

const ALERT_ICONS = {
    ROUTE_DEVIATION: "🔴",
    IDLE: "🟡",
    FUEL_ANOMALY: "🟣",
};

function timeSince(isoString) {
    if (!isoString) return "";
    const diff = (Date.now() - new Date(isoString).getTime()) / 1000;
    if (diff < 60) return `${Math.floor(diff)}s ago`;
    if (diff < 3600) return `${Math.floor(diff / 60)}m ago`;
    return `${Math.floor(diff / 3600)}h ago`;
}

function VehicleCard({ v, active, onClick }) {
    const { vehicleId, speed_kmh = 0, distance_from_route_m = 0, alerts = [], timestamp, total_distance_m = 0, total_fuel_l = 0 } = v;
    const isMoving = speed_kmh > 2;
    const hasAlert = alerts && alerts.length > 0;
    const badge = hasAlert ? "alert" : isMoving ? "moving" : "idle";
    const badgeLabel = hasAlert ? "ALERT" : isMoving ? "MOVING" : "IDLE";

    return (
        <div className={`vehicle-card${active ? " active" : ""}`} onClick={onClick} id={`vehicle-${vehicleId}`}>
            <div className="vehicle-header">
                <div className="vehicle-icon">🚛</div>
                <div>
                    <div className="vehicle-name">{vehicleId}</div>
                    <div className="vehicle-id">{timeSince(timestamp)}</div>
                </div>
                <span className={`vehicle-badge badge-${badge}`}>{badgeLabel}</span>
            </div>
            <div className="vehicle-stats">
                <div className="stat-item">
                    <div className="stat-value">{speed_kmh?.toFixed(1)}</div>
                    <div className="stat-label">km/h</div>
                </div>
                <div className="stat-item">
                    <div className="stat-value" style={{ color: distance_from_route_m > 50 ? "#ef4444" : "#f1f5f9" }}>
                        {distance_from_route_m?.toFixed(0)}m
                    </div>
                    <div className="stat-label">from route</div>
                </div>
                <div className="stat-item">
                    <div className="stat-value">{(total_distance_m / 1000).toFixed(2)}</div>
                    <div className="stat-label">km travelled</div>
                </div>
                <div className="stat-item">
                    <div className="stat-value">{total_fuel_l.toFixed(2)}</div>
                    <div className="stat-label">L fuel</div>
                </div>
            </div>
        </div>
    );
}

function AlertCard({ alert }) {
    const type = alert.type;
    const icon = ALERT_ICONS[type] || "⚠️";
    return (
        <div className={`alert-card alert-${type}`} id={`alert-${alert.id || Math.random()}`}>
            <div className="alert-header">
                <span className="alert-icon">{icon}</span>
                <span className={`alert-type alert-type-${type}`}>{type.replace(/_/g, " ")}</span>
                <span className="alert-vehicle">{alert.vehicleId}</span>
            </div>
            <div className="alert-message">{alert.message}</div>
            <div className="alert-time">{timeSince(alert.timestamp)}</div>
        </div>
    );
}

export default function VehiclePanel({ vehicleList, alerts, activeVehicle, setActiveVehicle }) {
    // Show only the most recently active vehicle (or the single simulated vehicle)
    const singleVehicle = [...vehicleList].sort((a, b) => new Date(b.timestamp || 0) - new Date(a.timestamp || 0)).slice(0, 1);

    return (
        <div className="sidebar">
            <div className="sidebar-section">
                <div className="sidebar-label">Active Vehicle</div>
                <div className="vehicles-list">
                    {singleVehicle.length === 0 ? (
                        <div className="empty-state">
                            <div className="icon">🚛</div>
                            <p>No vehicles detected. Start the edge simulator.</p>
                        </div>
                    ) : (
                        singleVehicle.map((v) => (
                            <VehicleCard
                                key={v.vehicleId}
                                v={v}
                                active={activeVehicle === v.vehicleId}
                                onClick={() => setActiveVehicle(v.vehicleId === activeVehicle ? null : v.vehicleId)}
                            />
                        ))
                    )}
                </div>
            </div>

            <div className="sidebar-section" style={{ borderBottom: "none", flex: 1, overflow: "hidden", display: "flex", flexDirection: "column" }}>
                <div className="sidebar-label">Live Alerts ({alerts.length})</div>
                <div className="alerts-panel">
                    {alerts.length === 0 ? (
                        <div className="empty-state">
                            <div className="icon">✅</div>
                            <p>No alerts. All vehicles operating normally.</p>
                        </div>
                    ) : (
                        alerts.map((a, i) => <AlertCard key={a.id || i} alert={a} />)
                    )}
                </div>
            </div>
        </div>
    );
}
