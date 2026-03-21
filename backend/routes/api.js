/**
 * routes/api.js
 * REST API routes for the Fleet Tracking system.
 *
 * POST /api/gps         – Ingest GPS data from edge device
 * GET  /api/vehicles    – List all tracked vehicles
 * GET  /api/history/:id – Location history for a vehicle
 * GET  /api/alerts      – Recent alerts (optionally filtered by vehicle)
 */

const express = require("express");
const { PrismaClient } = require("@prisma/client");

const router = express.Router();
const prisma = new PrismaClient();

// ─── POST /api/gps ────────────────────────────────────────────────────────────
router.post("/gps", async (req, res) => {
    try {
        const {
            vehicle_id,
            latitude,
            longitude,
            speed_kmh,
            timestamp,
            distance_from_route_m,
            distance_step_m,
            fuel_consumed_liters,
            alerts = [],
        } = req.body;

        if (!vehicle_id || latitude === undefined || longitude === undefined) {
            return res.status(400).json({ error: "Missing required fields" });
        }

        let elevation = 0;
        try {
            const response = await fetch(`https://api.open-elevation.com/api/v1/lookup?locations=${latitude},${longitude}`);
            if (response.ok) {
                const data = await response.json();
                if (data.results && data.results.length > 0) {
                    elevation = data.results[0].elevation || 0;
                }
            }
        } catch (error) {
            console.error("[POST /api/gps] Elevation fetch error:", error.message);
        }

        // Upsert vehicle record
        await prisma.vehicle.upsert({
            where: { vehicleId: vehicle_id },
            update: {},
            create: { vehicleId: vehicle_id, name: vehicle_id },
        });

        // Store location
        const location = await prisma.location.create({
            data: {
                vehicleId: vehicle_id,
                latitude,
                longitude,
                elevation: elevation || 0,
                speedKmh: speed_kmh || 0,
                timestamp: timestamp || new Date().toISOString(),
                distFromRouteM: distance_from_route_m || 0,
                distanceStepM: distance_step_m || 0,
                fuelConsumedLiters: fuel_consumed_liters || 0,
            },
        });

        // Store alerts
        const savedAlerts = [];
        for (const alert of alerts) {
            const saved = await prisma.alert.create({
                data: {
                    vehicleId: vehicle_id,
                    type: alert.type,
                    message: alert.message,
                    metadata: JSON.stringify(alert),
                },
            });
            savedAlerts.push(saved);
        }

        // Broadcast real-time update to all connected frontend clients
        const payload = {
            vehicle_id,
            latitude,
            longitude,
            elevation,
            speed_kmh,
            timestamp,
            distance_from_route_m,
            distance_step_m,
            fuel_consumed_liters,
            alerts: savedAlerts,
        };
        req.io.emit("gps_update", payload);

        return res.json({ success: true, location, alerts: savedAlerts });
    } catch (err) {
        console.error("[POST /api/gps] Error:", err);
        return res.status(500).json({ error: "Internal server error" });
    }
});

// ─── GET /api/vehicles ────────────────────────────────────────────────────────
router.get("/vehicles", async (_req, res) => {
    try {
        const vehicles = await prisma.vehicle.findMany({
            include: {
                locations: {
                    orderBy: { createdAt: "desc" },
                    take: 1,
                },
            },
        });
        return res.json(vehicles);
    } catch (err) {
        console.error("[GET /api/vehicles] Error:", err);
        return res.status(500).json({ error: "Internal server error" });
    }
});

// ─── POST /api/vehicles ────────────────────────────────────────────────────────
router.post("/vehicles", async (req, res) => {
    try {
        const { vehicleId, name } = req.body;
        if (!vehicleId) return res.status(400).json({ error: "Missing vehicleId" });
        const vehicle = await prisma.vehicle.upsert({
            where: { vehicleId },
            update: {},
            create: { vehicleId, name: name || vehicleId },
        });
        return res.json({ success: true, vehicle });
    } catch (err) {
        console.error("[POST /api/vehicles] Error:", err);
        return res.status(500).json({ error: "Internal server error" });
    }
});

// ─── DELETE /api/vehicles/:vehicleId ──────────────────────────────────────────
router.delete("/vehicles/:vehicleId", async (req, res) => {
    try {
        const { vehicleId } = req.params;
        
        // Delete related child records first to avoid foreign key constrain errors
        // (if cascade delete isn't set up in the DB schema)
        await prisma.location.deleteMany({ where: { vehicleId } });
        await prisma.alert.deleteMany({ where: { vehicleId } });
        
        // Delete the actual vehicle
        await prisma.vehicle.delete({
            where: { vehicleId }
        });
        
        return res.json({ success: true, message: `Vehicle ${vehicleId} deleted successfully` });
    } catch (err) {
        console.error("[DELETE /api/vehicles] Error:", err);
        return res.status(500).json({ error: "Internal server error" });
    }
});

// ─── GET /api/history/:id ─────────────────────────────────────────────────────
router.get("/history/:vehicleId", async (req, res) => {
    try {
        const { vehicleId } = req.params;
        const limit = parseInt(req.query.limit) || 500;
        const locations = await prisma.location.findMany({
            where: { vehicleId },
            orderBy: { createdAt: "asc" },
            take: limit,
        });
        return res.json(locations);
    } catch (err) {
        console.error("[GET /api/history] Error:", err);
        return res.status(500).json({ error: "Internal server error" });
    }
});

// ─── GET /api/alerts ──────────────────────────────────────────────────────────
router.get("/alerts", async (req, res) => {
    try {
        const { vehicleId, type, limit = "50" } = req.query;
        const where = {};
        if (vehicleId) where.vehicleId = vehicleId;
        if (type) where.type = type;

        const alerts = await prisma.alert.findMany({
            where,
            orderBy: { timestamp: "desc" },
            take: parseInt(limit),
        });
        return res.json(alerts);
    } catch (err) {
        console.error("[GET /api/alerts] Error:", err);
        return res.status(500).json({ error: "Internal server error" });
    }
});

module.exports = router;
