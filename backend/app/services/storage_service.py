# backend/app/services/storage_service.py
from __future__ import annotations

import os
import re
import uuid
from typing import Dict, Optional

try:
    import boto3
    from botocore.exceptions import BotoCoreError, ClientError
except ImportError:  # boto3 optional; storage disabled if not installed
    boto3 = None  # type: ignore[assignment]
    BotoCoreError = ClientError = Exception  # type: ignore[assignment]


def _sanitize_filename(name: str) -> str:
    name = name.replace("\\", "/").split("/")[-1]  # drop any path components
    name = re.sub(r"[^A-Za-z0-9._-]+", "_", name)
    return name or "file"


class StorageService:
    """
    Thin wrapper around S3 for report/attachment storage.

    All uploads are placed under a configurable prefix so they
    stay grouped per environment.
    """

    def __init__(self) -> None:
        if boto3 is None:
            self.bucket = None
            self.prefix = ""
            self.s3 = None
            return
        self.bucket = os.getenv("S3_BUCKET") or os.getenv("S3_REPORT_BUCKET")
        self.prefix = (os.getenv("S3_PREFIX") or "").strip().strip("/")
        region = os.getenv("AWS_REGION") or os.getenv("AWS_DEFAULT_REGION")
        session = boto3.session.Session(region_name=region) if self.bucket else None
        self.s3 = session.client("s3") if session and self.bucket else None

    def is_configured(self) -> bool:
        return bool(self.s3 and self.bucket)

    def _make_key(self, *parts: str) -> str:
        clean_parts = [p.strip("/ ") for p in parts if p and p.strip("/ ")]
        if self.prefix:
            clean_parts.insert(0, self.prefix)
        return "/".join(clean_parts)

    def upload_bytes(
        self,
        content: bytes,
        *,
        key_prefix: str,
        filename: str,
        content_type: str = "application/octet-stream",
    ) -> Dict[str, str]:
        if not self.is_configured():
            raise RuntimeError("S3 not configured")

        safe_name = _sanitize_filename(filename)
        key = self._make_key(key_prefix, f"{uuid.uuid4().hex}_{safe_name}")

        try:
            self.s3.put_object(
                Bucket=self.bucket,
                Key=key,
                Body=content,
                ContentType=content_type,
            )
        except (BotoCoreError, ClientError) as exc:
            raise RuntimeError(f"Failed to upload to S3: {exc}") from exc

        return {"bucket": self.bucket, "key": key, "filename": safe_name}

    def presign_get(self, key: str, expires_in: int = 3600) -> Optional[str]:
        if not self.is_configured():
            return None
        try:
            return self.s3.generate_presigned_url(
                ClientMethod="get_object",
                Params={"Bucket": self.bucket, "Key": key},
                ExpiresIn=expires_in,
            )
        except (BotoCoreError, ClientError):
            return None
