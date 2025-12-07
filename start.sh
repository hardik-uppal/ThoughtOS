#!/bin/bash

# Kill running processes
echo "🧹 Cleaning up old processes..."
pkill -f "uvicorn"
pkill -f "vite"

# Start Backend
echo "🚀 Starting Backend (FastAPI)..."
uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000 > backend.log 2>&1 &
BACKEND_PID=$!
echo "   Backend running on PID $BACKEND_PID"

# Start Frontend
echo "🎨 Starting Frontend (React + Vite)..."
cd frontend
npm run dev -- --host > ../frontend.log 2>&1 &
FRONTEND_PID=$!
echo "   Frontend running on PID $FRONTEND_PID"

echo "✅ ContextOS is Online!"
echo "   Backend: http://localhost:8000"
echo "   Frontend: http://localhost:5173"
echo "   (Logs are being written to backend.log and frontend.log)"

# Wait for processes
wait $BACKEND_PID $FRONTEND_PID
