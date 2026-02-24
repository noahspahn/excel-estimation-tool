from mangum import Mangum

from app.main import app


_handler = Mangum(app, lifespan="off")


def handler(event, context):
    if isinstance(event, dict) and event.get("job_type") == "report_job":
        from app.main import run_report_job_now

        run_report_job_now(
            job_id=str(event.get("job_id") or ""),
            owner_email=str(event.get("owner_email") or "") or None,
        )
        return {"status": "ok", "job_id": event.get("job_id")}

    return _handler(event, context)
