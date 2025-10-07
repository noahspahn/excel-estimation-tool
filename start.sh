#!/bin/bash
set -e  # Exit on error

echo "🚀 Starting Estimation Tool..."

# Check if Docker is running
if ! docker info > /dev/null 2>&1; then
    echo "⚠️  Docker is not running."
    echo "Choose an option:"
    echo "  1) Start Docker Desktop and run this script again"
    echo "  2) Run without databases: ./start-no-docker.sh"
    exit 1
fi

# Check if Docker is running
if ! docker info > /dev/null 2>&1; then
    echo "Docker is not running. Please start Docker first."
    exit 1
fi

# Start databases
echo "Starting databases..."
docker-compose up -d postgres redis

# Wait for databases
echo "Waiting for databases to be ready..."
sleep 15

# Start backend
echo "Starting backend..."
cd backend

if [ ! -d "venv_311" ]; then
    echo "   Creating virtual environment..."
    python3.11 -m venv venv_311 || python -m venv venv_311
fi

if [ -f "venv_311/Scripts/activate" ]; then
    source venv_311/Scripts/activate
    echo "   ✅ Virtual environment activated"
else
    echo "   ❌ Failed to find venv activation script"
    exit 1
fi

echo "   📦 Installing/updating backend dependencies..."
python -m pip install -q --upgrade pip 2>/dev/null || echo "   ⚠️  Pip upgrade skipped"
pip install -q fastapi uvicorn python-dotenv sqlalchemy pydantic
pip install -q reportlab 2>/dev/null && echo "   ✅ ReportLab installed" || echo "   ⚠️  ReportLab not installed"

if [ -f "alembic.ini" ] && command -v alembic &> /dev/null; then
    echo "   Running database migrations..."
    alembic upgrade head 2>/dev/null || echo "   ⚠️  Migrations skipped"
fi

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
echo "🌐 Frontend:       http://localhost:3000"
echo "🔧 Backend API:    http://localhost:8000"
echo "📚 API Docs:       http://localhost:8000/docs"
echo "🐘 PostgreSQL:     localhost:5432"
echo "🔴 Redis:          localhost:6379"
echo ""
echo "Press Ctrl+C to stop all services"

# Wait for Ctrl+C
trap 'kill $BACKEND_PID $FRONTEND_PID; docker-compose down; exit' INT
wait