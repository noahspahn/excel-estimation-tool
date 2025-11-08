from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Dict, Optional, Any
from dataclasses import asdict
import uvicorn
import os
from pathlib import Path
from dotenv import load_dotenv, find_dotenv

# Load environment variables from a local .env if present
# 1) Try auto-discovery up the directory tree
load_dotenv(find_dotenv(), override=False)
# 2) Try repo root relative to this file (../../.env)
_root_env = Path(__file__).resolve().parents[2] / ".env"
if _root_env.exists():
    load_dotenv(_root_env.as_posix(), override=False)
# 3) Try backend-local .env (../.env)
_backend_env = Path(__file__).resolve().parents[1] / ".env"
if _backend_env.exists():
    load_dotenv(_backend_env.as_posix(), override=False)

# Import our services
from .services.calculation_service import CalculationService
from .services.data_service import DataService
from .models import ComplexityLevel, EstimationInput

app = FastAPI(title="Estimation Tool API", version="2.0.0")

# Enable CORS
_default_origins = "http://localhost:3000,http://localhost:3001,http://127.0.0.1:3000,http://127.0.0.1:3001"
_allowed = os.getenv("ALLOWED_ORIGINS", _default_origins)
_origins = [o.strip() for o in _allowed.split(",") if o.strip()] if _allowed != "*" else ["*"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize services
calculation_service = CalculationService()
data_service = DataService()
# Note: ExportService (and ReportLab) are imported lazily in the report endpoint

@app.get("/")
def read_root():
    return {"message": "Estimation Tool API v2.0 is running", "status": "ready"}

@app.get("/health")
def health_check():
    return {
        "status": "healthy",
        "version": "2.0.0",
        "ai_configured": bool(os.getenv("OPENAI_API_KEY")),
    }

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


class EstimationRequest(BaseModel):
    modules: List[str]
    complexity: str
    environment: str = "production"
    integration_level: str = "moderate_integration"
    geography: str = "dc_metro"
    clearance_level: str = "secret"
    is_prime_contractor: bool = True
    custom_role_overrides: Dict[str, float] = {}
    # Extended project info
    project_name: Optional[str] = None
    government_poc: Optional[str] = None
    account_manager: Optional[str] = None
    service_delivery_mgr: Optional[str] = None
    service_delivery_exec: Optional[str] = None
    site_location: Optional[str] = None
    email: Optional[str] = None
    fy: Optional[str] = None
    rap_number: Optional[str] = None
    psi_code: Optional[str] = None
    additional_comments: Optional[str] = None
    # Site and schedule
    sites: int = 1
    overtime: bool = False
    # Other costs
    odc_items: List[Dict[str, Any]] = []
    fixed_price_items: List[Dict[str, Any]] = []
    hardware_subtotal: float = 0.0
    warranty_months: int = 0
    warranty_cost: float = 0.0


class NarrativeRequest(EstimationRequest):
    sections: Optional[List[str]] = None
    tone: str = "professional"


class ReportRequest(EstimationRequest):
    """Report request body, allowing optional custom narrative sections."""
    narrative_sections: Optional[Dict[str, str]] = None


@app.post("/api/v1/estimate")
def estimate(req: EstimationRequest):
    """Full-feature estimate using the advanced calculation service"""
    try:
        complexity_level = ComplexityLevel(req.complexity)
    except ValueError:
        complexity_level = ComplexityLevel.MEDIUM

    est_input = EstimationInput(
        modules=req.modules,
        complexity=complexity_level,
        environment=req.environment,
        integration_level=req.integration_level,
        geography=req.geography,
        clearance_level=req.clearance_level,
        is_prime_contractor=req.is_prime_contractor,
        custom_role_overrides=req.custom_role_overrides or {},
        project_name=req.project_name,
        government_poc=req.government_poc,
        account_manager=req.account_manager,
        service_delivery_mgr=req.service_delivery_mgr,
        service_delivery_exec=req.service_delivery_exec,
        site_location=req.site_location,
        email=req.email,
        fy=req.fy,
        rap_number=req.rap_number,
        psi_code=req.psi_code,
        additional_comments=req.additional_comments,
        sites=req.sites,
        overtime=req.overtime,
        odc_items=req.odc_items or [],
        fixed_price_items=req.fixed_price_items or [],
        hardware_subtotal=req.hardware_subtotal or 0.0,
        warranty_months=req.warranty_months or 0,
        warranty_cost=req.warranty_cost or 0.0,
    )

    warnings = calculation_service.validate_estimate(est_input)
    result = calculation_service.calculate_estimate(est_input)

    payload = {
        "warnings": warnings,
        "estimation_result": asdict(result),
        "project_info": {
            "project_name": req.project_name,
            "government_poc": req.government_poc,
            "account_manager": req.account_manager,
            "service_delivery_mgr": req.service_delivery_mgr,
            "service_delivery_exec": req.service_delivery_exec,
            "site_location": req.site_location,
            "email": req.email,
            "fy": req.fy,
            "rap_number": req.rap_number,
            "psi_code": req.psi_code,
            "additional_comments": req.additional_comments,
        },
        "odc_items": req.odc_items or [],
        "fixed_price_items": req.fixed_price_items or [],
        "hardware_subtotal": req.hardware_subtotal or 0.0,
        "warranty_months": req.warranty_months or 0,
        "warranty_cost": req.warranty_cost or 0.0,
    }
    return JSONResponse(payload)


@app.post("/api/v1/narrative")
def generate_narrative(req: NarrativeRequest):
    # Lazy import to avoid hard dependency when not configured
    try:
        from .services.ai_service import AIService  # type: ignore
    except Exception:
        raise HTTPException(status_code=500, detail="AI module missing. Ensure ai_service.py exists.")

    try:
        complexity_level = ComplexityLevel(req.complexity)
    except ValueError:
        complexity_level = ComplexityLevel.MEDIUM

    est_input = EstimationInput(
        modules=req.modules,
        complexity=complexity_level,
        environment=req.environment,
        integration_level=req.integration_level,
        geography=req.geography,
        clearance_level=req.clearance_level,
        is_prime_contractor=req.is_prime_contractor,
        custom_role_overrides=req.custom_role_overrides or {},
        project_name=req.project_name,
        government_poc=req.government_poc,
        account_manager=req.account_manager,
        service_delivery_mgr=req.service_delivery_mgr,
        service_delivery_exec=req.service_delivery_exec,
        site_location=req.site_location,
        email=req.email,
        fy=req.fy,
        rap_number=req.rap_number,
        psi_code=req.psi_code,
        additional_comments=req.additional_comments,
        sites=req.sites,
        overtime=req.overtime,
        odc_items=req.odc_items or [],
        fixed_price_items=req.fixed_price_items or [],
        hardware_subtotal=req.hardware_subtotal or 0.0,
        warranty_months=req.warranty_months or 0,
        warranty_cost=req.warranty_cost or 0.0,
    )

    result = calculation_service.calculate_estimate(est_input)
    estimation_data = {"estimation_result": asdict(result)}
    input_summary = {"complexity": req.complexity, "module_count": len(req.modules)}

    ai = AIService()
    if not ai.is_configured():
        raise HTTPException(status_code=400, detail="OPENAI_API_KEY not configured on backend.")

    try:
        narrative = ai.generate_narrative(
            estimation_data=estimation_data,
            input_summary=input_summary,
            sections=req.sections,
            tone=req.tone,
        )
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e))

    return JSONResponse({"narrative": narrative})


@app.post("/api/v1/report")
def generate_report(req: ReportRequest, include_ai: bool = False, tone: str = "professional"):
    """Generate and return a PDF estimation report as a download"""
    # Lazy import so the API can run without reportlab installed
    try:
        from .services.export_service import ExportService  # type: ignore
    except Exception as e:
        raise HTTPException(status_code=500, detail="Report generation dependency missing. Install 'reportlab'.")
    try:
        complexity_level = ComplexityLevel(req.complexity)
    except ValueError:
        complexity_level = ComplexityLevel.MEDIUM

    est_input = EstimationInput(
        modules=req.modules,
        complexity=complexity_level,
        environment=req.environment,
        integration_level=req.integration_level,
        geography=req.geography,
        clearance_level=req.clearance_level,
        is_prime_contractor=req.is_prime_contractor,
        custom_role_overrides=req.custom_role_overrides or {},
        project_name=req.project_name,
        government_poc=req.government_poc,
        account_manager=req.account_manager,
        service_delivery_mgr=req.service_delivery_mgr,
        service_delivery_exec=req.service_delivery_exec,
        site_location=req.site_location,
        email=req.email,
        fy=req.fy,
        rap_number=req.rap_number,
        psi_code=req.psi_code,
        additional_comments=req.additional_comments,
        sites=req.sites,
        overtime=req.overtime,
        odc_items=req.odc_items or [],
        fixed_price_items=req.fixed_price_items or [],
        hardware_subtotal=req.hardware_subtotal or 0.0,
        warranty_months=req.warranty_months or 0,
        warranty_cost=req.warranty_cost or 0.0,
    )

    result = calculation_service.calculate_estimate(est_input)

    estimation_data = {
        "estimation_result": asdict(result),
        "project_info": {
            "project_name": req.project_name,
            "government_poc": req.government_poc,
            "account_manager": req.account_manager,
            "service_delivery_mgr": req.service_delivery_mgr,
            "service_delivery_exec": req.service_delivery_exec,
            "site_location": req.site_location,
            "email": req.email,
            "fy": req.fy,
            "rap_number": req.rap_number,
            "psi_code": req.psi_code,
            "additional_comments": req.additional_comments,
        },
        "odc_items": req.odc_items or [],
        "fixed_price_items": req.fixed_price_items or [],
        "hardware_subtotal": req.hardware_subtotal or 0.0,
        "warranty_months": req.warranty_months or 0,
        "warranty_cost": req.warranty_cost or 0.0,
    }
    input_summary = {
        "complexity": req.complexity,
        "module_count": len(req.modules),
    }

    export_service = ExportService()

    # Prefer client-provided narrative sections if present.
    narrative_sections = req.narrative_sections or None
    if narrative_sections is None and include_ai:
        try:
            from .services.ai_service import AIService  # type: ignore

            ai = AIService()
            if ai.is_configured():
                narrative_sections = ai.generate_narrative(
                    estimation_data=estimation_data,
                    input_summary=input_summary,
                    tone=tone,
                )
        except Exception:
            # If AI generation fails or is not configured, continue without AI text
            narrative_sections = None

    pdf_bytes = export_service.generate_estimation_pdf(
        estimation_data,
        input_summary,
        narrative_sections=narrative_sections,
    )

    from datetime import datetime
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"estimation_report_{ts}.pdf"

    return StreamingResponse(
        iter([pdf_bytes]),
        media_type="application/pdf",
        headers={
            "Content-Disposition": f"attachment; filename=\"{filename}\""
        },
    )

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
