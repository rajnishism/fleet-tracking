#!/bin/bash
# start.sh – Start the Fleet Tracker backend, frontend, and edge simulator
set -e

echo "🚀 Starting Fleet Tracker Backend..."
cd backend
node server.js &
BACKEND_PID=$!
echo "Backend PID: $BACKEND_PID"
cd ..

sleep 2

echo "🌐 Starting Fleet Tracker Frontend..."
cd frontend
npm run dev &
FRONTEND_PID=$!
echo "Frontend PID: $FRONTEND_PID"
cd ..

echo ""
echo "✅ System running:"
echo "   Backend  → http://localhost:3001"
echo "   Frontend → http://localhost:5173"
echo ""
echo "🛰️  To start edge simulator (in a new terminal):"
echo "   cd edge && python3 main.py --mode simulate"
echo ""
echo "Press Ctrl+C to stop all services."
wait
