#!/bin/bash

echo "🛑 Stopping ContextOS servers..."

# Kill backend (port 8000)
BACKEND_PID=$(lsof -ti:8000)
if [ ! -z "$BACKEND_PID" ]; then
    echo "   Killing backend on port 8000 (PID: $BACKEND_PID)"
    kill -9 $BACKEND_PID
fi

# Kill frontend (port 5173)
FRONTEND_PID=$(lsof -ti:5173)
if [ ! -z "$FRONTEND_PID" ]; then
    echo "   Killing frontend on port 5173 (PID: $FRONTEND_PID)"
    kill -9 $FRONTEND_PID
fi

# Small delay to ensure ports are free
sleep 1

echo "🚀 Starting ContextOS..."

# Start Backend
uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000 > backend.log 2>&1 &
BACKEND_PID=$!
echo "   Backend running (PID $BACKEND_PID) on http://localhost:8000"

# Start Frontend
cd frontend
npm run dev -- --host > ../frontend.log 2>&1 &
FRONTEND_PID=$!
cd ..
echo "   Frontend running (PID $FRONTEND_PID) on http://localhost:5173"

echo "✅ ContextOS is Online!"
echo ""
echo "   Backend:  http://localhost:8000/health"
echo "   Frontend: http://localhost:5173"
echo ""
echo "Logs: backend.log, frontend.log"
