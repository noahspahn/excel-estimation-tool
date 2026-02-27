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


class ProposalStoreService:
    """
    Proposal/version/document persistence.

    Uses DynamoDB when table names are configured; otherwise uses in-memory
    storage for local development.
    """

    def __init__(self) -> None:
        self.proposals_table_name = os.getenv("PROPOSALS_TABLE_NAME")
        self.versions_table_name = os.getenv("PROPOSAL_VERSIONS_TABLE_NAME")
        self.documents_table_name = os.getenv("PROPOSAL_DOCUMENTS_TABLE_NAME")
        self.in_lambda = bool(os.getenv("AWS_LAMBDA_FUNCTION_NAME"))

        self.proposals = None
        self.versions = None
        self.documents = None
        if (
            boto3 is not None
            and self.proposals_table_name
            and self.versions_table_name
            and self.documents_table_name
        ):
            region = os.getenv("AWS_REGION") or os.getenv("AWS_DEFAULT_REGION")
            session = boto3.session.Session(region_name=region)
            ddb = session.resource("dynamodb")
            self.proposals = ddb.Table(self.proposals_table_name)
            self.versions = ddb.Table(self.versions_table_name)
            self.documents = ddb.Table(self.documents_table_name)

        self._lock = threading.Lock()
        self._proposals_mem: Dict[str, Dict[str, Any]] = {}
        self._versions_mem: Dict[str, List[Dict[str, Any]]] = {}
        self._documents_mem: Dict[str, Dict[str, Dict[str, Any]]] = {}

    def mode(self) -> str:
        if self.proposals and self.versions and self.documents:
            return "dynamo"
        return "memory"

    def is_configured(self) -> bool:
        if self.proposals and self.versions and self.documents:
            return True
        return not self.in_lambda

    def new_proposal_id(self) -> str:
        return f"prop_{secrets.token_urlsafe(8)}"

    def new_public_id(self) -> str:
        return secrets.token_urlsafe(9)

    def new_version_id(self) -> str:
        return f"ver_{secrets.token_urlsafe(8)}"

    def new_document_id(self) -> str:
        return f"doc_{secrets.token_urlsafe(8)}"

    def _ensure_configured(self) -> None:
        if not self.is_configured():
            raise RuntimeError(
                "Proposal store is not configured. Set PROPOSALS_TABLE_NAME, "
                "PROPOSAL_VERSIONS_TABLE_NAME, and PROPOSAL_DOCUMENTS_TABLE_NAME."
            )

    def create_proposal(self, *, owner_email: str, title: Optional[str], payload: Dict[str, Any]) -> Dict[str, Any]:
        self._ensure_configured()
        now = _now_iso()
        proposal_id = self.new_proposal_id()
        public_id = self.new_public_id()
        proposal = {
            "proposal_id": proposal_id,
            "public_id": public_id,
            "owner_email": owner_email,
            "title": title,
            "payload": payload,
            "created_at": now,
            "updated_at": now,
        }
        version = {
            "proposal_id": proposal_id,
            "version": 1,
            "version_id": self.new_version_id(),
            "title": title,
            "payload": payload,
            "created_at": now,
        }
        if self.proposals:
            try:
                self.proposals.put_item(Item=_to_dynamo(proposal))
                self.versions.put_item(Item=_to_dynamo(version))
            except (BotoCoreError, ClientError) as exc:
                raise RuntimeError(f"Failed to create proposal: {exc}") from exc
            return proposal

        with self._lock:
            self._proposals_mem[proposal_id] = dict(proposal)
            self._versions_mem[proposal_id] = [dict(version)]
            self._documents_mem.setdefault(proposal_id, {})
        return proposal

    def get_owned_proposal(self, *, proposal_id: str, owner_email: str) -> Optional[Dict[str, Any]]:
        self._ensure_configured()
        if self.proposals:
            try:
                resp = self.proposals.get_item(Key={"proposal_id": proposal_id})
            except (BotoCoreError, ClientError) as exc:
                raise RuntimeError(f"Failed to fetch proposal: {exc}") from exc
            item = _from_dynamo(resp.get("Item")) if resp.get("Item") else None
            if not item or item.get("owner_email") != owner_email:
                return None
            return item

        with self._lock:
            item = self._proposals_mem.get(proposal_id)
            if not item or item.get("owner_email") != owner_email:
                return None
            return dict(item)

    def get_by_public_id(self, public_id: str) -> Optional[Dict[str, Any]]:
        self._ensure_configured()
        if self.proposals:
            if Key is not None:
                try:
                    resp = self.proposals.query(
                        IndexName="public-id-index",
                        KeyConditionExpression=Key("public_id").eq(public_id),
                        Limit=1,
                    )
                    items = resp.get("Items", [])
                    if items:
                        return _from_dynamo(items[0])
                except Exception:
                    pass
            if Attr is not None:
                try:
                    resp = self.proposals.scan(
                        FilterExpression=Attr("public_id").eq(public_id),
                        Limit=1,
                    )
                    items = resp.get("Items", [])
                    if items:
                        return _from_dynamo(items[0])
                except (BotoCoreError, ClientError) as exc:
                    raise RuntimeError(f"Failed to fetch public proposal: {exc}") from exc
            return None

        with self._lock:
            for item in self._proposals_mem.values():
                if item.get("public_id") == public_id:
                    return dict(item)
        return None

    def create_version(
        self,
        *,
        proposal_id: str,
        owner_email: str,
        title: Optional[str],
        payload: Dict[str, Any],
    ) -> Dict[str, Any]:
        self._ensure_configured()
        proposal = self.get_owned_proposal(proposal_id=proposal_id, owner_email=owner_email)
        if not proposal:
            raise KeyError("Proposal not found")
        now = _now_iso()

        if self.versions:
            try:
                resp = self.versions.query(
                    KeyConditionExpression=Key("proposal_id").eq(proposal_id),
                    ScanIndexForward=False,
                    Limit=1,
                )
                items = [_from_dynamo(i) for i in resp.get("Items", [])]
                next_version = int(items[0].get("version", 0)) + 1 if items else 1
            except (BotoCoreError, ClientError) as exc:
                raise RuntimeError(f"Failed to compute next proposal version: {exc}") from exc
        else:
            with self._lock:
                versions = self._versions_mem.get(proposal_id, [])
                next_version = int(versions[-1]["version"]) + 1 if versions else 1

        version = {
            "proposal_id": proposal_id,
            "version": next_version,
            "version_id": self.new_version_id(),
            "title": title or proposal.get("title"),
            "payload": payload,
            "created_at": now,
        }
        proposal["payload"] = payload
        if title is not None:
            proposal["title"] = title
        proposal["updated_at"] = now

        if self.proposals:
            try:
                self.versions.put_item(Item=_to_dynamo(version))
                self.proposals.put_item(Item=_to_dynamo(proposal))
            except (BotoCoreError, ClientError) as exc:
                raise RuntimeError(f"Failed to create proposal version: {exc}") from exc
            return version

        with self._lock:
            self._proposals_mem[proposal_id] = dict(proposal)
            self._versions_mem.setdefault(proposal_id, []).append(dict(version))
        return version

    def list_versions(self, *, proposal_id: str, owner_email: str) -> List[Dict[str, Any]]:
        self._ensure_configured()
        proposal = self.get_owned_proposal(proposal_id=proposal_id, owner_email=owner_email)
        if not proposal:
            return []
        if self.versions:
            try:
                resp = self.versions.query(
                    KeyConditionExpression=Key("proposal_id").eq(proposal_id),
                    ScanIndexForward=True,
                )
                rows = [_from_dynamo(i) for i in resp.get("Items", [])]
                rows.sort(key=lambda r: int(r.get("version") or 0))
                return rows
            except (BotoCoreError, ClientError) as exc:
                raise RuntimeError(f"Failed to list proposal versions: {exc}") from exc

        with self._lock:
            rows = [dict(v) for v in self._versions_mem.get(proposal_id, [])]
        rows.sort(key=lambda r: int(r.get("version") or 0))
        return rows

    def get_version(self, *, proposal_id: str, version: int, owner_email: str) -> Optional[Dict[str, Any]]:
        self._ensure_configured()
        proposal = self.get_owned_proposal(proposal_id=proposal_id, owner_email=owner_email)
        if not proposal:
            return None
        if self.versions:
            try:
                resp = self.versions.get_item(Key={"proposal_id": proposal_id, "version": int(version)})
            except (BotoCoreError, ClientError) as exc:
                raise RuntimeError(f"Failed to fetch proposal version: {exc}") from exc
            item = resp.get("Item")
            return _from_dynamo(item) if item else None

        with self._lock:
            for v in self._versions_mem.get(proposal_id, []):
                if int(v.get("version") or 0) == int(version):
                    return dict(v)
        return None

    def list_documents(
        self,
        *,
        proposal_id: str,
        owner_email: str,
        version: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        self._ensure_configured()
        proposal = self.get_owned_proposal(proposal_id=proposal_id, owner_email=owner_email)
        if not proposal:
            return []
        if self.documents:
            try:
                resp = self.documents.query(
                    KeyConditionExpression=Key("proposal_id").eq(proposal_id),
                    ScanIndexForward=True,
                )
                rows = [_from_dynamo(i) for i in resp.get("Items", [])]
            except (BotoCoreError, ClientError) as exc:
                raise RuntimeError(f"Failed to list proposal documents: {exc}") from exc
        else:
            with self._lock:
                rows = [dict(d) for d in self._documents_mem.get(proposal_id, {}).values()]

        if version is not None:
            rows = [r for r in rows if r.get("version") is not None and int(r.get("version")) == int(version)]
        rows.sort(key=lambda r: str(r.get("created_at") or ""))
        return rows

    def add_document(
        self,
        *,
        proposal_id: str,
        owner_email: str,
        kind: str,
        version: Optional[int],
        filename: str,
        content_type: Optional[str],
        bucket: str,
        key: str,
        size_bytes: int,
        meta: Optional[Dict[str, Any]],
    ) -> Dict[str, Any]:
        self._ensure_configured()
        proposal = self.get_owned_proposal(proposal_id=proposal_id, owner_email=owner_email)
        if not proposal:
            raise KeyError("Proposal not found")
        now = _now_iso()
        row = {
            "proposal_id": proposal_id,
            "document_id": self.new_document_id(),
            "kind": kind,
            "version": version,
            "filename": filename,
            "content_type": content_type,
            "bucket": bucket,
            "key": key,
            "size_bytes": int(size_bytes),
            "meta": meta or {},
            "created_at": now,
        }
        if self.documents:
            try:
                self.documents.put_item(Item=_to_dynamo(row))
            except (BotoCoreError, ClientError) as exc:
                raise RuntimeError(f"Failed to save proposal document metadata: {exc}") from exc
            return row

        with self._lock:
            self._documents_mem.setdefault(proposal_id, {})[row["document_id"]] = dict(row)
        return row

    def get_document(
        self,
        *,
        proposal_id: str,
        document_id: str,
        owner_email: str,
    ) -> Optional[Dict[str, Any]]:
        self._ensure_configured()
        proposal = self.get_owned_proposal(proposal_id=proposal_id, owner_email=owner_email)
        if not proposal:
            return None
        if self.documents:
            try:
                resp = self.documents.get_item(
                    Key={"proposal_id": proposal_id, "document_id": document_id}
                )
            except (BotoCoreError, ClientError) as exc:
                raise RuntimeError(f"Failed to fetch proposal document metadata: {exc}") from exc
            item = resp.get("Item")
            return _from_dynamo(item) if item else None

        with self._lock:
            item = self._documents_mem.get(proposal_id, {}).get(document_id)
            return dict(item) if item else None

    def delete_document(
        self,
        *,
        proposal_id: str,
        document_id: str,
        owner_email: str,
    ) -> bool:
        self._ensure_configured()
        proposal = self.get_owned_proposal(proposal_id=proposal_id, owner_email=owner_email)
        if not proposal:
            return False
        if self.documents:
            try:
                self.documents.delete_item(Key={"proposal_id": proposal_id, "document_id": document_id})
                return True
            except (BotoCoreError, ClientError):
                return False

        with self._lock:
            docs = self._documents_mem.get(proposal_id, {})
            return bool(docs.pop(document_id, None))
