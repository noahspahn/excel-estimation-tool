from __future__ import annotations

import os
from unittest.mock import patch

from backend.app.services.report_job_service import ReportJobService


def test_report_job_service_memory_mode_create_and_update() -> None:
    with patch.dict(
        os.environ,
        {
            "REPORT_JOBS_TABLE_NAME": "",
        },
        clear=False,
    ):
        svc = ReportJobService()
        assert svc.mode() == "memory"
        assert svc.is_configured()

        created = svc.create_job(
            owner_email="dev@example.com",
            job_kind="report",
            request_payload={"request": {"project_name": "Test"}},
        )
        job_id = str(created["job_id"])
        assert job_id

        job = svc.get_job(job_id)
        assert job is not None
        assert job["owner_email"] == "dev@example.com"
        assert job["status"] == "queued"

        updated = svc.update_status(
            job_id=job_id,
            status="completed",
            result_payload={"ok": True},
        )
        assert updated is not None
        assert updated["status"] == "completed"
        assert updated["result_payload"] == {"ok": True}
