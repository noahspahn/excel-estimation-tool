from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from html.parser import HTMLParser
from typing import Optional
from urllib.parse import urlparse
from urllib.request import Request, urlopen
import ssl


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
    user_agent: str = "EstimationToolScraper/0.1"


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


class WebScraperService:
    """
    Simple HTTP/HTML scraper focused on producing clean text.

    Uses only the Python standard library so it works in constrained
    environments and can be easily extended later (e.g., for
    contract-specific parsing, link following, etc.).
    """

    def __init__(self, default_user_agent: Optional[str] = None) -> None:
        self._default_user_agent = default_user_agent or "EstimationToolScraper/0.1"
        self._ssl_context = ssl.create_default_context()

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
        req = Request(target_url, headers=headers)
        fetched_at = datetime.now(timezone.utc)

        try:
            with urlopen(req, context=self._ssl_context, timeout=request.timeout) as resp:
                status = getattr(resp, "status", None)
                final_url = getattr(resp, "url", target_url)
                content_type = resp.headers.get("Content-Type")
                raw = resp.read(request.max_bytes + 1)
        except Exception as e:
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
                error=str(e),
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

