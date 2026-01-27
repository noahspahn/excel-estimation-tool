from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional
import json
import os
import urllib.parse
import urllib.request

from .web_scraper_service import DEFAULT_USER_AGENT


def _parse_iso_datetime(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    raw = value.strip()
    if not raw:
        return None
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except Exception:
        try:
            parsed = datetime.strptime(raw, "%m/%d/%Y").replace(tzinfo=timezone.utc)
        except Exception:
            try:
                parsed = datetime.strptime(raw, "%Y-%m-%d").replace(tzinfo=timezone.utc)
            except Exception:
                return None
    if parsed.tzinfo:
        parsed = parsed.astimezone(timezone.utc).replace(tzinfo=None)
    return parsed


def _first_value(payload: Dict[str, Any], keys: List[str]) -> Optional[Any]:
    for key in keys:
        if key in payload and payload[key] not in (None, ""):
            return payload[key]
    return None


def _normalize_location(payload: Dict[str, Any]) -> Optional[str]:
    place = payload.get("placeOfPerformance") or payload.get("placeOfPerformanceCity")
    if isinstance(place, str):
        return place.strip() or None
    if isinstance(place, dict):
        parts: List[str] = []
        for key in ("streetAddress", "street", "cityName", "city", "state", "zip", "country"):
            val = place.get(key)
            if isinstance(val, dict):
                val = val.get("name") or val.get("code")
            if val:
                parts.append(str(val))
        return ", ".join(parts) if parts else None
    return None


def _stringify(value: Any) -> Optional[str]:
    if value is None:
        return None
    if isinstance(value, (str, int, float)):
        return str(value)
    try:
        return json.dumps(value)
    except Exception:
        return str(value)


def normalize_sam_record(payload: Dict[str, Any]) -> Dict[str, Any]:
    source_id = _stringify(_first_value(payload, ["noticeId", "id", "opportunityId", "oppId"]))
    title = _stringify(_first_value(payload, ["title", "solicitationTitle", "noticeTitle"]))
    agency = _stringify(_first_value(payload, ["department", "agency", "agencyName", "organization"]))
    sub_agency = _stringify(_first_value(payload, ["subTier", "subAgency"]))
    office = _stringify(_first_value(payload, ["office", "officeName"]))
    naics = _stringify(_first_value(payload, ["naicsCode", "naics"]))
    psc = _stringify(_first_value(payload, ["pscCode", "psc"]))
    set_aside = _stringify(_first_value(payload, ["typeOfSetAside", "setAside", "setAsideType"]))
    posted_at = _parse_iso_datetime(_stringify(_first_value(payload, ["postedDate", "postDate", "publishDate"])))
    due_at = _parse_iso_datetime(_stringify(_first_value(payload, ["responseDeadLine", "responseDate", "dueDate"])))
    value = _stringify(_first_value(payload, ["baseAndAllOptionsValue", "estimatedValue", "awardValue"]))
    location = _normalize_location(payload) or _stringify(_first_value(payload, ["placeOfPerformanceCity", "placeOfPerformance"]))
    url = _stringify(_first_value(payload, ["uiLink", "link", "opportunityUrl", "url"]))
    synopsis = _stringify(_first_value(payload, ["description", "synopsis", "summary"]))
    excerpt = synopsis[:4000] if synopsis else None

    return {
        "source": "sam.gov",
        "source_id": source_id,
        "title": title,
        "agency": agency,
        "sub_agency": sub_agency,
        "office": office,
        "naics": naics,
        "psc": psc,
        "set_aside": set_aside,
        "posted_at": posted_at,
        "due_at": due_at,
        "value": value,
        "location": location,
        "url": url,
        "synopsis": synopsis,
        "contract_excerpt": excerpt,
        "raw_payload": payload,
    }


def fetch_sam_opportunities(
    api_key: str,
    query: Optional[str] = None,
    days_back: int = 7,
    limit: int = 25,
    offset: int = 0,
) -> Dict[str, Any]:
    posted_to = datetime.now(timezone.utc)
    days_back = max(1, days_back)
    posted_from = posted_to - timedelta(days=days_back)
    params = {
        "api_key": api_key,
        "limit": max(1, min(limit, 1000)),
        "offset": max(0, offset),
        "postedFrom": posted_from.strftime("%m/%d/%Y"),
        "postedTo": posted_to.strftime("%m/%d/%Y"),
    }
    if query:
        params["q"] = query
    url = "https://api.sam.gov/opportunities/v2/search?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"Accept": "application/json", "User-Agent": DEFAULT_USER_AGENT})
    with urllib.request.urlopen(req, timeout=20) as resp:
        raw = resp.read()
    return json.loads(raw.decode("utf-8", errors="ignore"))


def extract_sam_results(payload: Dict[str, Any]) -> List[Dict[str, Any]]:
    for key in ("opportunitiesData", "opportunities", "data", "results"):
        val = payload.get(key)
        if isinstance(val, list):
            return val
    return []
