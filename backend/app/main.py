from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Dict
import uvicorn

# Import our services
from .services.calculation_service import CalculationService
from .services.data_service import DataService
from .models import ComplexityLevel

app = FastAPI(title="Estimation Tool API", version="2.0.0")

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://localhost:3001", 
        "http://127.0.0.1:3000",
        "http://127.0.0.1:3001"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize services
calculation_service = CalculationService()
data_service = DataService()

@app.get("/")
def read_root():
    return {"message": "Estimation Tool API v2.0 is running", "status": "ready"}

@app.get("/health")
def health_check():
    return {"status": "healthy", "version": "2.0.0"}

@app.get("/api/v1/modules")
def get_modules():
    """Get all available modules"""
    modules = data_service.get_all_modules()
    return [
        {
            "id": module.id,
            "name": module.name,
            "focus_area": module.focus_area.value,
            "base_hours_by_role": module.base_hours_by_role,
            "prerequisites": module.prerequisites
        }
        for module in modules.values()
    ]

@app.get("/api/v1/roles")
def get_roles():
    """Get all available roles"""
    roles = data_service.get_all_roles()
    return [
        {
            "id": role.id,
            "name": role.name,
            "base_hourly_rate": role.base_hourly_rate
        }
        for role in roles.values()
    ]

@app.post("/api/v1/calculate")
def calculate_simple(data: dict):
    """Legacy simple calculation endpoint"""
    base_hours = data.get("base_hours", 100)
    complexity = data.get("complexity", "M")
    
    try:
        complexity_level = ComplexityLevel(complexity)
    except ValueError:
        complexity_level = ComplexityLevel.MEDIUM
    
    # Simple multiplier calculation
    multipliers = {"S": 0.7, "M": 1.0, "L": 1.6, "XL": 2.3}
    multiplier = multipliers.get(complexity, 1.0)
    
    total_hours = base_hours * multiplier
    hourly_rate = 150
    total_cost = total_hours * hourly_rate
    
    return {
        "total_hours": round(total_hours, 2),
        "hourly_rate": hourly_rate,
        "total_cost": round(total_cost, 2),
        "complexity": complexity
    }

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)