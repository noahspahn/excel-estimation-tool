from fastapi import FastAPI, HTTPException, Depends, Header
from fastapi.responses import StreamingResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Dict, Optional, Any
from dataclasses import asdict
import uvicorn
import os
import json
import time
import urllib.request
from pathlib import Path
from dotenv import load_dotenv, find_dotenv
from jose import jwt, JWTError, jwk
from jose.utils import base64url_decode
from datetime import datetime, timedelta, timezone

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
from .services.web_scraper_service import WebScraperService, ScrapeRequest
from .models import ComplexityLevel, EstimationInput
from .db import engine, get_session
from .db_models import Base, Proposal, ProposalVersion

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
web_scraper_service = WebScraperService()
# Note: ExportService (and ReportLab) are imported lazily in the report endpoint

# Ensure DB tables exist (lightweight, safe on startup)
try:
    Base.metadata.create_all(bind=engine)
except Exception:
    # DB optional for stateless runs; endpoints using DB will error if unavailable
    pass

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
    # Optional scraped contract context to embed in the report
    contract_url: Optional[str] = None
    contract_excerpt: Optional[str] = None


class ScrapeUrlRequest(BaseModel):
    """Request body for a simple URL scrape preview."""

    url: str
    max_bytes: int = 200_000
    max_chars: int = 4_000
    timeout: float = 10.0


class ScrapeUrlResponse(BaseModel):
    """Lightweight view of scraped content for UI preview and later analysis."""

    url: str
    final_url: Optional[str] = None
    success: bool
    status_code: Optional[int] = None
    content_type: Optional[str] = None
    encoding: Optional[str] = None
    text_excerpt: str
    fetched_at: datetime
    truncated: bool = False
    error: Optional[str] = None


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
    if req.contract_url or req.contract_excerpt:
        estimation_data["contract_source"] = {
            "url": req.contract_url,
            "excerpt": req.contract_excerpt,
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

# -----------------------------
# -----------------------------
# Proposal persistence endpoints
# -----------------------------

def get_current_user(authorization: str | None = Header(default=None)) -> str:
    """
    Resolve the current user from an Authorization header if present.

    For now, API access does not require a token. If no valid bearer
    token is supplied, fall back to a default dev user identity so
    that endpoints can still operate without authentication.
    """
    default_user = os.getenv("DEV_DEFAULT_USER_EMAIL", "anonymous@example.com")

    # No auth required for now: if there is no bearer token, just return the
    # default dev user identity.
    if not authorization or not authorization.lower().startswith("bearer "):
        return default_user

    token = authorization.split(" ", 1)[1].strip()
    try:
        return _verify_cognito_token(token)
    except Exception:
        # For any verification error (network, config, invalid token, etc.),
        # fall back to the default user instead of failing the request.
        return default_user


@app.post("/api/v1/scrape/url", response_model=ScrapeUrlResponse)
def scrape_url(req: ScrapeUrlRequest, current_user: str = Depends(get_current_user)):
    """
    Scrape a single URL and return a cleaned text excerpt.

    This is a foundation endpoint intended for exploration and for
    feeding future contract-analysis/report-generation workflows.
    """
    job = ScrapeRequest(
        url=req.url,
        max_bytes=req.max_bytes,
        max_chars=req.max_chars,
        timeout=req.timeout,
    )
    result = web_scraper_service.scrape(job)

    return ScrapeUrlResponse(
        url=result.url,
        final_url=result.final_url,
        success=result.success,
        status_code=result.status_code,
        content_type=result.content_type,
        encoding=result.encoding,
        text_excerpt=result.text_excerpt,
        fetched_at=result.fetched_at,
        truncated=result.truncated,
        error=result.error,
    )


class ProposalCreate(BaseModel):
    title: Optional[str] = None
    payload: Dict[str, Any]


class ProposalResponse(BaseModel):
    id: str
    public_id: str
    title: Optional[str] = None
    created_at: Optional[str] = None


@app.post("/api/v1/proposals", response_model=ProposalResponse)
def create_proposal(req: ProposalCreate, current_user: str = Depends(get_current_user)):
    with get_session() as session:
        proposal = Proposal(title=req.title, payload=req.payload, owner_email=current_user)
        session.add(proposal)
        session.flush()
        # Create first version (v1)
        v = ProposalVersion(
            proposal_id=proposal.id,
            version=1,
            title=proposal.title,
            payload=req.payload,
        )
        session.add(v)
        return ProposalResponse(
            id=proposal.id,
            public_id=proposal.public_id,
            title=proposal.title,
            created_at=str(proposal.created_at) if proposal.created_at else None,
        )


@app.get("/api/v1/proposals/public/{public_id}")
def get_public_proposal(public_id: str):
    with get_session() as session:
        obj = session.query(Proposal).filter(Proposal.public_id == public_id).one_or_none()
        if not obj:
            raise HTTPException(status_code=404, detail="Not found")
        return {
            "id": obj.id,
            "public_id": obj.public_id,
            "title": obj.title,
            "payload": obj.payload,
            "created_at": str(obj.created_at) if obj.created_at else None,
        }


class VersionCreate(BaseModel):
    title: Optional[str] = None
    payload: Dict[str, Any]


@app.post("/api/v1/proposals/{proposal_id}/versions")
def create_version(proposal_id: str, body: VersionCreate, current_user: str = Depends(get_current_user)):
    with get_session() as session:
        prop = (
            session.query(Proposal)
            .filter(Proposal.id == proposal_id, Proposal.owner_email == current_user)
            .one_or_none()
        )
        if not prop:
            raise HTTPException(status_code=404, detail="Proposal not found")
        # next version number
        last = (
            session.query(ProposalVersion)
            .filter(ProposalVersion.proposal_id == proposal_id)
            .order_by(ProposalVersion.version.desc())
            .first()
        )
        next_ver = 1 + (last.version if last else 0)
        ver = ProposalVersion(
            proposal_id=proposal_id,
            version=next_ver,
            title=body.title or prop.title,
            payload=body.payload,
        )
        prop.payload = body.payload
        session.add(ver)
        session.flush()
        return {"proposal_id": proposal_id, "version": next_ver, "id": ver.id}


@app.get("/api/v1/proposals/{proposal_id}/versions")
def list_versions(proposal_id: str, current_user: str = Depends(get_current_user)):
    with get_session() as session:
        rows = (
            session.query(ProposalVersion)
            .join(Proposal, Proposal.id == ProposalVersion.proposal_id)
            .filter(ProposalVersion.proposal_id == proposal_id, Proposal.owner_email == current_user)
            .order_by(ProposalVersion.version.asc())
            .all()
        )
        return [
            {
                "id": r.id,
                "version": r.version,
                "title": r.title,
                "created_at": str(r.created_at) if r.created_at else None,
            }
            for r in rows
        ]


@app.get("/api/v1/proposals/{proposal_id}/versions/{version}")
def get_version(proposal_id: str, version: int, current_user: str = Depends(get_current_user)):
    with get_session() as session:
        ver = (
            session.query(ProposalVersion)
            .join(Proposal, Proposal.id == ProposalVersion.proposal_id)
            .filter(
                ProposalVersion.proposal_id == proposal_id,
                ProposalVersion.version == version,
                Proposal.owner_email == current_user,
            )
            .one_or_none()
        )
        if not ver:
            raise HTTPException(status_code=404, detail="Version not found")
        return {
            "id": ver.id,
            "version": ver.version,
            "title": ver.title,
            "payload": ver.payload,
            "created_at": str(ver.created_at) if ver.created_at else None,
        }


def _json_diff(a: Any, b: Any, path: str = "") -> List[Dict[str, Any]]:
    """Produce a simple JSON diff list with entries: {path, left, right, change}.
    change is one of 'added', 'removed', 'changed'."""
    diffs: List[Dict[str, Any]] = []
    if isinstance(a, dict) and isinstance(b, dict):
        keys = set(a.keys()) | set(b.keys())
        for k in sorted(keys):
            p = f"{path}.{k}" if path else str(k)
            if k not in a:
                diffs.append({"path": p, "left": None, "right": b[k], "change": "added"})
            elif k not in b:
                diffs.append({"path": p, "left": a[k], "right": None, "change": "removed"})
            else:
                diffs.extend(_json_diff(a[k], b[k], p))
    elif isinstance(a, list) and isinstance(b, list):
        # Compare by length and primitive element differences best-effort
        if a == b:
            return diffs
        diffs.append({"path": path, "left": a, "right": b, "change": "changed"})
    else:
        if a != b:
            diffs.append({"path": path, "left": a, "right": b, "change": "changed"})
    return diffs


@app.get("/api/v1/proposals/{proposal_id}/diff")
def diff_versions(proposal_id: str, from_version: int, to_version: int, current_user: str = Depends(get_current_user)):
    with get_session() as session:
        v1 = (
            session.query(ProposalVersion)
            .join(Proposal, Proposal.id == ProposalVersion.proposal_id)
            .filter(
                ProposalVersion.proposal_id == proposal_id,
                ProposalVersion.version == from_version,
                Proposal.owner_email == current_user,
            )
            .one_or_none()
        )
        v2 = (
            session.query(ProposalVersion)
            .join(Proposal, Proposal.id == ProposalVersion.proposal_id)
            .filter(
                ProposalVersion.proposal_id == proposal_id,
                ProposalVersion.version == to_version,
                Proposal.owner_email == current_user,
            )
            .one_or_none()
        )
        if not v1 or not v2:
            raise HTTPException(status_code=404, detail="One or both versions not found")
        diffs = _json_diff(v1.payload, v2.payload)
        return {"from": from_version, "to": to_version, "diffs": diffs}


# -----------------------------
# Simple auth (email magic link) + Cognito integration
# -----------------------------

JWT_SECRET = os.getenv("SECRET_KEY", "dev-secret-key-change-me")
JWT_ALG = "HS256"
AUTH_ALLOWED = os.getenv("ALLOWED_AUTH_DOMAINS", "*")

# Optional Cognito config (preferred in production)
COGNITO_REGION = os.getenv("COGNITO_REGION")
COGNITO_USER_POOL_ID = os.getenv("COGNITO_USER_POOL_ID")
COGNITO_CLIENT_ID = os.getenv("COGNITO_CLIENT_ID")

if COGNITO_REGION and COGNITO_USER_POOL_ID:
    COGNITO_ISS = f"https://cognito-idp.{COGNITO_REGION}.amazonaws.com/{COGNITO_USER_POOL_ID}"
    COGNITO_JWKS_URL = f"{COGNITO_ISS}/.well-known/jwks.json"
else:
    COGNITO_ISS = None
    COGNITO_JWKS_URL = None

_JWKS_CACHE: Dict[str, Any] = {}


def _get_cognito_jwks() -> List[Dict[str, Any]]:
    if not COGNITO_JWKS_URL:
        raise RuntimeError("Cognito not configured")
    now = time.time()
    cached = _JWKS_CACHE.get("data")
    if cached is not None and now - _JWKS_CACHE.get("ts", 0) < 3600:
        return cached  # type: ignore[return-value]
    with urllib.request.urlopen(COGNITO_JWKS_URL) as resp:
        data = json.load(resp)
    keys = data.get("keys", [])
    _JWKS_CACHE["data"] = keys
    _JWKS_CACHE["ts"] = now
    return keys


def _allowed_email(email: str) -> bool:
    if AUTH_ALLOWED.strip() == "*":
        return True
    domains = [d.strip().lower() for d in AUTH_ALLOWED.split(",") if d.strip()]
    try:
        domain = email.split("@", 1)[1].lower()
        return domain in domains
    except Exception:
        return False


def _issue_token(email: str, ttl_minutes: int, purpose: str) -> str:
    """Local HS256 token issuer (dev fallback)."""
    now = datetime.now(timezone.utc)
    payload = {
        "sub": email,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=ttl_minutes)).timestamp()),
        "purpose": purpose,
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALG)


def _verify_token(token: str, purpose: str) -> str:
    """Local HS256 token verifier (dev fallback)."""
    try:
        data = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALG])
        if data.get("purpose") != purpose:
            raise JWTError("Invalid purpose")
        return str(data.get("sub"))
    except JWTError as e:
        raise HTTPException(status_code=400, detail=f"Invalid token: {e}")


def _verify_cognito_token(raw: str) -> str:
    """Verify a Cognito JWT and return the email claim.

    If Cognito is not configured, fall back to local dev tokens.
    """
    if not (COGNITO_REGION and COGNITO_USER_POOL_ID and COGNITO_CLIENT_ID and COGNITO_ISS):
        # Dev / local mode: use legacy HS256 access tokens
        return _verify_token(raw, purpose="access")

    try:
        headers = jwt.get_unverified_header(raw)
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid token header")

    kid = headers.get("kid")
    if not kid:
        raise HTTPException(status_code=401, detail="Invalid token kid")

    keys = _get_cognito_jwks()
    key = next((k for k in keys if k.get("kid") == kid), None)
    if not key:
        raise HTTPException(status_code=401, detail="Unknown token key")

    public_key = jwk.construct(key, algorithm="RS256")
    try:
        message, encoded_sig = raw.rsplit(".", 1)
    except ValueError:
        raise HTTPException(status_code=401, detail="Invalid token format")

    decoded_sig = base64url_decode(encoded_sig.encode("utf-8"))
    if not public_key.verify(message.encode("utf-8"), decoded_sig):
        raise HTTPException(status_code=401, detail="Invalid token signature")

    claims = jwt.get_unverified_claims(raw)
    if claims.get("iss") != COGNITO_ISS:
        raise HTTPException(status_code=401, detail="Invalid token issuer")

    aud = claims.get("aud") or claims.get("client_id")
    if aud != COGNITO_CLIENT_ID:
        raise HTTPException(status_code=401, detail="Invalid token audience")

    if claims.get("exp", 0) < time.time():
        raise HTTPException(status_code=401, detail="Token expired")

    email = claims.get("email")
    if not email:
        raise HTTPException(status_code=401, detail="Token missing email claim")
    return str(email)


class AuthRequest(BaseModel):
    email: str


@app.post("/api/v1/auth/request_link")
def auth_request_link(req: AuthRequest):
    """Legacy dev-only magic link issuer (unused with Cognito)."""
    email = (req.email or "").strip()
    if not email or "@" not in email:
        raise HTTPException(status_code=400, detail="Invalid email")
    if not _allowed_email(email):
        raise HTTPException(status_code=403, detail="Email domain not allowed")
    token = _issue_token(email, ttl_minutes=15, purpose="magic")
    url = f"/auth?token={token}"
    return {"token": token, "magic_url": url, "expires_in": 900}


class TokenExchange(BaseModel):
    token: str


@app.post("/api/v1/auth/exchange")
def auth_exchange(body: TokenExchange):
    """Legacy dev-only token exchange (unused with Cognito)."""
    email = _verify_token(body.token, purpose="magic")
    access = _issue_token(email, ttl_minutes=60 * 24 * 7, purpose="access")
    return {"access_token": access, "token_type": "bearer", "email": email}


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
