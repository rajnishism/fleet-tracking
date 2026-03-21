/**
 * server.js
 * Main Express + Socket.io server for Fleet Tracking backend.
 */

const express = require("express");
const http = require("http");
const { Server } = require("socket.io");
const cors = require("cors");
const dotenv = require("dotenv");

dotenv.config();

const apiRouter = require("./routes/api");

const app = express();
const server = http.createServer(app);

const io = new Server(server, {
    cors: {
        origin: process.env.FRONTEND_URL || "*",
        methods: ["GET", "POST"],
    },
});

// ─── Middleware ───────────────────────────────────────────────────────────────
app.use(cors({ origin: process.env.FRONTEND_URL || "*" }));
app.use(express.json());

// Attach io to req so routes can emit events
app.use((req, _res, next) => {
    req.io = io;
    next();
});

// ─── Routes ───────────────────────────────────────────────────────────────────
app.use("/api", apiRouter);

app.get("/health", (_req, res) => res.json({ status: "ok" }));

// ─── Socket.io ────────────────────────────────────────────────────────────────
io.on("connection", (socket) => {
    console.log(`[Socket.io] Client connected: ${socket.id}`);
    socket.on("disconnect", () => {
        console.log(`[Socket.io] Client disconnected: ${socket.id}`);
    });
});

// ─── Start ────────────────────────────────────────────────────────────────────
const PORT = process.env.PORT || 3001;
server.listen(PORT, () => {
    console.log(`Fleet Tracker Backend listening on http://localhost:${PORT}`);
});
