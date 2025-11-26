#!/bin/bash
set -e

echo "Starting Estimation Tool..."

# Require Docker for database services
if ! docker info > /dev/null 2>&1; then
  echo "Docker is not running. Start Docker Desktop and rerun this script (or launch manually without DBs)."
  exit 1
fi

echo "Starting databases..."
docker-compose up -d postgres redis

echo "Waiting for databases to be ready..."
sleep 15

echo "Starting backend..."
cd backend

if [ ! -d "venv_311" ]; then
  echo "   Creating virtual environment..."
  python3.11 -m venv venv_311 || python -m venv venv_311
fi

if [ -f "venv_311/Scripts/activate" ]; then
  source venv_311/Scripts/activate
  echo "   Virtual environment activated"
else
  echo "   Failed to find venv activation script"
  exit 1
fi

echo "   Installing/updating backend dependencies..."
python -m pip install --upgrade pip
pip install -q -r requirements.txt

if [ -f "alembic.ini" ] && command -v alembic &> /dev/null; then
  echo "   Running database migrations..."
  alembic upgrade head 2>/dev/null || echo "   Migrations skipped"
fi

uvicorn app.main:app --reload --port 8000 &
BACKEND_PID=$!
cd ..

echo "Starting frontend..."
cd frontend
npm install > /dev/null 2>&1
npm run dev &
FRONTEND_PID=$!
cd ..

echo "Estimation Tool is starting up..."
echo "Frontend:       http://localhost:3000"
echo "Backend API:    http://localhost:8000"
echo "API Docs:       http://localhost:8000/docs"
echo "PostgreSQL:     localhost:5432"
echo "Redis:          localhost:6379"
echo ""
echo "Press Ctrl+C to stop all services"

trap 'kill $BACKEND_PID $FRONTEND_PID; docker-compose down; exit' INT
wait
