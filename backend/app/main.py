from fastapi import FastAPI, HTTPException, Depends, Header, UploadFile, File
from fastapi.responses import StreamingResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Dict, Optional, Any
from dataclasses import asdict
import uvicorn
import os
import json
import time
import threading
import urllib.request
from collections import Counter
from pathlib import Path
from dotenv import load_dotenv, find_dotenv
from jose import jwt, JWTError, jwk
from jose.utils import base64url_decode
from datetime import datetime, timedelta, timezone
from sqlalchemy import or_, func

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

PROMPTS_DIR = Path(os.getenv("PROMPTS_DIR", Path(__file__).resolve().parent / "prompts"))

# Import our services
from .services.calculation_service import CalculationService
from .services.data_service import DataService
from .services.web_scraper_service import WebScraperService, ScrapeRequest
from .services.storage_service import StorageService
from .models import ComplexityLevel, EstimationInput
from .db import engine, get_session
from .db_models import Base, Proposal, ProposalVersion, ProposalDocument, ContractOpportunity, ContractSyncState
from .services.sam_contract_service import (
    fetch_sam_opportunities,
    extract_sam_results,
    normalize_sam_record,
)

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
storage_service = StorageService()
# Note: ExportService (and ReportLab) are imported lazily in the report endpoint

CONTRACT_STATUSES = {"new", "in_progress", "submitted", "awarded", "lost"}

SAM_API_KEY = os.getenv("SAM_API_KEY")
SAM_SYNC_SOURCE = "sam.gov"
SAM_SYNC_SCHEDULED = os.getenv("SAM_SYNC_SCHEDULED", "true").lower() in ("1", "true", "yes")
SAM_SYNC_INTERVAL_MINUTES = int(os.getenv("SAM_SYNC_INTERVAL_MINUTES", "1440"))
SAM_SYNC_MIN_INTERVAL_MINUTES = int(os.getenv("SAM_SYNC_MIN_INTERVAL_MINUTES", "1440"))
SAM_SYNC_MAX_REQUESTS_PER_DAY = int(os.getenv("SAM_SYNC_MAX_REQUESTS_PER_DAY", "10"))
SAM_SYNC_DAYS_BACK = int(os.getenv("SAM_SYNC_DAYS_BACK", "7"))
SAM_SYNC_QUERY = os.getenv("SAM_SYNC_QUERY", "")
SAM_SYNC_LIMIT = int(os.getenv("SAM_SYNC_LIMIT", "1000"))
SAM_SYNC_PAGES = int(os.getenv("SAM_SYNC_PAGES", "1"))
SAM_SYNC_STATE: Dict[str, Any] = {"last_run": None, "last_error": None, "last_result": None}
SAM_SYNC_LOCK = threading.Lock()
SAM_SYNC_STARTED = False

# -----------------------------
# Simple auth / identity helper (must be defined before endpoints use it)
# -----------------------------
AUTH_REQUIRED = os.getenv("AUTH_REQUIRED", "true").lower() in ("1", "true", "yes")


def get_current_user(authorization: str | None = Header(default=None)) -> str:
    """
    Resolve the current user from an Authorization header if present.

    If AUTH_REQUIRED is enabled, a valid bearer token is mandatory.
    Otherwise, fall back to a default dev user identity when no token
    (or an invalid token) is supplied.
    """
    default_user = os.getenv("DEV_DEFAULT_USER_EMAIL", "anonymous@example.com")

    if not authorization or not authorization.lower().startswith("bearer "):
        if AUTH_REQUIRED:
            raise HTTPException(status_code=401, detail="Authorization required")
        return default_user

    token = authorization.split(" ", 1)[1].strip()
    try:
        return _verify_cognito_token(token)
    except Exception:
        if AUTH_REQUIRED:
            raise HTTPException(status_code=401, detail="Invalid or expired token")
        return default_user


def _get_owned_proposal(session, proposal_id: str, owner_email: str) -> Optional[Proposal]:
    return (
        session.query(Proposal)
        .filter(Proposal.id == proposal_id, Proposal.owner_email == owner_email)
        .one_or_none()
    )

# Ensure DB tables exist (lightweight, safe on startup)
try:
    Base.metadata.create_all(bind=engine)
except Exception:
    # DB optional for stateless runs; endpoints using DB will error if unavailable
    pass

@app.get("/")
def read_root():
    return {"message": "Estimation Tool API v2.0 is running", "status": "ready"}

def _health_payload():
    return {
        "status": "healthy",
        "version": "2.0.0",
        "ai_configured": bool(os.getenv("OPENAI_API_KEY")),
    }


@app.get("/health")
def health_check():
    return _health_payload()


@app.get("/api/health")
def api_health_check():
    return _health_payload()

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
    security_protocols: Optional[str] = None
    compliance_frameworks: Optional[str] = None
    additional_assumptions: Optional[str] = None
    # Site and schedule
    sites: int = 1
    overtime: bool = False
    tool_version: Optional[str] = None
    period_of_performance: Optional[str] = None
    estimating_method: Optional[str] = "engineering"
    historical_estimates: Optional[List[Dict[str, Any]]] = None
    raci_matrix: Optional[List[Dict[str, str]]] = None
    roadmap_phases: Optional[List[Dict[str, str]]] = None
    roi_capex_event_cost_low: Optional[float] = None
    roi_capex_event_cost_high: Optional[float] = None
    roi_capex_event_interval_months: Optional[float] = None
    roi_downtime_cost_per_hour: Optional[float] = None
    roi_current_availability: Optional[float] = None
    roi_target_availability: Optional[float] = None
    roi_legacy_support_savings_annual: Optional[float] = None
    # Other costs
    odc_items: List[Dict[str, Any]] = []
    fixed_price_items: List[Dict[str, Any]] = []
    hardware_subtotal: float = 0.0
    warranty_months: int = 0
    warranty_cost: float = 0.0


class NarrativeRequest(EstimationRequest):
    sections: Optional[List[str]] = None
    tone: str = "professional"
    # Optional scraped contract context for narrative generation
    contract_url: Optional[str] = None
    contract_excerpt: Optional[str] = None
    # Optional style guide for AI narrative
    style_guide: Optional[str] = None


class NarrativeSectionPrompt(BaseModel):
    """Request to rewrite or create a single narrative section with a custom prompt."""
    section: str
    estimation_data: Dict[str, Any]
    input_summary: Optional[Dict[str, Any]] = None
    prompt: Optional[str] = None
    current_text: Optional[str] = None
    tone: str = "professional"
    model: str = "gpt-4o-mini"
    style_guide: Optional[str] = None


class ReportRequest(EstimationRequest):
    """Report request body, allowing optional custom narrative sections."""
    narrative_sections: Optional[Dict[str, str]] = None
    # Optional style guide for AI narrative
    style_guide: Optional[str] = None
    # Optional scraped contract context to embed in the report
    contract_url: Optional[str] = None
    contract_excerpt: Optional[str] = None
    # Optional persistence hooks
    proposal_id: Optional[str] = None
    proposal_version: Optional[int] = None
    # AI subtasks toggle
    use_ai_subtasks: bool = True


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


class AssumptionsPromptRequest(BaseModel):
    scraped_text: str
    project_name: Optional[str] = None
    site_location: Optional[str] = None
    government_poc: Optional[str] = None
    fy: Optional[str] = None
    selected_modules: Optional[List[str]] = None


def _build_scrape_prompt_context(req: AssumptionsPromptRequest, scraped_text: str) -> Dict[str, str]:
    modules = req.selected_modules or []
    return {
        "PROJECT_NAME": req.project_name or "",
        "SITE_LOCATION": req.site_location or "",
        "GOV_POC": req.government_poc or "",
        "FY": req.fy or "",
        "SELECTED_MODULES": ", ".join(modules),
        "SCRAPED_TEXT": scraped_text,
    }


def _safe_float(value: Any) -> Optional[float]:
    try:
        if value is None or value == "":
            return None
        return float(value)
    except Exception:
        return None


def _compute_roi_summary(
    roi_inputs: Dict[str, Any],
    horizon_years: int,
    total_cost: float,
) -> Optional[Dict[str, Any]]:
    capex_low = _safe_float(roi_inputs.get("capex_event_cost_low"))
    capex_high = _safe_float(roi_inputs.get("capex_event_cost_high"))
    interval_months = _safe_float(roi_inputs.get("capex_event_interval_months"))
    downtime_cost = _safe_float(roi_inputs.get("downtime_cost_per_hour"))
    current_avail = _safe_float(roi_inputs.get("current_availability"))
    target_avail = _safe_float(roi_inputs.get("target_availability"))
    legacy_annual = _safe_float(roi_inputs.get("legacy_support_savings_annual"))

    has_inputs = any(
        v is not None
        for v in [capex_low, capex_high, interval_months, downtime_cost, current_avail, target_avail, legacy_annual]
    )
    if not has_inputs:
        return None

    capex_events = None
    if interval_months and interval_months > 0:
        capex_events = (horizon_years * 12) / interval_months

    capex_savings_low = capex_low * capex_events if capex_low is not None and capex_events else None
    capex_savings_high = capex_high * capex_events if capex_high is not None and capex_events else None
    if capex_savings_low is None and capex_savings_high is None and capex_events and capex_low is not None:
        capex_savings_low = capex_low * capex_events

    downtime_savings = None
    if downtime_cost is not None and current_avail is not None and target_avail is not None:
        hours_per_year = 24 * 365
        current_down = hours_per_year * max(0.0, 1 - (current_avail / 100))
        target_down = hours_per_year * max(0.0, 1 - (target_avail / 100))
        delta = max(0.0, current_down - target_down)
        downtime_savings = delta * downtime_cost * horizon_years

    legacy_savings = legacy_annual * horizon_years if legacy_annual is not None else None

    total_savings_low = 0.0
    total_savings_high = 0.0
    has_range = capex_savings_low is not None and capex_savings_high is not None

    for val in [capex_savings_low, downtime_savings, legacy_savings]:
        if val is not None:
            total_savings_low += val
    for val in [capex_savings_high or capex_savings_low, downtime_savings, legacy_savings]:
        if val is not None:
            total_savings_high += val

    net_benefit_low = total_savings_low - total_cost
    net_benefit_high = total_savings_high - total_cost

    return {
        "horizon_years": horizon_years,
        "capex_events": capex_events,
        "capex_savings_low": capex_savings_low,
        "capex_savings_high": capex_savings_high if has_range else None,
        "downtime_savings": downtime_savings,
        "legacy_savings": legacy_savings,
        "total_savings_low": total_savings_low,
        "total_savings_high": total_savings_high if has_range else None,
        "net_benefit_low": net_benefit_low,
        "net_benefit_high": net_benefit_high if has_range else None,
        "current_availability": current_avail,
        "target_availability": target_avail,
        "downtime_cost_per_hour": downtime_cost,
        "capex_interval_months": interval_months,
    }


def _extract_roi_inputs_from_estimation_input(estimation_input: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "capex_event_cost_low": estimation_input.get("roi_capex_event_cost_low"),
        "capex_event_cost_high": estimation_input.get("roi_capex_event_cost_high"),
        "capex_event_interval_months": estimation_input.get("roi_capex_event_interval_months"),
        "downtime_cost_per_hour": estimation_input.get("roi_downtime_cost_per_hour"),
        "current_availability": estimation_input.get("roi_current_availability"),
        "target_availability": estimation_input.get("roi_target_availability"),
        "legacy_support_savings_annual": estimation_input.get("roi_legacy_support_savings_annual"),
    }


class ContractCreate(BaseModel):
    source: Optional[str] = "manual"
    source_id: Optional[str] = None
    title: Optional[str] = None
    agency: Optional[str] = None
    sub_agency: Optional[str] = None
    office: Optional[str] = None
    naics: Optional[str] = None
    psc: Optional[str] = None
    set_aside: Optional[str] = None
    posted_at: Optional[datetime] = None
    due_at: Optional[datetime] = None
    value: Optional[str] = None
    location: Optional[str] = None
    url: Optional[str] = None
    synopsis: Optional[str] = None
    contract_excerpt: Optional[str] = None
    status: Optional[str] = "new"
    proposal_id: Optional[str] = None
    report_submitted_at: Optional[datetime] = None
    decision_date: Optional[datetime] = None
    awardee_name: Optional[str] = None
    award_value: Optional[float] = None
    award_notes: Optional[str] = None
    win_factors: Optional[str] = None
    loss_factors: Optional[str] = None
    analysis_notes: Optional[str] = None
    tags: Optional[List[str]] = None


class ContractUpdate(BaseModel):
    source: Optional[str] = None
    source_id: Optional[str] = None
    title: Optional[str] = None
    agency: Optional[str] = None
    sub_agency: Optional[str] = None
    office: Optional[str] = None
    naics: Optional[str] = None
    psc: Optional[str] = None
    set_aside: Optional[str] = None
    posted_at: Optional[datetime] = None
    due_at: Optional[datetime] = None
    value: Optional[str] = None
    location: Optional[str] = None
    url: Optional[str] = None
    synopsis: Optional[str] = None
    contract_excerpt: Optional[str] = None
    status: Optional[str] = None
    proposal_id: Optional[str] = None
    report_submitted_at: Optional[datetime] = None
    decision_date: Optional[datetime] = None
    awardee_name: Optional[str] = None
    award_value: Optional[float] = None
    award_notes: Optional[str] = None
    win_factors: Optional[str] = None
    loss_factors: Optional[str] = None
    analysis_notes: Optional[str] = None
    tags: Optional[List[str]] = None


def _normalize_contract_status(raw: Optional[str]) -> Optional[str]:
    if raw is None:
        return None
    val = raw.strip().lower().replace("-", "_").replace(" ", "_")
    if val == "pending":
        val = "submitted"
    if val not in CONTRACT_STATUSES:
        raise HTTPException(status_code=400, detail=f"Invalid status '{raw}'")
    return val


def _dt_to_str(value: Optional[datetime]) -> Optional[str]:
    if not value:
        return None
    if value.tzinfo:
        value = value.astimezone(timezone.utc).replace(tzinfo=None)
    return value.isoformat()


def _contract_to_dict(contract: ContractOpportunity, include_raw: bool = False) -> Dict[str, Any]:
    data = {
        "id": contract.id,
        "source": contract.source,
        "source_id": contract.source_id,
        "title": contract.title,
        "agency": contract.agency,
        "sub_agency": contract.sub_agency,
        "office": contract.office,
        "naics": contract.naics,
        "psc": contract.psc,
        "set_aside": contract.set_aside,
        "posted_at": _dt_to_str(contract.posted_at),
        "due_at": _dt_to_str(contract.due_at),
        "value": contract.value,
        "location": contract.location,
        "url": contract.url,
        "synopsis": contract.synopsis,
        "contract_excerpt": contract.contract_excerpt,
        "status": contract.status,
        "proposal_id": contract.proposal_id,
        "report_submitted_at": _dt_to_str(contract.report_submitted_at),
        "decision_date": _dt_to_str(contract.decision_date),
        "awardee_name": contract.awardee_name,
        "award_value": contract.award_value,
        "award_notes": contract.award_notes,
        "win_factors": contract.win_factors,
        "loss_factors": contract.loss_factors,
        "analysis_notes": contract.analysis_notes,
        "tags": contract.tags or [],
        "last_seen_at": _dt_to_str(contract.last_seen_at),
        "created_at": _dt_to_str(contract.created_at),
        "updated_at": _dt_to_str(contract.updated_at),
    }
    if include_raw:
        data["raw_payload"] = contract.raw_payload
    return data


def _get_sync_state(session) -> ContractSyncState:
    state = (
        session.query(ContractSyncState)
        .filter(ContractSyncState.source == SAM_SYNC_SOURCE)
        .one_or_none()
    )
    if not state:
        state = ContractSyncState(source=SAM_SYNC_SOURCE, requests_today=0)
        session.add(state)
        session.flush()
    return state


def _reset_daily_budget(state: ContractSyncState, now: datetime) -> None:
    today = now.strftime("%Y-%m-%d")
    if state.requests_today_date != today:
        state.requests_today_date = today
        state.requests_today = 0


def _update_contract_from_source(contract: ContractOpportunity, payload: Dict[str, Any], now: datetime) -> None:
    for field in [
        "title",
        "agency",
        "sub_agency",
        "office",
        "naics",
        "psc",
        "set_aside",
        "posted_at",
        "due_at",
        "value",
        "location",
        "url",
        "synopsis",
        "contract_excerpt",
    ]:
        val = payload.get(field)
        if val is None:
            continue
        if isinstance(val, str) and not val.strip():
            continue
        setattr(contract, field, val)
    contract.raw_payload = payload.get("raw_payload") or contract.raw_payload
    contract.last_seen_at = now
    contract.updated_at = now


def _sync_sam_contracts(trigger: str = "manual") -> Dict[str, Any]:
    if not SAM_API_KEY:
        result = {"status": "skipped", "reason": "missing_api_key"}
        SAM_SYNC_STATE.update({"last_run": _dt_to_str(datetime.utcnow()), "last_error": "missing_api_key", "last_result": result})
        return result
    if SAM_SYNC_MAX_REQUESTS_PER_DAY <= 0:
        result = {"status": "skipped", "reason": "daily_limit_disabled"}
        SAM_SYNC_STATE.update({"last_run": _dt_to_str(datetime.utcnow()), "last_error": "daily_limit_disabled", "last_result": result})
        return result
    if not SAM_SYNC_LOCK.acquire(blocking=False):
        return {"status": "busy"}
    now = datetime.utcnow()
    try:
        inserted = 0
        updated = 0
        seen: set[str] = set()
        request_count = 0
        with get_session() as session:
            state = _get_sync_state(session)
            _reset_daily_budget(state, now)

            if trigger == "scheduled" and state.last_run_at:
                delta = (now - state.last_run_at).total_seconds()
                if delta < max(0, SAM_SYNC_MIN_INTERVAL_MINUTES) * 60:
                    result = {
                        "status": "skipped",
                        "reason": "min_interval",
                        "seconds_since_last_run": round(delta, 1),
                    }
                    state.last_status = result["status"]
                    state.last_error = result["reason"]
                    state.last_result = result
                    state.updated_at = now
                    SAM_SYNC_STATE.update({"last_run": _dt_to_str(state.last_run_at), "last_error": result["reason"], "last_result": result})
                    return result

            remaining = max(0, SAM_SYNC_MAX_REQUESTS_PER_DAY - (state.requests_today or 0))
            if remaining <= 0:
                result = {"status": "skipped", "reason": "daily_limit_reached", "remaining": 0}
                state.last_status = result["status"]
                state.last_error = result["reason"]
                state.last_result = result
                state.last_run_at = now
                state.updated_at = now
                SAM_SYNC_STATE.update({"last_run": _dt_to_str(now), "last_error": result["reason"], "last_result": result})
                return result

            days_back = SAM_SYNC_DAYS_BACK
            if state.last_run_at:
                delta_days = max(1, int((now - state.last_run_at).total_seconds() // 86400) + 1)
                days_back = min(SAM_SYNC_DAYS_BACK, delta_days)

            pages = max(1, SAM_SYNC_PAGES)
            pages = min(pages, remaining)
            for page in range(pages):
                request_count += 1
                state.requests_today = (state.requests_today or 0) + 1
                try:
                    payload = fetch_sam_opportunities(
                        api_key=SAM_API_KEY,
                        query=SAM_SYNC_QUERY or None,
                        days_back=days_back,
                        limit=SAM_SYNC_LIMIT,
                        offset=page * SAM_SYNC_LIMIT,
                    )
                except Exception as exc:
                    err = str(exc)
                    result = {
                        "status": "error",
                        "error": err,
                        "request_count": request_count,
                        "remaining_quota": max(0, SAM_SYNC_MAX_REQUESTS_PER_DAY - (state.requests_today or 0)),
                        "trigger": trigger,
                    }
                    state.last_run_at = now
                    state.last_status = "error"
                    state.last_error = err
                    state.last_result = result
                    state.updated_at = now
                    SAM_SYNC_STATE.update({"last_run": _dt_to_str(now), "last_error": err, "last_result": result})
                    return result
                rows = extract_sam_results(payload)
                for row in rows:
                    normalized = normalize_sam_record(row or {})
                    source_id = normalized.get("source_id")
                    if not source_id or source_id in seen:
                        continue
                    seen.add(source_id)
                    existing = (
                        session.query(ContractOpportunity)
                        .filter(
                            ContractOpportunity.source == normalized.get("source", "sam.gov"),
                            ContractOpportunity.source_id == source_id,
                        )
                        .one_or_none()
                    )
                    if existing:
                        _update_contract_from_source(existing, normalized, now)
                        updated += 1
                    else:
                        contract = ContractOpportunity(**normalized)
                        contract.status = "new"
                        contract.last_seen_at = now
                        contract.updated_at = now
                        session.add(contract)
                        inserted += 1
            result = {
                "status": "ok",
                "inserted": inserted,
                "updated": updated,
                "total_seen": len(seen),
                "request_count": request_count,
                "days_back": days_back,
                "remaining_quota": max(0, SAM_SYNC_MAX_REQUESTS_PER_DAY - (state.requests_today or 0)),
                "trigger": trigger,
            }
            state.last_run_at = now
            state.last_status = result["status"]
            state.last_error = None
            state.last_result = result
            state.updated_at = now
        SAM_SYNC_STATE.update({"last_run": _dt_to_str(now), "last_error": None, "last_result": result})
        return result
    except Exception as exc:
        err = str(exc)
        try:
            with get_session() as session:
                state = _get_sync_state(session)
                state.last_run_at = now
                state.last_status = "error"
                state.last_error = err
                state.last_result = None
                state.updated_at = now
        except Exception:
            pass
        SAM_SYNC_STATE.update({"last_run": _dt_to_str(now), "last_error": err, "last_result": None})
        return {"status": "error", "error": err}
    finally:
        SAM_SYNC_LOCK.release()


def _sam_sync_loop() -> None:
    while True:
        _sync_sam_contracts(trigger="scheduled")
        time.sleep(max(60, SAM_SYNC_INTERVAL_MINUTES * 60))


def _start_sam_sync() -> None:
    global SAM_SYNC_STARTED
    if SAM_SYNC_STARTED or not SAM_SYNC_SCHEDULED:
        return
    if not SAM_API_KEY:
        return
    if SAM_SYNC_MAX_REQUESTS_PER_DAY <= 0:
        return
    thread = threading.Thread(target=_sam_sync_loop, daemon=True)
    thread.start()
    SAM_SYNC_STARTED = True


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
        security_protocols=req.security_protocols,
        compliance_frameworks=req.compliance_frameworks,
        additional_assumptions=req.additional_assumptions,
        sites=req.sites,
        overtime=req.overtime,
        period_of_performance=req.period_of_performance,
        estimating_method=req.estimating_method or "engineering",
        historical_estimates=req.historical_estimates or [],
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
            "security_protocols": req.security_protocols,
            "compliance_frameworks": req.compliance_frameworks,
            "additional_assumptions": req.additional_assumptions,
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
        security_protocols=req.security_protocols,
        compliance_frameworks=req.compliance_frameworks,
        additional_assumptions=req.additional_assumptions,
        sites=req.sites,
        overtime=req.overtime,
        period_of_performance=req.period_of_performance,
        estimating_method=req.estimating_method or "engineering",
        historical_estimates=req.historical_estimates or [],
        odc_items=req.odc_items or [],
        fixed_price_items=req.fixed_price_items or [],
        hardware_subtotal=req.hardware_subtotal or 0.0,
        warranty_months=req.warranty_months or 0,
        warranty_cost=req.warranty_cost or 0.0,
    )

    result = calculation_service.calculate_estimate(est_input)
    estimation_data = {"estimation_result": asdict(result)}
    project_info = {
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
        "security_protocols": req.security_protocols,
        "compliance_frameworks": req.compliance_frameworks,
        "additional_assumptions": req.additional_assumptions,
    }
    if any(v for v in project_info.values()):
        estimation_data["project_info"] = project_info
    if req.odc_items:
        estimation_data["odc_items"] = req.odc_items
    if req.fixed_price_items:
        estimation_data["fixed_price_items"] = req.fixed_price_items
    if req.hardware_subtotal:
        estimation_data["hardware_subtotal"] = req.hardware_subtotal
    if req.warranty_months:
        estimation_data["warranty_months"] = req.warranty_months
    if req.warranty_cost:
        estimation_data["warranty_cost"] = req.warranty_cost
    roi_inputs = {
        "capex_event_cost_low": req.roi_capex_event_cost_low,
        "capex_event_cost_high": req.roi_capex_event_cost_high,
        "capex_event_interval_months": req.roi_capex_event_interval_months,
        "downtime_cost_per_hour": req.roi_downtime_cost_per_hour,
        "current_availability": req.roi_current_availability,
        "target_availability": req.roi_target_availability,
        "legacy_support_savings_annual": req.roi_legacy_support_savings_annual,
    }
    if any(v is not None for v in roi_inputs.values()):
        estimation_data["roi_inputs"] = roi_inputs
        estimation_data["roi_horizon_years"] = 5
        roi_summary = _compute_roi_summary(roi_inputs, 5, float(result.total_cost or 0))
        if roi_summary:
            estimation_data["roi_summary"] = roi_summary
    if req.contract_url or req.contract_excerpt:
        estimation_data["contract_source"] = {
            "url": req.contract_url,
            "excerpt": req.contract_excerpt,
        }
    if req.style_guide:
        estimation_data["style_guide"] = req.style_guide
    # Add deterministic scope details for richer narrative context
    try:
        module_subtasks = calculation_service.build_module_subtasks(
            est_input,
            contract_excerpt=req.contract_excerpt,
        )
        estimation_data["module_subtasks"] = module_subtasks
    except Exception:
        # Narrative can still be generated without subtasks
        pass
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


@app.post("/api/v1/narrative/section")
def rewrite_narrative_section(req: NarrativeSectionPrompt):
    """Regenerate a single narrative section using a user-provided prompt."""
    # Lazy import to avoid hard dependency when not configured
    try:
        from .services.ai_service import AIService  # type: ignore
    except Exception:
        raise HTTPException(status_code=500, detail="AI module missing. Ensure ai_service.py exists.")

    ai = AIService()
    if not ai.is_configured():
        raise HTTPException(status_code=400, detail="OPENAI_API_KEY not configured on backend.")

    estimation_data = req.estimation_data or {}
    if req.style_guide and not estimation_data.get("style_guide"):
        estimation_data["style_guide"] = req.style_guide

    roi_inputs = estimation_data.get("roi_inputs")
    if not roi_inputs:
        roi_inputs = _extract_roi_inputs_from_estimation_input(estimation_data.get("estimation_input", {}) or {})
    if roi_inputs and any(v is not None for v in roi_inputs.values()):
        estimation_data["roi_inputs"] = roi_inputs
        if not estimation_data.get("roi_horizon_years"):
            estimation_data["roi_horizon_years"] = 5
        if not estimation_data.get("roi_summary"):
            total_cost = (estimation_data.get("estimation_result") or {}).get("total_cost") or 0
            roi_summary = _compute_roi_summary(roi_inputs, int(estimation_data.get("roi_horizon_years") or 5), float(total_cost))
            if roi_summary:
                estimation_data["roi_summary"] = roi_summary

    # Derive a minimal input summary if the caller did not provide one
    input_summary = req.input_summary
    if input_summary is None:
        est_input = estimation_data.get("estimation_input", {}) or {}
        module_ids = est_input.get("modules") or []
        if not module_ids:
            mod_src = estimation_data.get("estimation_result", {}).get("breakdown_by_module", {}) or {}
            module_ids = list(mod_src.keys()) if isinstance(mod_src, dict) else mod_src
        input_summary = {
            "complexity": est_input.get("complexity"),
            "module_count": len(module_ids or []),
        }

    if not estimation_data.get("module_subtasks"):
        est_input = estimation_data.get("estimation_input", {}) or {}
        module_ids = est_input.get("modules") or []
        if module_ids:
            try:
                complexity_level = ComplexityLevel(est_input.get("complexity", "M"))
            except ValueError:
                complexity_level = ComplexityLevel.MEDIUM
            contract_excerpt = None
            contract_src = estimation_data.get("contract_source") or {}
            if isinstance(contract_src, dict):
                contract_excerpt = contract_src.get("excerpt")
            est_input_obj = EstimationInput(
                modules=module_ids,
                complexity=complexity_level,
                environment=est_input.get("environment", "production"),
                integration_level=est_input.get("integration_level", "moderate_integration"),
                geography=est_input.get("geography", "dc_metro"),
                clearance_level=est_input.get("clearance_level", "secret"),
                is_prime_contractor=bool(est_input.get("is_prime_contractor", True)),
                custom_role_overrides=est_input.get("custom_role_overrides") or {},
                project_name=est_input.get("project_name"),
                government_poc=est_input.get("government_poc"),
                account_manager=est_input.get("account_manager"),
                service_delivery_mgr=est_input.get("service_delivery_mgr"),
                service_delivery_exec=est_input.get("service_delivery_exec"),
                site_location=est_input.get("site_location"),
                email=est_input.get("email"),
                fy=est_input.get("fy"),
                rap_number=est_input.get("rap_number"),
                psi_code=est_input.get("psi_code"),
                additional_comments=est_input.get("additional_comments"),
                security_protocols=est_input.get("security_protocols"),
                compliance_frameworks=est_input.get("compliance_frameworks"),
                additional_assumptions=est_input.get("additional_assumptions"),
                sites=est_input.get("sites") or 1,
                overtime=bool(est_input.get("overtime")),
                period_of_performance=est_input.get("period_of_performance"),
                estimating_method=est_input.get("estimating_method") or "engineering",
                historical_estimates=est_input.get("historical_estimates") or [],
                odc_items=est_input.get("odc_items") or [],
                fixed_price_items=est_input.get("fixed_price_items") or [],
                hardware_subtotal=est_input.get("hardware_subtotal") or 0.0,
                warranty_months=est_input.get("warranty_months") or 0,
                warranty_cost=est_input.get("warranty_cost") or 0.0,
            )
            try:
                module_subtasks = calculation_service.build_module_subtasks(
                    est_input_obj,
                    contract_excerpt=contract_excerpt,
                )
                estimation_data["module_subtasks"] = module_subtasks
            except Exception:
                pass

    try:
        text, raw = ai.rewrite_narrative_section(
            estimation_data=estimation_data,
            input_summary=input_summary,
            section=req.section,
            prompt=req.prompt,
            current_text=req.current_text,
            tone=req.tone,
            model=req.model,
        )
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e))

    return {"section": req.section, "text": text, "raw": raw}


@app.post("/api/v1/assumptions/generate")
def generate_additional_assumptions(req: AssumptionsPromptRequest, current_user: str = Depends(get_current_user)):
    """
    Generate additional assumptions text from scraped RFP content.
    """
    try:
        from .services.ai_service import AIService  # type: ignore
    except Exception:
        raise HTTPException(status_code=500, detail="AI module missing. Ensure ai_service.py exists.")

    ai = AIService()
    if not ai.is_configured():
        raise HTTPException(status_code=500, detail="OPENAI_API_KEY not configured")

    prompt_path = PROMPTS_DIR / "additional_assumptions_prompt.txt"
    if not prompt_path.exists():
        raise HTTPException(status_code=500, detail="Prompt template not found.")

    scraped_text = (req.scraped_text or "").strip()
    if not scraped_text:
        raise HTTPException(status_code=400, detail="scraped_text is required.")

    max_chars = 8000
    if len(scraped_text) > max_chars:
        scraped_text = scraped_text[:max_chars]

    context = _build_scrape_prompt_context(req, scraped_text)

    try:
        prompt_template = prompt_path.read_text(encoding="utf-8")
    except Exception:
        raise HTTPException(status_code=500, detail="Unable to read prompt template.")

    try:
        text, raw = ai.generate_additional_assumptions(prompt_template, context)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    return {"text": text, "raw": raw}


@app.post("/api/v1/comments/generate")
def generate_additional_comments(req: AssumptionsPromptRequest, current_user: str = Depends(get_current_user)):
    """
    Generate additional comments text from scraped RFP content.
    """
    try:
        from .services.ai_service import AIService  # type: ignore
    except Exception:
        raise HTTPException(status_code=500, detail="AI module missing. Ensure ai_service.py exists.")

    ai = AIService()
    if not ai.is_configured():
        raise HTTPException(status_code=500, detail="OPENAI_API_KEY not configured")

    prompt_path = PROMPTS_DIR / "additional_comments_prompt.txt"
    if not prompt_path.exists():
        raise HTTPException(status_code=500, detail="Prompt template not found.")

    scraped_text = (req.scraped_text or "").strip()
    if not scraped_text:
        raise HTTPException(status_code=400, detail="scraped_text is required.")

    max_chars = 8000
    if len(scraped_text) > max_chars:
        scraped_text = scraped_text[:max_chars]

    context = _build_scrape_prompt_context(req, scraped_text)

    try:
        prompt_template = prompt_path.read_text(encoding="utf-8")
    except Exception:
        raise HTTPException(status_code=500, detail="Unable to read prompt template.")

    try:
        text, raw = ai.generate_additional_comments(prompt_template, context)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    return {"text": text, "raw": raw}


@app.post("/api/v1/security-protocols/generate")
def generate_security_protocols(req: AssumptionsPromptRequest, current_user: str = Depends(get_current_user)):
    """
    Generate security protocols text from scraped RFP content.
    """
    try:
        from .services.ai_service import AIService  # type: ignore
    except Exception:
        raise HTTPException(status_code=500, detail="AI module missing. Ensure ai_service.py exists.")

    ai = AIService()
    if not ai.is_configured():
        raise HTTPException(status_code=500, detail="OPENAI_API_KEY not configured")

    prompt_path = PROMPTS_DIR / "security_protocols_prompt.txt"
    if not prompt_path.exists():
        raise HTTPException(status_code=500, detail="Prompt template not found.")

    scraped_text = (req.scraped_text or "").strip()
    if not scraped_text:
        raise HTTPException(status_code=400, detail="scraped_text is required.")

    max_chars = 8000
    if len(scraped_text) > max_chars:
        scraped_text = scraped_text[:max_chars]

    context = _build_scrape_prompt_context(req, scraped_text)

    try:
        prompt_template = prompt_path.read_text(encoding="utf-8")
    except Exception:
        raise HTTPException(status_code=500, detail="Unable to read prompt template.")

    try:
        text, raw = ai.generate_security_protocols(prompt_template, context)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    return {"text": text, "raw": raw}


@app.post("/api/v1/compliance-frameworks/generate")
def generate_compliance_frameworks(req: AssumptionsPromptRequest, current_user: str = Depends(get_current_user)):
    """
    Generate compliance frameworks text from scraped RFP content.
    """
    try:
        from .services.ai_service import AIService  # type: ignore
    except Exception:
        raise HTTPException(status_code=500, detail="AI module missing. Ensure ai_service.py exists.")

    ai = AIService()
    if not ai.is_configured():
        raise HTTPException(status_code=500, detail="OPENAI_API_KEY not configured")

    prompt_path = PROMPTS_DIR / "compliance_frameworks_prompt.txt"
    if not prompt_path.exists():
        raise HTTPException(status_code=500, detail="Prompt template not found.")

    scraped_text = (req.scraped_text or "").strip()
    if not scraped_text:
        raise HTTPException(status_code=400, detail="scraped_text is required.")

    max_chars = 8000
    if len(scraped_text) > max_chars:
        scraped_text = scraped_text[:max_chars]

    context = _build_scrape_prompt_context(req, scraped_text)

    try:
        prompt_template = prompt_path.read_text(encoding="utf-8")
    except Exception:
        raise HTTPException(status_code=500, detail="Unable to read prompt template.")

    try:
        text, raw = ai.generate_compliance_frameworks(prompt_template, context)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    return {"text": text, "raw": raw}


@app.post("/api/v1/report")
def generate_report(req: ReportRequest, include_ai: bool = False, tone: str = "professional", current_user: str = Depends(get_current_user)):
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
        security_protocols=req.security_protocols,
        compliance_frameworks=req.compliance_frameworks,
        additional_assumptions=req.additional_assumptions,
        sites=req.sites,
        overtime=req.overtime,
        period_of_performance=req.period_of_performance,
        estimating_method=req.estimating_method or "engineering",
        historical_estimates=req.historical_estimates or [],
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
            "security_protocols": req.security_protocols,
            "compliance_frameworks": req.compliance_frameworks,
            "additional_assumptions": req.additional_assumptions,
        },
        "odc_items": req.odc_items or [],
        "fixed_price_items": req.fixed_price_items or [],
        "hardware_subtotal": req.hardware_subtotal or 0.0,
        "warranty_months": req.warranty_months or 0,
        "warranty_cost": req.warranty_cost or 0.0,
        "raci_matrix": req.raci_matrix or [],
        "roadmap_phases": req.roadmap_phases or [],
        "roi_inputs": {
            "capex_event_cost_low": req.roi_capex_event_cost_low,
            "capex_event_cost_high": req.roi_capex_event_cost_high,
            "capex_event_interval_months": req.roi_capex_event_interval_months,
            "downtime_cost_per_hour": req.roi_downtime_cost_per_hour,
            "current_availability": req.roi_current_availability,
            "target_availability": req.roi_target_availability,
            "legacy_support_savings_annual": req.roi_legacy_support_savings_annual,
        },
        "roi_horizon_years": 5,
        "tool_version": req.tool_version,
    }
    roi_summary = _compute_roi_summary(estimation_data.get("roi_inputs") or {}, 5, float(result.total_cost or 0))
    if roi_summary:
        estimation_data["roi_summary"] = roi_summary
    if req.contract_url or req.contract_excerpt:
        estimation_data["contract_source"] = {
            "url": req.contract_url,
            "excerpt": req.contract_excerpt,
        }
    input_summary = {
        "complexity": req.complexity,
        "module_count": len(req.modules),
    }
    module_subtasks = calculation_service.build_module_subtasks(
        est_input,
        contract_excerpt=req.contract_excerpt,
    )
    subtask_status = "deterministic"
    subtask_error: Optional[str] = None
    subtask_ai_raw: Optional[str] = None
    if req.use_ai_subtasks:
        try:
            from .services.ai_service import AIService  # type: ignore

            ai = AIService()
            if ai.is_configured():
                module_subtasks, subtask_ai_raw = ai.generate_subtasks(
                    module_subtasks,
                    contract_excerpt=req.contract_excerpt,
                    tone=tone,
                )
                subtask_status = "ai_generated"
            else:
                subtask_status = "ai_disabled"
        except Exception as e:
            # Keep deterministic subtasks but record failure
            subtask_status = "ai_failed"
            subtask_error = str(e)
    estimation_data["module_subtasks"] = module_subtasks
    estimation_data["subtask_generation_status"] = subtask_status
    if subtask_ai_raw:
        estimation_data["subtask_ai_raw"] = subtask_ai_raw
    if subtask_error:
        estimation_data["subtask_generation_error"] = subtask_error

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
        module_subtasks=module_subtasks,
    )

    from datetime import datetime
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"estimation_report_{ts}.pdf"

    storage_record: Optional[Dict[str, Any]] = None
    if storage_service.is_configured() and req.proposal_id:
        # Validate proposal ownership before persisting the report
        with get_session() as session:
            prop = (
                session.query(Proposal)
                .filter(Proposal.id == req.proposal_id, Proposal.owner_email == current_user)
                .one_or_none()
            )
            if not prop:
                raise HTTPException(status_code=404, detail="Proposal not found for current user")
            upload = storage_service.upload_bytes(
                pdf_bytes,
                key_prefix=f"proposals/{req.proposal_id}/reports",
                filename=filename,
                content_type="application/pdf",
            )
            doc = ProposalDocument(
                proposal_id=req.proposal_id,
                version=req.proposal_version,
                kind="report",
                filename=upload["filename"],
                content_type="application/pdf",
                bucket=upload["bucket"],
                key=upload["key"],
                size_bytes=len(pdf_bytes),
                meta={
                    "tone": tone,
                    "include_ai": include_ai,
                    "tool_version": req.tool_version,
                    "created_by": current_user,
                    "proposal_version": req.proposal_version,
                    "module_count": len(req.modules),
                    "complexity": req.complexity,
                    "total_cost": float(result.total_cost or 0),
                    "total_hours": float(result.total_labor_hours or 0),
                    "period_of_performance": req.period_of_performance,
                    "estimating_method": req.estimating_method,
                },
            )
            session.add(doc)
            # Commit happens via context manager in get_session
            storage_record = {
                "id": doc.id,
                "bucket": upload["bucket"],
                "key": upload["key"],
                "presigned_url": storage_service.presign_get(upload["key"]),
            }

    headers = {
        "Content-Disposition": f"attachment; filename=\"{filename}\""
    }
    if storage_record and storage_record.get("presigned_url"):
        headers["X-Report-Location"] = storage_record["presigned_url"]
        headers["X-Report-Document-Id"] = storage_record["id"]

    return StreamingResponse(
        iter([pdf_bytes]),
        media_type="application/pdf",
        headers=headers,
    )

# -----------------------------
# -----------------------------
# Proposal persistence endpoints
# -----------------------------

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


@app.post("/api/v1/contracts/sam/sync")
def sync_sam_contracts(current_user: str = Depends(get_current_user)):
    return _sync_sam_contracts(trigger="manual")


@app.get("/api/v1/contracts/sam/status")
def sam_sync_status():
    now = datetime.utcnow()
    with get_session() as session:
        state = _get_sync_state(session)
        _reset_daily_budget(state, now)
        remaining = max(0, SAM_SYNC_MAX_REQUESTS_PER_DAY - (state.requests_today or 0))
        return {
            "source": state.source,
            "last_run": _dt_to_str(state.last_run_at),
            "last_status": state.last_status,
            "last_error": state.last_error,
            "requests_today": state.requests_today,
            "requests_today_date": state.requests_today_date,
            "remaining_quota": remaining,
            "max_requests_per_day": SAM_SYNC_MAX_REQUESTS_PER_DAY,
            "last_result": state.last_result,
        }


@app.get("/api/v1/contracts")
def list_contracts(
    status: Optional[str] = None,
    q: Optional[str] = None,
    source: Optional[str] = None,
    limit: int = 100,
    offset: int = 0,
    current_user: str = Depends(get_current_user),
):
    with get_session() as session:
        query = session.query(ContractOpportunity)
        if status:
            statuses = [
                _normalize_contract_status(s)
                for s in status.split(",")
                if s.strip()
            ]
            if statuses:
                query = query.filter(ContractOpportunity.status.in_(statuses))
        if source:
            query = query.filter(ContractOpportunity.source == source)
        if q:
            needle = f"%{q.strip().lower()}%"
            query = query.filter(
                or_(
                    func.lower(ContractOpportunity.title).like(needle),
                    func.lower(ContractOpportunity.agency).like(needle),
                    func.lower(ContractOpportunity.naics).like(needle),
                )
            )
        rows = (
            query.order_by(ContractOpportunity.posted_at.desc(), ContractOpportunity.created_at.desc())
            .offset(max(0, offset))
            .limit(max(1, min(limit, 500)))
            .all()
        )
        return [_contract_to_dict(row) for row in rows]


@app.get("/api/v1/contracts/{contract_id}")
def get_contract(contract_id: str, current_user: str = Depends(get_current_user)):
    with get_session() as session:
        row = session.query(ContractOpportunity).filter(ContractOpportunity.id == contract_id).one_or_none()
        if not row:
            raise HTTPException(status_code=404, detail="Contract not found")
        return _contract_to_dict(row, include_raw=True)


@app.post("/api/v1/contracts")
def create_contract(body: ContractCreate, current_user: str = Depends(get_current_user)):
    status = _normalize_contract_status(body.status or "new")
    now = datetime.utcnow()
    synopsis = body.synopsis or None
    excerpt = body.contract_excerpt or (synopsis[:4000] if synopsis else None)
    proposal_id = body.proposal_id or None
    with get_session() as session:
        contract = ContractOpportunity(
            source=body.source or "manual",
            source_id=body.source_id,
            title=body.title,
            agency=body.agency,
            sub_agency=body.sub_agency,
            office=body.office,
            naics=body.naics,
            psc=body.psc,
            set_aside=body.set_aside,
            posted_at=body.posted_at,
            due_at=body.due_at,
            value=body.value,
            location=body.location,
            url=body.url,
            synopsis=synopsis,
            contract_excerpt=excerpt,
            status=status,
            proposal_id=proposal_id,
            report_submitted_at=body.report_submitted_at,
            decision_date=body.decision_date,
            awardee_name=body.awardee_name,
            award_value=body.award_value,
            award_notes=body.award_notes,
            win_factors=body.win_factors,
            loss_factors=body.loss_factors,
            analysis_notes=body.analysis_notes,
            tags=body.tags or [],
            last_seen_at=now,
            updated_at=now,
        )
        session.add(contract)
        session.flush()
        return _contract_to_dict(contract, include_raw=True)


@app.patch("/api/v1/contracts/{contract_id}")
def update_contract(contract_id: str, body: ContractUpdate, current_user: str = Depends(get_current_user)):
    patch = body.dict(exclude_unset=True)
    if "status" in patch:
        patch["status"] = _normalize_contract_status(patch["status"])
    if "proposal_id" in patch:
        patch["proposal_id"] = patch["proposal_id"] or None
    if "tags" in patch and patch["tags"] is not None:
        patch["tags"] = [t.strip() for t in patch["tags"] if t and t.strip()]
    now = datetime.utcnow()
    with get_session() as session:
        contract = session.query(ContractOpportunity).filter(ContractOpportunity.id == contract_id).one_or_none()
        if not contract:
            raise HTTPException(status_code=404, detail="Contract not found")
        for key, val in patch.items():
            setattr(contract, key, val)
        if patch.get("status") == "submitted" and not contract.report_submitted_at:
            contract.report_submitted_at = now
        if patch.get("status") in ("awarded", "lost") and not contract.decision_date:
            contract.decision_date = now
        if not contract.contract_excerpt and contract.synopsis:
            contract.contract_excerpt = contract.synopsis[:4000]
        contract.updated_at = now
        session.flush()
        return _contract_to_dict(contract, include_raw=True)


@app.get("/api/v1/contracts/stats")
def contract_stats(current_user: str = Depends(get_current_user)):
    with get_session() as session:
        rows = session.query(ContractOpportunity).all()
        state = _get_sync_state(session)

    total = len(rows)
    by_status = Counter([r.status for r in rows if r.status])
    awarded = by_status.get("awarded", 0)
    lost = by_status.get("lost", 0)
    win_rate = round((awarded / (awarded + lost)) * 100, 1) if (awarded + lost) > 0 else 0.0

    awarded_values = [r.award_value for r in rows if r.status == "awarded" and r.award_value]
    lost_values = [r.award_value for r in rows if r.status == "lost" and r.award_value]
    avg_award_value = round(sum(awarded_values) / len(awarded_values), 2) if awarded_values else None
    avg_lost_value = round(sum(lost_values) / len(lost_values), 2) if lost_values else None

    def top_counts(attr: str, status_key: str) -> List[Dict[str, Any]]:
        counts = Counter(
            [getattr(r, attr) for r in rows if r.status == status_key and getattr(r, attr)]
        )
        return [{"name": k, "count": v} for k, v in counts.most_common(5)]

    return {
        "total": total,
        "by_status": dict(by_status),
        "awarded": awarded,
        "lost": lost,
        "win_rate": win_rate,
        "avg_award_value": avg_award_value,
        "avg_lost_value": avg_lost_value,
        "top_agencies_awarded": top_counts("agency", "awarded"),
        "top_agencies_lost": top_counts("agency", "lost"),
        "top_naics_awarded": top_counts("naics", "awarded"),
        "top_naics_lost": top_counts("naics", "lost"),
        "last_sync": _dt_to_str(state.last_run_at),
        "last_sync_error": state.last_error,
    }


@app.post("/api/v1/subtasks/preview")
def preview_subtasks(req: ReportRequest, tone: str = "professional", debug: bool = True, current_user: str = Depends(get_current_user)):
    """
    Build module subtasks with optional AI enrichment for preview in the UI.
    """
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
        security_protocols=req.security_protocols,
        compliance_frameworks=req.compliance_frameworks,
        additional_assumptions=req.additional_assumptions,
        sites=req.sites,
        overtime=req.overtime,
        period_of_performance=req.period_of_performance,
        estimating_method=req.estimating_method or "engineering",
        historical_estimates=req.historical_estimates or [],
        odc_items=req.odc_items or [],
        fixed_price_items=req.fixed_price_items or [],
        hardware_subtotal=req.hardware_subtotal or 0.0,
        warranty_months=req.warranty_months or 0,
        warranty_cost=req.warranty_cost or 0.0,
    )

    deterministic_subtasks = calculation_service.build_module_subtasks(
        est_input, contract_excerpt=req.contract_excerpt
    )
    module_subtasks = deterministic_subtasks
    status = "deterministic"
    error: Optional[str] = None
    ai_raw: Optional[str] = None
    debug_payload: Optional[Dict[str, Any]] = None
    if req.use_ai_subtasks:
        try:
            from .services.ai_service import AIService  # type: ignore

            ai = AIService()
            if ai.is_configured():
                module_subtasks, ai_raw = ai.generate_subtasks(
                    deterministic_subtasks,
                    contract_excerpt=req.contract_excerpt,
                    tone=tone,
                )
                status = "ai_generated"
            else:
                status = "ai_disabled"
        except Exception as e:
            status = "ai_failed"
            error = str(e)
    if debug:
        try:
            from .services.ai_service import AIService  # type: ignore

            ai = AIService()
            guidance, sources = ai.build_subtask_guidance_debug(
                deterministic_subtasks,
                req.contract_excerpt,
            )
            debug_payload = {
                "module_guidance": guidance,
                "prompt_sources": sources,
            }
        except Exception as e:
            debug_payload = {"error": str(e)}

    response = {
        "module_subtasks": module_subtasks,
        "status": status,
        "error": error,
        "raw_ai_response": ai_raw,
    }
    if debug:
        response["debug"] = debug_payload
    return response


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
        response = ProposalResponse(
            id=proposal.id,
            public_id=proposal.public_id,
            title=proposal.title,
            created_at=str(proposal.created_at) if proposal.created_at else None,
        )

    # Optionally persist a copy of the payload to object storage so public previews
    # still work if the DB is cleaned between deploys.
    if storage_service.is_configured():
        try:
            storage_service.upload_bytes(
                json.dumps({
                    "id": response.id,
                    "public_id": response.public_id,
                    "title": response.title,
                    "payload": req.payload,
                    "created_at": response.created_at,
                }).encode("utf-8"),
                key_prefix=f"proposals/{response.public_id}",
                filename="payload.json",
                content_type="application/json",
            )
        except Exception:
            # Non-fatal: DB already has the record; storage just improves durability
            pass

    return response


@app.get("/api/v1/proposals/public/{public_id}")
def get_public_proposal(public_id: str):
    with get_session() as session:
        obj = session.query(Proposal).filter(Proposal.public_id == public_id).one_or_none()
        if obj:
            return {
                "id": obj.id,
                "public_id": obj.public_id,
                "title": obj.title,
                "payload": obj.payload,
                "created_at": str(obj.created_at) if obj.created_at else None,
            }

    # Fallback: attempt to load from object storage if configured
    if storage_service.is_configured():
        try:
            key = f"{storage_service.prefix}/{('proposals/' + public_id).strip('/')}/payload.json" if storage_service.prefix else f"proposals/{public_id}/payload.json"
            obj = storage_service.s3.get_object(Bucket=storage_service.bucket, Key=key)
            raw = obj["Body"].read().decode("utf-8")
            data = json.loads(raw)
            return {
                "id": data.get("id"),
                "public_id": data.get("public_id", public_id),
                "title": data.get("title"),
                "payload": data.get("payload"),
                "created_at": data.get("created_at"),
                "from_storage": True,
            }
        except Exception:
            pass

    raise HTTPException(status_code=404, detail="Not found")


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


@app.get("/api/v1/proposals/{proposal_id}/documents")
def list_documents(
    proposal_id: str,
    version: Optional[int] = None,
    presign: bool = True,
    current_user: str = Depends(get_current_user),
):
    with get_session() as session:
        prop = _get_owned_proposal(session, proposal_id, current_user)
        if not prop:
            raise HTTPException(status_code=404, detail="Proposal not found")
        query = session.query(ProposalDocument).filter(ProposalDocument.proposal_id == proposal_id)
        if version is not None:
            query = query.filter(ProposalDocument.version == version)
        rows = query.order_by(ProposalDocument.created_at.asc()).all()

    docs = []
    for r in rows:
        meta = r.meta or {}
        doc = {
            "id": r.id,
            "kind": r.kind,
            "filename": r.filename,
            "content_type": r.content_type,
            "bucket": r.bucket,
            "key": r.key,
            "size_bytes": r.size_bytes,
            "version": r.version,
            "created_at": str(r.created_at) if r.created_at else None,
            "meta": meta,
            "created_by": meta.get("created_by"),
            "tool_version": meta.get("tool_version"),
            "proposal_version": meta.get("proposal_version"),
            "total_cost": meta.get("total_cost"),
            "total_hours": meta.get("total_hours"),
            "module_count": meta.get("module_count"),
            "tone": meta.get("tone"),
            "include_ai": meta.get("include_ai"),
        }
        if presign and storage_service.is_configured():
            doc["url"] = storage_service.presign_get(r.key)
        docs.append(doc)
    return docs


@app.get("/api/v1/reports")
def list_reports(
    proposal_id: Optional[str] = None,
    presign: bool = True,
    current_user: str = Depends(get_current_user),
):
    with get_session() as session:
        query = (
            session.query(ProposalDocument, Proposal)
            .join(Proposal, Proposal.id == ProposalDocument.proposal_id)
            .filter(Proposal.owner_email == current_user, ProposalDocument.kind == "report")
        )
        if proposal_id:
            query = query.filter(ProposalDocument.proposal_id == proposal_id)
        rows = query.order_by(ProposalDocument.created_at.desc()).all()

    docs = []
    for doc, prop in rows:
        meta = doc.meta or {}
        row = {
            "id": doc.id,
            "kind": doc.kind,
            "filename": doc.filename,
            "content_type": doc.content_type,
            "bucket": doc.bucket,
            "key": doc.key,
            "size_bytes": doc.size_bytes,
            "version": doc.version,
            "created_at": str(doc.created_at) if doc.created_at else None,
            "meta": meta,
            "created_by": meta.get("created_by"),
            "tool_version": meta.get("tool_version"),
            "proposal_version": meta.get("proposal_version"),
            "total_cost": meta.get("total_cost"),
            "total_hours": meta.get("total_hours"),
            "module_count": meta.get("module_count"),
            "tone": meta.get("tone"),
            "include_ai": meta.get("include_ai"),
            "proposal_id": prop.id,
            "proposal_title": prop.title,
            "proposal_public_id": prop.public_id,
        }
        if presign and storage_service.is_configured():
            row["url"] = storage_service.presign_get(doc.key)
        docs.append(row)
    return docs


@app.post("/api/v1/proposals/{proposal_id}/documents")
async def upload_document(
    proposal_id: str,
    kind: str = "attachment",
    version: Optional[int] = None,
    source_url: Optional[str] = None,
    file: UploadFile = File(...),
    current_user: str = Depends(get_current_user),
):
    if not storage_service.is_configured():
        raise HTTPException(status_code=400, detail="Storage not configured. Set S3_BUCKET/S3_REPORT_BUCKET.")

    content = await file.read()
    content_type = file.content_type or "application/octet-stream"
    key_prefix = f"proposals/{proposal_id}/{kind}s"

    with get_session() as session:
        prop = _get_owned_proposal(session, proposal_id, current_user)
        if not prop:
            raise HTTPException(status_code=404, detail="Proposal not found")
        upload = storage_service.upload_bytes(
            content,
            key_prefix=key_prefix,
            filename=file.filename or "attachment",
            content_type=content_type,
        )
        doc = ProposalDocument(
            proposal_id=proposal_id,
            version=version,
            kind=kind,
            filename=upload["filename"],
            content_type=content_type,
            bucket=upload["bucket"],
            key=upload["key"],
            size_bytes=len(content),
            meta={"source_url": source_url} if source_url else None,
        )
        session.add(doc)
        # commit via context manager
        doc_id = doc.id

    return {
        "id": doc_id,
        "kind": kind,
        "filename": upload["filename"],
        "bucket": upload["bucket"],
        "key": upload["key"],
        "size_bytes": len(content),
        "content_type": content_type,
        "url": storage_service.presign_get(upload["key"]),
    }


@app.delete("/api/v1/proposals/{proposal_id}/documents/{document_id}")
def delete_document(
    proposal_id: str,
    document_id: str,
    current_user: str = Depends(get_current_user),
):
    with get_session() as session:
        prop = _get_owned_proposal(session, proposal_id, current_user)
        if not prop:
            raise HTTPException(status_code=404, detail="Proposal not found")
        doc = (
            session.query(ProposalDocument)
            .filter(
                ProposalDocument.id == document_id,
                ProposalDocument.proposal_id == proposal_id,
            )
            .one_or_none()
        )
        if not doc:
            raise HTTPException(status_code=404, detail="Document not found")
        key = doc.key
        session.delete(doc)

    if storage_service.is_configured() and key:
        storage_service.delete_object(key)

    return {"deleted": True, "id": document_id}


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


_start_sam_sync()

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
