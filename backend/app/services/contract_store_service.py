from __future__ import annotations

import os
import secrets
import threading
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Dict, List, Optional

try:
    import boto3
    from boto3.dynamodb.conditions import Attr, Key
    from botocore.exceptions import BotoCoreError, ClientError
except ImportError:  # boto3 optional
    boto3 = None  # type: ignore[assignment]
    Attr = Key = None  # type: ignore[assignment]
    BotoCoreError = ClientError = Exception  # type: ignore[assignment]


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _to_dynamo(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.astimezone(timezone.utc).isoformat()
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


def _normalize_datetime_value(value: Any) -> Optional[str]:
    if value is None:
        return None
    if isinstance(value, datetime):
        if value.tzinfo:
            value = value.astimezone(timezone.utc)
        return value.replace(tzinfo=None).isoformat()
    raw = str(value).strip()
    if not raw:
        return None
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        if parsed.tzinfo:
            parsed = parsed.astimezone(timezone.utc).replace(tzinfo=None)
        return parsed.isoformat()
    except Exception:
        return raw


class ContractStoreService:
    """
    Contract and sync-state persistence.

    Uses DynamoDB when CONTRACTS_TABLE_NAME + CONTRACT_SYNC_TABLE_NAME are set.
    Falls back to in-memory storage for local development.
    """

    def __init__(self) -> None:
        self.contracts_table_name = os.getenv("CONTRACTS_TABLE_NAME")
        self.sync_table_name = os.getenv("CONTRACT_SYNC_TABLE_NAME")
        self.in_lambda = bool(os.getenv("AWS_LAMBDA_FUNCTION_NAME"))

        self.contracts = None
        self.sync = None
        if boto3 is not None and self.contracts_table_name and self.sync_table_name:
            region = os.getenv("AWS_REGION") or os.getenv("AWS_DEFAULT_REGION")
            session = boto3.session.Session(region_name=region)
            ddb = session.resource("dynamodb")
            self.contracts = ddb.Table(self.contracts_table_name)
            self.sync = ddb.Table(self.sync_table_name)

        self._lock = threading.Lock()
        self._contracts_mem: Dict[str, Dict[str, Any]] = {}
        self._sync_mem: Dict[str, Dict[str, Any]] = {}

    def mode(self) -> str:
        if self.contracts and self.sync:
            return "dynamo"
        return "memory"

    def is_configured(self) -> bool:
        if self.contracts and self.sync:
            return True
        return not self.in_lambda

    def _ensure_configured(self) -> None:
        if not self.is_configured():
            raise RuntimeError(
                "Contract store is not configured. Set CONTRACTS_TABLE_NAME and CONTRACT_SYNC_TABLE_NAME."
            )

    def new_contract_id(self) -> str:
        return f"con_{secrets.token_urlsafe(8)}"

    def _normalize_contract_row(self, row: Dict[str, Any]) -> Dict[str, Any]:
        clean = dict(row)
        for key in (
            "posted_at",
            "due_at",
            "report_submitted_at",
            "decision_date",
            "last_seen_at",
            "created_at",
            "updated_at",
        ):
            if key in clean:
                clean[key] = _normalize_datetime_value(clean.get(key))
        if "tags" in clean and clean.get("tags") is None:
            clean["tags"] = []
        if "status" in clean and isinstance(clean["status"], str):
            clean["status"] = clean["status"].strip().lower().replace("-", "_").replace(" ", "_")
        return clean

    def get_sync_state(self, source: str) -> Optional[Dict[str, Any]]:
        self._ensure_configured()
        if self.sync:
            try:
                resp = self.sync.get_item(Key={"source": source})
            except (BotoCoreError, ClientError) as exc:
                raise RuntimeError(f"Failed to fetch contract sync state: {exc}") from exc
            item = resp.get("Item")
            return _from_dynamo(item) if item else None
        with self._lock:
            item = self._sync_mem.get(source)
            return dict(item) if item else None

    def save_sync_state(self, state: Dict[str, Any]) -> Dict[str, Any]:
        self._ensure_configured()
        now = _now_iso()
        item = dict(state)
        item["updated_at"] = item.get("updated_at") or now
        if not item.get("created_at"):
            item["created_at"] = now
        if self.sync:
            try:
                self.sync.put_item(Item=_to_dynamo(item))
            except (BotoCoreError, ClientError) as exc:
                raise RuntimeError(f"Failed to save contract sync state: {exc}") from exc
            return item
        with self._lock:
            self._sync_mem[str(item["source"])] = dict(item)
        return item

    def create_contract(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        self._ensure_configured()
        now = _now_iso()
        row = self._normalize_contract_row(payload)
        row["contract_id"] = row.get("contract_id") or self.new_contract_id()
        row["created_at"] = row.get("created_at") or now
        row["updated_at"] = row.get("updated_at") or now
        row["status"] = row.get("status") or "new"
        row["tags"] = row.get("tags") or []
        if self.contracts:
            try:
                self.contracts.put_item(Item=_to_dynamo(row))
            except (BotoCoreError, ClientError) as exc:
                raise RuntimeError(f"Failed to create contract: {exc}") from exc
            return row
        with self._lock:
            self._contracts_mem[str(row["contract_id"])] = dict(row)
        return row

    def get_contract(self, contract_id: str) -> Optional[Dict[str, Any]]:
        self._ensure_configured()
        if self.contracts:
            try:
                resp = self.contracts.get_item(Key={"contract_id": contract_id})
            except (BotoCoreError, ClientError) as exc:
                raise RuntimeError(f"Failed to fetch contract: {exc}") from exc
            item = resp.get("Item")
            return _from_dynamo(item) if item else None
        with self._lock:
            item = self._contracts_mem.get(contract_id)
            return dict(item) if item else None

    def save_contract(self, contract: Dict[str, Any]) -> Dict[str, Any]:
        self._ensure_configured()
        row = self._normalize_contract_row(contract)
        row["contract_id"] = row.get("contract_id") or self.new_contract_id()
        row["updated_at"] = row.get("updated_at") or _now_iso()
        if not row.get("created_at"):
            row["created_at"] = row["updated_at"]
        if self.contracts:
            try:
                self.contracts.put_item(Item=_to_dynamo(row))
            except (BotoCoreError, ClientError) as exc:
                raise RuntimeError(f"Failed to save contract: {exc}") from exc
            return row
        with self._lock:
            self._contracts_mem[str(row["contract_id"])] = dict(row)
        return row

    def update_contract(self, contract_id: str, patch: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        self._ensure_configured()
        current = self.get_contract(contract_id)
        if not current:
            return None
        merged = dict(current)
        merged.update(patch)
        merged["contract_id"] = contract_id
        merged["updated_at"] = _now_iso()
        return self.save_contract(merged)

    def list_contracts(
        self,
        *,
        statuses: Optional[List[str]] = None,
        source: Optional[str] = None,
        q: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[Dict[str, Any]]:
        self._ensure_configured()
        if self.contracts:
            rows: List[Dict[str, Any]] = []
            last_key = None
            while True:
                kwargs: Dict[str, Any] = {}
                if last_key:
                    kwargs["ExclusiveStartKey"] = last_key
                resp = self.contracts.scan(**kwargs)
                rows.extend([_from_dynamo(i) for i in resp.get("Items", [])])
                last_key = resp.get("LastEvaluatedKey")
                if not last_key:
                    break
        else:
            with self._lock:
                rows = [dict(v) for v in self._contracts_mem.values()]

        if statuses:
            normalized = {s.strip().lower() for s in statuses if s and s.strip()}
            rows = [r for r in rows if str(r.get("status", "")).lower() in normalized]
        if source:
            rows = [r for r in rows if str(r.get("source", "")) == source]
        if q:
            needle = q.strip().lower()
            if needle:
                rows = [
                    r
                    for r in rows
                    if needle in str(r.get("title") or "").lower()
                    or needle in str(r.get("agency") or "").lower()
                    or needle in str(r.get("naics") or "").lower()
                ]

        rows.sort(
            key=lambda r: (
                str(r.get("posted_at") or ""),
                str(r.get("created_at") or ""),
            ),
            reverse=True,
        )
        start = max(0, int(offset))
        end = start + max(1, min(int(limit), 5000))
        return rows[start:end]

    def find_by_source_source_id(self, source: str, source_id: str) -> Optional[Dict[str, Any]]:
        self._ensure_configured()
        if self.contracts and Key is not None:
            try:
                resp = self.contracts.query(
                    IndexName="source-id-index",
                    KeyConditionExpression=Key("source").eq(source) & Key("source_id").eq(source_id),
                    Limit=1,
                )
                items = resp.get("Items", [])
                if items:
                    return _from_dynamo(items[0])
            except Exception:
                pass
            if Attr is not None:
                try:
                    resp = self.contracts.scan(
                        FilterExpression=Attr("source").eq(source) & Attr("source_id").eq(source_id),
                        Limit=1,
                    )
                    items = resp.get("Items", [])
                    if items:
                        return _from_dynamo(items[0])
                except (BotoCoreError, ClientError) as exc:
                    raise RuntimeError(f"Failed to lookup contract by source id: {exc}") from exc
            return None

        with self._lock:
            for row in self._contracts_mem.values():
                if row.get("source") == source and row.get("source_id") == source_id:
                    return dict(row)
        return None
