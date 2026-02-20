from mangum import Mangum

from app.main import app


_handler = Mangum(app, lifespan="off")


def _normalize_path(path: str, stage: str) -> str:
    p = path or "/"
    stage_prefix = f"/{stage}" if stage else ""

    # CloudFront routes API Next requests as /api-next/*.
    if p == "/api-next":
        return "/"
    if p.startswith("/api-next/"):
        return p[len("/api-next") :]

    # For REST API events path can include stage prefix.
    if stage_prefix:
        stage_next = f"{stage_prefix}/api-next"
        if p == stage_next:
            return f"{stage_prefix}/"
        if p.startswith(f"{stage_next}/"):
            return f"{stage_prefix}{p[len(stage_next):]}"

    return p


def handler(event, context):
    request_context = event.get("requestContext") or {}
    stage = str(request_context.get("stage") or "").strip("/")

    if "path" in event:
        event["path"] = _normalize_path(str(event.get("path") or "/"), stage)
    if "rawPath" in event:
        event["rawPath"] = _normalize_path(str(event.get("rawPath") or "/"), stage)
    if isinstance(request_context, dict) and "path" in request_context:
        request_context["path"] = _normalize_path(str(request_context.get("path") or "/"), stage)

    return _handler(event, context)
