from __future__ import annotations

import os
import secrets
import threading
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Dict, Optional

try:
    import boto3
    from botocore.exceptions import BotoCoreError, ClientError
except ImportError:  # boto3 optional
    boto3 = None  # type: ignore[assignment]
    BotoCoreError = ClientError = Exception  # type: ignore[assignment]


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _to_dynamo(value: Any) -> Any:
    if isinstance(value, float):
        return Decimal(str(value))
    if isinstance(value, dict):
        return {k: _to_dynamo(v) for k, v in value.items() if v is not None}
    if isinstance(value, list):
        return [_to_dynamo(v) for v in value]
    return value


def _from_dynamo(value: Any) -> Any:
    if isinstance(value, Decimal):
        if value == value.to_integral_value():
            return int(value)
        return float(value)
    if isinstance(value, dict):
        return {k: _from_dynamo(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_from_dynamo(v) for v in value]
    return value


class ReportJobService:
    """
    Registry for async report jobs.

    Uses DynamoDB when REPORT_JOBS_TABLE_NAME is configured. Falls back to an
    in-memory store for local development.
    """

    def __init__(self) -> None:
        self.table_name = os.getenv("REPORT_JOBS_TABLE_NAME")
        self.in_lambda = bool(os.getenv("AWS_LAMBDA_FUNCTION_NAME"))
        self.table = None
        if boto3 is not None and self.table_name:
            region = os.getenv("AWS_REGION") or os.getenv("AWS_DEFAULT_REGION")
            session = boto3.session.Session(region_name=region)
            self.table = session.resource("dynamodb").Table(self.table_name)
        self._memory: Dict[str, Dict[str, Any]] = {}
        self._lock = threading.Lock()

    def mode(self) -> str:
        if self.table is not None:
            return "dynamo"
        return "memory"

    def is_configured(self) -> bool:
        if self.table is not None:
            return True
        # Memory fallback is acceptable for local dev only.
        return not self.in_lambda

    def new_job_id(self) -> str:
        return f"job_{secrets.token_urlsafe(8)}"

    def create_job(
        self,
        *,
        owner_email: str,
        job_kind: str,
        request_payload: Dict[str, Any],
        job_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        if not self.is_configured():
            raise RuntimeError(
                "Report jobs are not configured. Set REPORT_JOBS_TABLE_NAME and redeploy."
            )
        now = _now_iso()
        item = {
            "job_id": job_id or self.new_job_id(),
            "owner_email": owner_email,
            "job_kind": job_kind,
            "status": "queued",
            "request_payload": request_payload,
            "result_payload": {},
            "error": None,
            "created_at": now,
            "started_at": None,
            "finished_at": None,
            "updated_at": now,
        }
        self.save_job(item)
        return item

    def get_job(self, job_id: str) -> Optional[Dict[str, Any]]:
        if not self.is_configured() or not job_id:
            return None
        if self.table is not None:
            try:
                resp = self.table.get_item(Key={"job_id": job_id})
            except (BotoCoreError, ClientError) as exc:
                raise RuntimeError(f"Failed to fetch report job: {exc}") from exc
            item = resp.get("Item")
            return _from_dynamo(item) if item else None
        with self._lock:
            item = self._memory.get(job_id)
            return dict(item) if item else None

    def save_job(self, item: Dict[str, Any]) -> Dict[str, Any]:
        if not self.is_configured():
            raise RuntimeError(
                "Report jobs are not configured. Set REPORT_JOBS_TABLE_NAME and redeploy."
            )
        clean = {k: v for k, v in item.items() if v is not None}
        if self.table is not None:
            try:
                self.table.put_item(Item=_to_dynamo(clean))
            except (BotoCoreError, ClientError) as exc:
                raise RuntimeError(f"Failed to save report job: {exc}") from exc
            return clean
        with self._lock:
            self._memory[str(clean["job_id"])] = dict(clean)
        return clean

    def update_status(
        self,
        *,
        job_id: str,
        status: str,
        error: Optional[str] = None,
        result_payload: Optional[Dict[str, Any]] = None,
    ) -> Optional[Dict[str, Any]]:
        job = self.get_job(job_id)
        if not job:
            return None
        now = _now_iso()
        job["status"] = status
        job["updated_at"] = now
        if status == "running" and not job.get("started_at"):
            job["started_at"] = now
        if status in ("completed", "failed"):
            job["finished_at"] = now
        if error is not None:
            job["error"] = error
        if result_payload is not None:
            job["result_payload"] = result_payload
        self.save_job(job)
        return job
