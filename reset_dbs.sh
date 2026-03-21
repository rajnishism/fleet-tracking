#!/bin/bash
echo "Resetting both Fleet Tracking databases for a fresh demo..."

# 1. Reset Cloud Database (Backend)
echo "Deleting Backend Cloud Database..."
rm -f backend/prisma/fleet.db
rm -f backend/prisma/fleet.db-journal
cd backend
npx prisma db push
cd ..

# 2. Reset Edge Database (Local Storage)
echo "Deleting Edge Local Database..."
rm -f edge/database/vehicle_data.db
rm -f edge/database/vehicle_data.db-journal

echo "Database reset complete! You are ready for a fresh demo."
