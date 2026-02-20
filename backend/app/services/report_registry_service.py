from __future__ import annotations

import os
import secrets
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Dict, List, Optional

try:
    import boto3
    from boto3.dynamodb.conditions import Key
    from botocore.exceptions import BotoCoreError, ClientError
except ImportError:  # boto3 optional
    boto3 = None  # type: ignore[assignment]
    Key = None  # type: ignore[assignment]
    BotoCoreError = ClientError = Exception  # type: ignore[assignment]


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _to_dynamo(value: Any) -> Any:
    if isinstance(value, float):
        # DynamoDB stores numbers as Decimal.
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


class ReportRegistryService:
    """
    DynamoDB-backed metadata registry for generated reports.

    Table schema expected:
      - partition key: owner_email (S)
      - sort key: report_id (S)
    """

    def __init__(self) -> None:
        self.table_name = os.getenv("REPORTS_TABLE_NAME")
        self.table = None
        if boto3 is None or not self.table_name:
            return
        region = os.getenv("AWS_REGION") or os.getenv("AWS_DEFAULT_REGION")
        session = boto3.session.Session(region_name=region)
        self.table = session.resource("dynamodb").Table(self.table_name)

    def is_configured(self) -> bool:
        return bool(self.table)

    def new_report_id(self) -> str:
        return f"rep_{secrets.token_urlsafe(8)}"

    def get_report(self, owner_email: str, report_id: str) -> Optional[Dict[str, Any]]:
        if not self.is_configured():
            return None
        try:
            resp = self.table.get_item(Key={"owner_email": owner_email, "report_id": report_id})
        except (BotoCoreError, ClientError) as exc:
            raise RuntimeError(f"Failed to fetch report metadata: {exc}") from exc
        item = resp.get("Item")
        return _from_dynamo(item) if item else None

    def save_report(self, item: Dict[str, Any]) -> Dict[str, Any]:
        if not self.is_configured():
            raise RuntimeError("Report registry is not configured")
        clean = {k: v for k, v in item.items() if v is not None}
        try:
            self.table.put_item(Item=_to_dynamo(clean))
        except (BotoCoreError, ClientError) as exc:
            raise RuntimeError(f"Failed to save report metadata: {exc}") from exc
        return clean

    def delete_report(self, owner_email: str, report_id: str) -> bool:
        if not self.is_configured():
            return False
        try:
            self.table.delete_item(Key={"owner_email": owner_email, "report_id": report_id})
            return True
        except (BotoCoreError, ClientError):
            return False

    def list_reports(
        self,
        owner_email: str,
        *,
        proposal_id: Optional[str] = None,
        limit: int = 500,
    ) -> List[Dict[str, Any]]:
        if not self.is_configured():
            return []
        if Key is None:
            return []

        items: List[Dict[str, Any]] = []
        start_key = None
        while True:
            query_kwargs: Dict[str, Any] = {
                "KeyConditionExpression": Key("owner_email").eq(owner_email),
                "Limit": min(200, limit),
            }
            if start_key:
                query_kwargs["ExclusiveStartKey"] = start_key
            try:
                resp = self.table.query(**query_kwargs)
            except (BotoCoreError, ClientError) as exc:
                raise RuntimeError(f"Failed to list report metadata: {exc}") from exc

            rows = resp.get("Items", [])
            for row in rows:
                item = _from_dynamo(row)
                if proposal_id and item.get("proposal_id") != proposal_id:
                    continue
                items.append(item)
                if len(items) >= limit:
                    break
            if len(items) >= limit:
                break
            start_key = resp.get("LastEvaluatedKey")
            if not start_key:
                break

        items.sort(
            key=lambda r: (
                str(r.get("updated_at") or ""),
                str(r.get("created_at") or ""),
            ),
            reverse=True,
        )
        return items

    def to_api_row(
        self,
        item: Dict[str, Any],
        *,
        presigned_url: Optional[str] = None,
    ) -> Dict[str, Any]:
        row = {
            "id": item.get("report_id"),
            "filename": item.get("filename"),
            "report_label": item.get("report_label"),
            "content_type": item.get("content_type"),
            "bucket": item.get("bucket"),
            "key": item.get("key"),
            "size_bytes": item.get("size_bytes"),
            "created_at": item.get("created_at"),
            "updated_at": item.get("updated_at"),
            "created_by": item.get("created_by"),
            "tool_version": item.get("tool_version"),
            "proposal_version": item.get("proposal_version"),
            "total_cost": item.get("total_cost"),
            "total_hours": item.get("total_hours"),
            "module_count": item.get("module_count"),
            "complexity": item.get("complexity"),
            "period_of_performance": item.get("period_of_performance"),
            "estimating_method": item.get("estimating_method"),
            "tone": item.get("tone"),
            "include_ai": item.get("include_ai"),
            "proposal_id": item.get("proposal_id"),
            "proposal_title": item.get("proposal_title"),
            "proposal_public_id": item.get("proposal_public_id"),
        }
        if presigned_url:
            row["url"] = presigned_url
        return row

    def new_item(
        self,
        *,
        owner_email: str,
        report_id: str,
        filename: str,
        content_type: str,
        bucket: str,
        key: str,
        size_bytes: int,
        created_by: str,
        tool_version: Optional[str],
        proposal_id: Optional[str],
        proposal_title: Optional[str],
        proposal_public_id: Optional[str],
        proposal_version: Optional[int],
        total_cost: Optional[float],
        total_hours: Optional[float],
        module_count: Optional[int],
        complexity: Optional[str],
        period_of_performance: Optional[str],
        estimating_method: Optional[str],
        tone: Optional[str],
        include_ai: bool,
        report_label: Optional[str],
        payload: Optional[Dict[str, Any]],
        existing_created_at: Optional[str] = None,
    ) -> Dict[str, Any]:
        now = _now_iso()
        return {
            "owner_email": owner_email,
            "report_id": report_id,
            "created_at": existing_created_at or now,
            "updated_at": now,
            "filename": filename,
            "content_type": content_type,
            "bucket": bucket,
            "key": key,
            "size_bytes": size_bytes,
            "created_by": created_by,
            "tool_version": tool_version,
            "proposal_id": proposal_id,
            "proposal_title": proposal_title,
            "proposal_public_id": proposal_public_id,
            "proposal_version": proposal_version,
            "total_cost": total_cost,
            "total_hours": total_hours,
            "module_count": module_count,
            "complexity": complexity,
            "period_of_performance": period_of_performance,
            "estimating_method": estimating_method,
            "tone": tone,
            "include_ai": include_ai,
            "report_label": report_label,
            "payload": payload or {},
        }
