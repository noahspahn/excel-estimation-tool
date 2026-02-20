import base64
import json
import os
import urllib.error
import urllib.parse
import urllib.request
from typing import Dict, Iterable, List, Optional, Tuple

LEGACY_BASE_URL = os.getenv("LEGACY_BASE_URL", "").strip().rstrip("/")

ROLES = [
    {"id": "solution_architect", "name": "Solution Architect", "base_hourly_rate": 175.0},
    {"id": "technical_lead", "name": "Technical Lead", "base_hourly_rate": 150.0},
    {"id": "senior_engineer", "name": "Senior Engineer", "base_hourly_rate": 135.0},
    {"id": "engineer", "name": "Engineer", "base_hourly_rate": 110.0},
    {"id": "junior_engineer", "name": "Junior Engineer", "base_hourly_rate": 85.0},
    {"id": "project_manager", "name": "Project Manager", "base_hourly_rate": 140.0},
    {"id": "business_analyst", "name": "Business Analyst", "base_hourly_rate": 125.0},
    {"id": "security_specialist", "name": "Security Specialist", "base_hourly_rate": 160.0},
    {"id": "data_engineer", "name": "Data Engineer", "base_hourly_rate": 145.0},
    {"id": "cloud_architect", "name": "Cloud Architect", "base_hourly_rate": 165.0},
]

MODULES = [
    {
        "id": "dt_discovery",
        "name": "Discovery & Current State Mapping",
        "focus_area": "DT",
        "base_hours_by_role": {
            "solution_architect": 40,
            "business_analyst": 80,
            "senior_engineer": 60,
            "project_manager": 30,
        },
        "prerequisites": [],
    },
    {
        "id": "dt_strategy",
        "name": "Digital Strategy Development",
        "focus_area": "DT",
        "base_hours_by_role": {
            "solution_architect": 60,
            "business_analyst": 100,
            "project_manager": 40,
        },
        "prerequisites": ["dt_discovery"],
    },
    {
        "id": "itm_assessment",
        "name": "Legacy System Assessment",
        "focus_area": "ITM",
        "base_hours_by_role": {
            "solution_architect": 50,
            "technical_lead": 80,
            "senior_engineer": 120,
            "security_specialist": 40,
        },
        "prerequisites": [],
    },
    {
        "id": "itm_network_refresh",
        "name": "Network Core Refresh",
        "focus_area": "ITM",
        "base_hours_by_role": {
            "technical_lead": 100,
            "senior_engineer": 200,
            "engineer": 150,
            "project_manager": 50,
        },
        "prerequisites": [],
    },
    {
        "id": "itm_server_migration",
        "name": "Server Infrastructure Migration",
        "focus_area": "ITM",
        "base_hours_by_role": {
            "solution_architect": 60,
            "technical_lead": 80,
            "senior_engineer": 160,
            "engineer": 200,
            "project_manager": 60,
        },
        "prerequisites": [],
    },
    {
        "id": "sa_audit",
        "name": "Security Audit & Assessment",
        "focus_area": "SA",
        "base_hours_by_role": {
            "security_specialist": 120,
            "senior_engineer": 80,
            "business_analyst": 40,
        },
        "prerequisites": [],
    },
    {
        "id": "sa_compliance",
        "name": "Compliance Framework Implementation",
        "focus_area": "SA",
        "base_hours_by_role": {
            "security_specialist": 160,
            "solution_architect": 40,
            "business_analyst": 80,
            "project_manager": 60,
        },
        "prerequisites": ["sa_audit"],
    },
    {
        "id": "sa_license_audit",
        "name": "License Audit & Rightsizing",
        "focus_area": "SA",
        "base_hours_by_role": {
            "business_analyst": 60,
            "senior_engineer": 40,
            "project_manager": 20,
        },
        "prerequisites": [],
    },
    {
        "id": "cm_assessment",
        "name": "Cloud Readiness Assessment",
        "focus_area": "CM",
        "base_hours_by_role": {
            "cloud_architect": 80,
            "solution_architect": 40,
            "security_specialist": 60,
            "business_analyst": 40,
        },
        "prerequisites": [],
    },
    {
        "id": "cm_migration_plan",
        "name": "Cloud Migration Planning",
        "focus_area": "CM",
        "base_hours_by_role": {
            "cloud_architect": 100,
            "solution_architect": 60,
            "project_manager": 80,
        },
        "prerequisites": ["cm_assessment"],
    },
    {
        "id": "cm_workload_migration",
        "name": "Workload Migration Execution",
        "focus_area": "CM",
        "base_hours_by_role": {
            "cloud_architect": 60,
            "technical_lead": 100,
            "senior_engineer": 200,
            "engineer": 240,
            "project_manager": 80,
        },
        "prerequisites": ["cm_migration_plan"],
    },
    {
        "id": "da_discovery",
        "name": "Data Landscape Discovery",
        "focus_area": "DA",
        "base_hours_by_role": {
            "data_engineer": 80,
            "business_analyst": 100,
            "solution_architect": 40,
        },
        "prerequisites": [],
    },
    {
        "id": "da_pipeline",
        "name": "Data Pipeline Development",
        "focus_area": "DA",
        "base_hours_by_role": {
            "data_engineer": 160,
            "senior_engineer": 120,
            "engineer": 100,
            "project_manager": 40,
        },
        "prerequisites": ["da_discovery"],
    },
]


def _normalize_path(event: Dict) -> str:
    path = str(event.get("path") or "/")
    stage = str((event.get("requestContext") or {}).get("stage") or "").strip("/")
    if stage and path.startswith(f"/{stage}/"):
        path = path[len(stage) + 1 :]
    if not path.startswith("/"):
        path = f"/{path}"
    return path


def _query_string(event: Dict) -> str:
    multi = event.get("multiValueQueryStringParameters") or {}
    pairs: List[Tuple[str, str]] = []
    if multi:
        for key, values in multi.items():
            if values is None:
                pairs.append((key, ""))
                continue
            for value in values:
                pairs.append((str(key), "" if value is None else str(value)))
    else:
        single = event.get("queryStringParameters") or {}
        pairs.extend((str(key), "" if value is None else str(value)) for key, value in single.items())
    return urllib.parse.urlencode(pairs, doseq=True) if pairs else ""


def _json_response(status: int, payload: Dict, extra_headers: Optional[Dict[str, str]] = None) -> Dict:
    headers = {
        "Content-Type": "application/json",
        "Cache-Control": "no-store",
        "X-Backend-Mode": "api-next",
    }
    if extra_headers:
        headers.update(extra_headers)
    return {
        "statusCode": status,
        "headers": headers,
        "body": json.dumps(payload),
    }


def _is_text_content_type(content_type: str) -> bool:
    ct = (content_type or "").lower()
    return (
        ct.startswith("text/")
        or ct.startswith("application/json")
        or ct.startswith("application/xml")
        or ct.startswith("application/javascript")
        or ct.startswith("application/x-www-form-urlencoded")
    )


def _strip_hop_by_hop(headers: Iterable[Tuple[str, str]]) -> Dict[str, str]:
    blocked = {
        "connection",
        "content-length",
        "host",
        "transfer-encoding",
        "x-amzn-trace-id",
        "x-forwarded-for",
        "x-forwarded-port",
        "x-forwarded-proto",
        "via",
    }
    clean: Dict[str, str] = {}
    for key, value in headers:
        lower = key.lower()
        if lower in blocked:
            continue
        clean[key] = value
    return clean


def _event_body(event: Dict) -> Optional[bytes]:
    body = event.get("body")
    if body is None:
        return None
    if event.get("isBase64Encoded"):
        return base64.b64decode(body)
    return str(body).encode("utf-8")


def _proxy_response(status: int, headers: Dict[str, str], body: bytes) -> Dict:
    content_type = headers.get("Content-Type") or headers.get("content-type") or ""
    if _is_text_content_type(content_type):
        text = body.decode("utf-8", errors="replace")
        return {
            "statusCode": status,
            "headers": headers,
            "body": text,
            "isBase64Encoded": False,
        }
    return {
        "statusCode": status,
        "headers": headers,
        "body": base64.b64encode(body).decode("ascii"),
        "isBase64Encoded": True,
    }


def _proxy_to_legacy(event: Dict, path: str) -> Dict:
    if not LEGACY_BASE_URL:
        return _json_response(
            501,
            {
                "detail": "api-next proxy is not configured",
                "path": path,
            },
        )

    query = _query_string(event)
    url = f"{LEGACY_BASE_URL}{path}"
    if query:
        url = f"{url}?{query}"

    method = str(event.get("httpMethod") or "GET").upper()
    body = _event_body(event)
    if method in {"GET", "HEAD"}:
        body = None

    incoming_headers = event.get("headers") or {}
    header_pairs = ((str(k), str(v)) for k, v in incoming_headers.items() if v is not None)
    outbound_headers = _strip_hop_by_hop(header_pairs)
    outbound_headers["X-Backend-Mode"] = "api-next-proxy"

    request = urllib.request.Request(url=url, data=body, headers=outbound_headers, method=method)

    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            upstream_body = response.read()
            upstream_headers = _strip_hop_by_hop(response.getheaders())
            upstream_headers["X-Backend-Mode"] = "api-next-proxy"
            return _proxy_response(response.getcode(), upstream_headers, upstream_body)
    except urllib.error.HTTPError as exc:
        upstream_body = exc.read()
        upstream_headers = _strip_hop_by_hop(exc.headers.items())
        upstream_headers["X-Backend-Mode"] = "api-next-proxy"
        return _proxy_response(exc.code, upstream_headers, upstream_body)
    except Exception as exc:  # pragma: no cover - defensive
        return _json_response(502, {"detail": f"Legacy proxy failed: {exc}"})


def handler(event, _context):
    path = _normalize_path(event)
    method = str(event.get("httpMethod") or "GET").upper()

    if method == "OPTIONS":
        return {
            "statusCode": 204,
            "headers": {
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Headers": "*",
                "Access-Control-Allow-Methods": "*",
            },
            "body": "",
        }

    if method == "GET" and path in {"/health", "/api/health"}:
        return _json_response(
            200,
            {
                "status": "healthy",
                "version": "2.0.0-next",
                "ai_configured": bool(os.getenv("OPENAI_API_KEY")),
                "backend_mode": "api-next",
                "legacy_proxy_configured": bool(LEGACY_BASE_URL),
            },
        )

    if method == "GET" and path == "/api/v1/modules":
        return _json_response(200, MODULES)

    if method == "GET" and path == "/api/v1/roles":
        return _json_response(200, ROLES)

    return _proxy_to_legacy(event, path)
