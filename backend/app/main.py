from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="Estimation Tool API", version="1.0.0")

# Enable CORS for frontend - Updated to include port 3001
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://localhost:3001",  # Add this line
        "http://127.0.0.1:3000",
        "http://127.0.0.1:3001"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def read_root():
    return {"message": "Estimation Tool API is running"}

@app.get("/health")
def health_check():
    return {"status": "healthy"}

@app.get("/api/v1/modules")
def get_modules():
    # Mock data for now
    return {
        "modules": [
            {"id": 1, "name": "Discovery & Current State Mapping", "focus_area": "DT", "base_hours": 120},
            {"id": 2, "name": "Network Core Refresh", "focus_area": "ITM", "base_hours": 200},
            {"id": 3, "name": "License Audit & Rightsizing", "focus_area": "SA", "base_hours": 80}
        ]
    }

@app.post("/api/v1/calculate")
def calculate_estimate(data: dict):
    # Basic calculation for now
    base_hours = data.get("base_hours", 100)
    complexity_multiplier = {"S": 0.7, "M": 1.0, "L": 1.6, "XL": 2.3}.get(data.get("complexity", "M"), 1.0)
    
    total_hours = base_hours * complexity_multiplier
    hourly_rate = 150  # Mock rate
    total_cost = total_hours * hourly_rate
    
    return {
        "total_hours": total_hours,
        "hourly_rate": hourly_rate,
        "total_cost": total_cost,
        "complexity": data.get("complexity", "M")
    }