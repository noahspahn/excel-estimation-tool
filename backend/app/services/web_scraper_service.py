from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from html.parser import HTMLParser
from typing import Optional
from urllib.parse import urlparse
from urllib.request import Request, urlopen
import os
import ssl
import json

# Use a modern browser-like user agent by default so sites like Google Docs
# return full content instead of a "browser not supported" placeholder.
DEFAULT_USER_AGENT = os.getenv(
    "SCRAPER_USER_AGENT",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36 EstimationToolScraper/0.2",
)


@dataclass
class ScrapeRequest:
    """
    Configuration for a single scrape operation.

    This is intentionally minimal for now and can be
    extended later with things like allowlists, robots.txt
    handling, and custom parsing strategies.
    """

    url: str
    max_bytes: int = 500_000
    max_chars: int = 4_000
    timeout: float = 10.0
    user_agent: str = DEFAULT_USER_AGENT


@dataclass
class ScrapeResult:
    """Result of a scrape operation, suitable for feeding into downstream analysis."""

    url: str
    final_url: Optional[str]
    success: bool
    status_code: Optional[int]
    content_type: Optional[str]
    encoding: Optional[str]
    text_excerpt: str
    fetched_at: datetime
    truncated: bool = False
    error: Optional[str] = None


class _HTMLTextExtractor(HTMLParser):
    """
    Lightweight HTML → plain text extractor.

    This avoids adding external dependencies (e.g., BeautifulSoup)
    while still producing a reasonable text representation for LLMs.
    """

    def __init__(self) -> None:
        super().__init__()
        self._chunks: list[str] = []
        self._skip_stack: list[str] = []

    def handle_starttag(self, tag: str, attrs) -> None:  # type: ignore[override]
        if tag.lower() in ("script", "style", "noscript"):
            self._skip_stack.append(tag.lower())

    def handle_endtag(self, tag: str) -> None:  # type: ignore[override]
        tag = tag.lower()
        if self._skip_stack and self._skip_stack[-1] == tag:
            self._skip_stack.pop()

    def handle_data(self, data: str) -> None:  # type: ignore[override]
        if self._skip_stack:
            return
        text = data.strip()
        if text:
            self._chunks.append(text)

    def get_text(self) -> str:
        return " ".join(self._chunks)


def _extract_visible_text(html: str, max_chars: int) -> str:
    parser = _HTMLTextExtractor()
    parser.feed(html)
    parser.close()
    text = parser.get_text()
    if max_chars and max_chars > 0 and len(text) > max_chars:
        return text[:max_chars]
    return text


def _extract_google_doc_id(url: str) -> Optional[str]:
    parsed = urlparse(url)
    host = parsed.netloc.lower()
    if "docs.google.com" not in host:
        return None

    parts = [p for p in parsed.path.split("/") if p]
    for idx, part in enumerate(parts):
        if part == "d" and idx + 1 < len(parts):
            doc_id = parts[idx + 1]
            if doc_id and len(doc_id) > 8:  # basic sanity check to avoid catching "edit"
                return doc_id
    return None


def _scrape_sam_opportunity(opp_id: str, timeout: float, ssl_context: ssl.SSLContext) -> Optional[str]:
    """
    Best-effort scrape for SAM.gov opportunity pages without JS rendering.

    Uses the public JSON API to pull the full description instead of the
    skeleton HTML that omits content.
    """
    api_url = f"https://sam.gov/api/prod/opps/v2/opportunities/{opp_id}"
    headers = {
        "Accept": "*/*",
        "User-Agent": DEFAULT_USER_AGENT,
        "Referer": "https://sam.gov/",
    }

    # Try modern sam.gov API first; fall back to legacy if needed.
    for candidate in [
        api_url,
        f"https://sam.gov/api/prod/sgs/v1/opportunities/{opp_id}",
    ]:
        req = Request(candidate, headers=headers)
        try:
            with urlopen(req, context=ssl_context, timeout=timeout) as resp:
                raw = resp.read()
            data = json.loads(raw.decode("utf-8", errors="ignore"))
            break
        except Exception:
            data = None
    if not data:
        return None
    try:
        with urlopen(req, context=ssl_context, timeout=timeout) as resp:
            raw = resp.read()
    except Exception:
        return None

    try:
        data = json.loads(raw.decode("utf-8", errors="ignore"))
    except Exception:
        return None

    desc_parts: list[str] = []
    def add(val):
        v = (val or "").strip()
        if v:
            desc_parts.append(v)

    opp = data.get("opportunity") or data.get("data") or data
    meta = opp.get("data2") or opp.get("data") or {}

    add(meta.get("title"))
    add(meta.get("solicitationNumber") or meta.get("solicitation", {}).get("solicitationNumber"))

    deadlines = meta.get("solicitation", {}).get("deadlines", {})
    if deadlines.get("response"):
        add(f"Response due: {deadlines.get('response')}")
        if deadlines.get("responseTz"):
            add(f"Time zone: {deadlines.get('responseTz')}")

    location = meta.get("placeOfPerformance") or {}
    loc_parts = [
        location.get("streetAddress"),
        location.get("city", {}).get("name"),
        location.get("state", {}).get("name"),
        location.get("zip"),
    ]
    loc = ", ".join([p for p in loc_parts if p])
    if loc:
        add(f"Place of performance: {loc}")

    # SAM places the main description in an array under "description"
    desc_list = opp.get("description") or meta.get("description") or []
    if isinstance(desc_list, list):
        for d in desc_list:
            add(d.get("body") if isinstance(d, dict) else str(d))
    else:
        add(str(desc_list))

    if not desc_parts:
        return None
    return "\n\n".join(desc_parts)


def _scrape_google_doc(
    doc_id: str,
    target_url: str,
    request: ScrapeRequest,
    ssl_context: ssl.SSLContext,
    fetched_at: datetime,
) -> tuple[Optional[ScrapeResult], Optional[str]]:
    """
    Fetch a Google Doc using its export endpoints to obtain readable text.

    The standard HTML view returns a heavy JS app (and may block custom
    user agents), so we prefer the lightweight export formats.
    """
    base_url = f"https://docs.google.com/document/d/{doc_id}"
    export_urls = [
        (f"{base_url}/export?format=txt", "text"),
        (f"{base_url}/export?format=html", "html"),
    ]
    headers = {
        "User-Agent": request.user_agent or DEFAULT_USER_AGENT,
        "Accept": "text/plain, text/html;q=0.9, */*;q=0.8",
    }

    last_error: Optional[str] = None
    for export_url, kind in export_urls:
        try:
            with urlopen(
                Request(export_url, headers=headers), context=ssl_context, timeout=request.timeout
            ) as resp:
                status = getattr(resp, "status", None)
                final_url = getattr(resp, "url", export_url)
                content_type = resp.headers.get("Content-Type")
                raw = resp.read(request.max_bytes + 1)
        except Exception as e:
            last_error = str(e)
            continue

        if "accounts.google.com" in final_url:
            last_error = "Google Docs link requires authentication or is not publicly accessible."
            continue

        truncated = len(raw) > request.max_bytes
        if truncated:
            raw = raw[: request.max_bytes]

        encoding: Optional[str] = None
        if content_type and "charset=" in content_type:
            try:
                encoding = content_type.split("charset=", 1)[1].split(";", 1)[0].strip()
            except Exception:
                encoding = None
        if not encoding:
            encoding = "utf-8"

        if "html" in (content_type or "") or kind == "html":
            html = raw.decode(encoding, errors="replace")
            text_excerpt = _extract_visible_text(html, request.max_chars)
        else:
            text_excerpt = raw.decode(encoding, errors="replace")
            if request.max_chars and request.max_chars > 0 and len(text_excerpt) > request.max_chars:
                text_excerpt = text_excerpt[: request.max_chars]

        error_msg: Optional[str] = None
        if truncated:
            error_msg = "Response truncated to max_bytes; text excerpt may be incomplete."

        return (
            ScrapeResult(
                url=target_url,
                final_url=final_url,
                success=True,
                status_code=status,
                content_type=content_type,
                encoding=encoding,
                text_excerpt=text_excerpt,
                fetched_at=fetched_at,
                truncated=truncated,
                error=error_msg,
            ),
            None,
        )

    return None, last_error


class WebScraperService:
    """
    Simple HTTP/HTML scraper focused on producing clean text.

    Uses only the Python standard library so it works in constrained
    environments and can be easily extended later (e.g., for
    contract-specific parsing, link following, etc.).
    """

    def __init__(self, default_user_agent: Optional[str] = None) -> None:
        self._default_user_agent = default_user_agent or DEFAULT_USER_AGENT

        # Allow optional TLS verification disablement for environments where
        # the system trust store is incomplete (e.g., certain App Runner configs).
        # This should only be used for development / troubleshooting.
        disable_tls_verify = os.getenv("SCRAPER_DISABLE_TLS_VERIFY", "").lower() in (
            "1",
            "true",
            "yes",
        )
        ctx = ssl.create_default_context()
        if disable_tls_verify:
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE
        self._ssl_context = ctx

    def _normalize_url(self, url: str) -> str:
        url = (url or "").strip()
        if not url:
            raise ValueError("URL must not be empty")
        parsed = urlparse(url)
        if not parsed.scheme:
            # Default to https for bare hostnames
            return "https://" + url
        return url

    def scrape(self, request: ScrapeRequest) -> ScrapeResult:
        try:
            target_url = self._normalize_url(request.url)
        except Exception as e:
            return ScrapeResult(
                url=request.url,
                final_url=None,
                success=False,
                status_code=None,
                content_type=None,
                encoding=None,
                text_excerpt="",
                fetched_at=datetime.now(timezone.utc),
                truncated=False,
                error=str(e),
            )

        headers = {
            "User-Agent": request.user_agent or self._default_user_agent,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        }
        fetched_at = datetime.now(timezone.utc)

        parsed = urlparse(target_url)

        google_error: Optional[str] = None
        google_doc_id = _extract_google_doc_id(target_url)
        if google_doc_id:
            google_result, google_error = _scrape_google_doc(
                google_doc_id, target_url, request, self._ssl_context, fetched_at
            )
            if google_result:
                return google_result

        # Special-case SAM.gov pages to use their JSON API so we get real content.
        sam_text: Optional[str] = None
        if parsed.netloc.endswith("sam.gov") and "/opp/" in parsed.path:
            try:
                # Extract opportunity ID from path segments
                parts = [p for p in parsed.path.split("/") if p]
                if "opp" in parts:
                    idx = parts.index("opp")
                    if idx + 1 < len(parts):
                        opp_id = parts[idx + 1]
                        sam_text = _scrape_sam_opportunity(opp_id, request.timeout, self._ssl_context)
            except Exception:
                sam_text = None

        # If we successfully pulled meaningful SAM text, return now.
        if sam_text:
            text_excerpt = sam_text[: request.max_chars] if request.max_chars > 0 else sam_text
            return ScrapeResult(
                url=target_url,
                final_url=target_url,
                success=True,
                status_code=200,
                content_type="application/json",
                encoding="utf-8",
                text_excerpt=text_excerpt,
                fetched_at=fetched_at,
                truncated=len(sam_text) > request.max_chars,
                error=None,
            )

        req = Request(target_url, headers=headers)

        try:
            with urlopen(req, context=self._ssl_context, timeout=request.timeout) as resp:
                status = getattr(resp, "status", None)
                final_url = getattr(resp, "url", target_url)
                content_type = resp.headers.get("Content-Type")
                raw = resp.read(request.max_bytes + 1)
        except Exception as e:
            err = str(e)
            if google_error:
                err = f"{google_error} | {err}"
            return ScrapeResult(
                url=target_url,
                final_url=None,
                success=False,
                status_code=None,
                content_type=None,
                encoding=None,
                text_excerpt="",
                fetched_at=fetched_at,
                truncated=False,
                error=err,
            )

        truncated = len(raw) > request.max_bytes
        if truncated:
            raw = raw[: request.max_bytes]

        encoding: Optional[str] = None
        if content_type and "charset=" in content_type:
            try:
                encoding = content_type.split("charset=", 1)[1].split(";", 1)[0].strip()
            except Exception:
                encoding = None
        if not encoding:
            encoding = "utf-8"

        try:
            html = raw.decode(encoding, errors="replace")
        except Exception:
            encoding = "utf-8"
            html = raw.decode(encoding, errors="replace")

        text_excerpt = _extract_visible_text(html, request.max_chars)

        error_msg: Optional[str] = None
        if truncated:
            error_msg = "Response truncated to max_bytes; text excerpt may be incomplete."

        return ScrapeResult(
            url=target_url,
            final_url=final_url,
            success=True,
            status_code=status,
            content_type=content_type,
            encoding=encoding,
            text_excerpt=text_excerpt,
            fetched_at=fetched_at,
            truncated=truncated,
            error=error_msg,
        )

