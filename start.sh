#!/bin/bash
echo "Starting Estimation Tool..."

# Check if Docker is running
if ! docker info > /dev/null 2>&1; then
    echo "Docker is not running. Please start Docker first."
    exit 1
fi

# Start databases
echo "Starting databases..."
docker-compose up postgres redis -d

# Wait for databases
echo "Waiting for databases to be ready..."
sleep 15

# Start backend
echo "Starting backend..."
cd backend
source venv/bin/activate 2>/dev/null || (python -m venv venv && source venv/bin/activate)
pip install -r requirements.txt > /dev/null 2>&1
alembic upgrade head
uvicorn app.main:app --reload --port 8000 &
BACKEND_PID=$!
cd ..

# Start frontend
echo "Starting frontend..."
cd frontend
npm install > /dev/null 2>&1
npm run dev &
FRONTEND_PID=$!
cd ..

echo "Estimation Tool is starting up..."
echo "Frontend: http://localhost:3000"
echo "Backend API: http://localhost:8000"
echo "API Docs: http://localhost:8000/docs"
echo ""
echo "Press Ctrl+C to stop all services"

# Wait for Ctrl+C
trap 'kill $BACKEND_PID $FRONTEND_PID; docker-compose down; exit' INT
wait