#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from dataclasses import dataclass
from typing import Any, Iterable, Optional

try:
    import requests
except ModuleNotFoundError:
    print("Missing dependency: requests. Attempting to install it for this Python environment...")
    try:
        subprocess.run(
            [sys.executable, "-m", "pip", "install", "requests"],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )
        import requests  # type: ignore
    except Exception:
        print("Failed to install requests automatically.")
        print("Run: python -m pip install requests")
        raise SystemExit(2)


@dataclass
class CheckResult:
    name: str
    ok: bool
    status_code: int
    expected: set[int]
    detail: str


def _to_set(values: Iterable[int]) -> set[int]:
    return {int(v) for v in values}


def _safe_json(resp: requests.Response) -> Any:
    try:
        return resp.json()
    except Exception:
        return None


def _detail_snippet(resp: requests.Response) -> str:
    data = _safe_json(resp)
    if isinstance(data, dict):
        return json.dumps(data, ensure_ascii=True)[:300]
    text = (resp.text or "").strip().replace("\n", " ")
    return text[:300]


class ApiSmokeSuite:
    def __init__(self, base_url: str, timeout: float, token: Optional[str]) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.session = requests.Session()
        self.results: list[CheckResult] = []
        if token:
            self.session.headers["Authorization"] = f"Bearer {token}"

    def check(
        self,
        name: str,
        method: str,
        path: str,
        expected_statuses: Iterable[int],
        **kwargs: Any,
    ) -> requests.Response:
        expected = _to_set(expected_statuses)
        url = f"{self.base_url}{path}"
        resp = self.session.request(method=method, url=url, timeout=self.timeout, **kwargs)
        ok = resp.status_code in expected
        detail = _detail_snippet(resp)
        self.results.append(
            CheckResult(
                name=name,
                ok=ok,
                status_code=resp.status_code,
                expected=expected,
                detail=detail,
            )
        )
        status = "PASS" if ok else "FAIL"
        print(f"[{status}] {name}: {resp.status_code} (expected {sorted(expected)})")
        if not ok:
            print(f"       {detail}")
        return resp

    def summary(self) -> int:
        failures = [r for r in self.results if not r.ok]
        print("")
        print(f"Checks: {len(self.results)} total, {len(failures)} failed")
        if failures:
            print("Failed checks:")
            for f in failures:
                print(
                    f"- {f.name}: got {f.status_code}, expected {sorted(f.expected)}; "
                    f"detail={f.detail}"
                )
            return 1
        return 0


def _wait_for_backend(base_url: str, timeout_seconds: float) -> bool:
    deadline = time.time() + max(1.0, timeout_seconds)
    while time.time() < deadline:
        try:
            resp = requests.get(f"{base_url.rstrip('/')}/api/health", timeout=2)
            if resp.status_code < 500:
                return True
        except requests.RequestException:
            pass
        time.sleep(0.5)
    return False


def main() -> int:
    parser = argparse.ArgumentParser(description="Smoke-test backend API endpoints.")
    parser.add_argument("--base-url", default=os.getenv("API_TEST_BASE_URL", "http://127.0.0.1:8000"))
    parser.add_argument("--timeout", type=float, default=float(os.getenv("API_TEST_TIMEOUT", "30")))
    parser.add_argument(
        "--wait-seconds",
        type=float,
        default=float(os.getenv("API_TEST_WAIT_SECONDS", "8")),
        help="How long to wait for backend readiness before exiting.",
    )
    parser.add_argument("--token", default=os.getenv("API_TEST_BEARER_TOKEN"))
    args = parser.parse_args()

    if not _wait_for_backend(args.base_url, args.wait_seconds):
        print(f"Backend is not reachable at {args.base_url}.")
        print("Start it first (recommended): python scripts/dev_local.py")
        print("Or point to a running backend: --base-url http://127.0.0.1:<port>")
        return 2

    suite = ApiSmokeSuite(args.base_url, args.timeout, args.token)

    suite.check("root", "GET", "/", [200])
    suite.check("health", "GET", "/health", [200])
    suite.check("api health", "GET", "/api/health", [200])

    modules_resp = suite.check("list modules", "GET", "/api/v1/modules", [200])
    modules_data = _safe_json(modules_resp)
    if not isinstance(modules_data, list) or not modules_data:
        print("No modules available for downstream tests.")
        return 1
    module_id = str(modules_data[0].get("id") or "").strip()
    if not module_id:
        print("Module payload missing id.")
        return 1

    suite.check("list roles", "GET", "/api/v1/roles", [200])
    suite.check(
        "calculate",
        "POST",
        "/api/v1/calculate",
        [200],
        json={"base_hours": 120, "complexity": "M"},
    )

    base_estimate_payload = {
        "modules": [module_id],
        "complexity": "M",
        "project_name": "Endpoint Smoke Test",
        "sites": 1,
        "overtime": False,
    }
    estimate_resp = suite.check("estimate", "POST", "/api/v1/estimate", [200], json=base_estimate_payload)
    estimate_data = _safe_json(estimate_resp) if estimate_resp.status_code == 200 else {}

    narrative_payload = {
        **base_estimate_payload,
        "tone": "professional",
    }
    suite.check("narrative", "POST", "/api/v1/narrative", [200, 400], json=narrative_payload)
    suite.check(
        "narrative section",
        "POST",
        "/api/v1/narrative/section",
        [200, 400],
        json={
            "section": "executive_summary",
            "estimation_data": estimate_data if isinstance(estimate_data, dict) else {},
            "prompt": "Summarize key value drivers.",
        },
    )

    ai_prompt_body = {
        "scraped_text": "RFP sample text for smoke testing.",
        "project_name": "Endpoint Smoke Test",
        "selected_modules": [module_id],
    }
    suite.check("assumptions generate", "POST", "/api/v1/assumptions/generate", [200, 500], json=ai_prompt_body)
    suite.check("comments generate", "POST", "/api/v1/comments/generate", [200, 500], json=ai_prompt_body)
    suite.check(
        "security protocols generate",
        "POST",
        "/api/v1/security-protocols/generate",
        [200, 500],
        json=ai_prompt_body,
    )
    suite.check(
        "compliance frameworks generate",
        "POST",
        "/api/v1/compliance-frameworks/generate",
        [200, 500],
        json=ai_prompt_body,
    )

    report_payload = {
        **base_estimate_payload,
        "save_report": False,
        "use_ai_subtasks": False,
        "report_label": "Smoke Test Report",
    }
    report_resp = suite.check(
        "generate report",
        "POST",
        "/api/v1/report",
        [200],
        params={"include_ai": "false", "tone": "professional"},
        json=report_payload,
    )
    if report_resp.status_code == 200 and "application/pdf" not in report_resp.headers.get("content-type", ""):
        suite.results.append(
            CheckResult(
                name="generate report content-type",
                ok=False,
                status_code=report_resp.status_code,
                expected={200},
                detail=f"unexpected content-type={report_resp.headers.get('content-type')}",
            )
        )
        print("[FAIL] generate report content-type: expected application/pdf")

    report_job_resp = suite.check(
        "queue report job",
        "POST",
        "/api/v1/report/jobs",
        [200],
        params={"include_ai": "false", "tone": "professional"},
        json=report_payload,
    )
    report_job_id = None
    report_job_data = _safe_json(report_job_resp)
    if isinstance(report_job_data, dict):
        report_job_id = report_job_data.get("job_id")
    if report_job_id:
        suite.check("get report job", "GET", f"/api/v1/report/jobs/{report_job_id}", [200])

    suite.check(
        "scrape url",
        "POST",
        "/api/v1/scrape/url",
        [200],
        json={
            "url": "https://example.com",
            "max_bytes": 100_000,
            "max_chars": 2_000,
            "timeout": 8,
        },
    )

    contract_resp = suite.check(
        "create contract",
        "POST",
        "/api/v1/contracts",
        [200],
        json={
            "title": "Smoke Contract",
            "agency": "Test Agency",
            "status": "new",
            "synopsis": "Local smoke test contract entry.",
        },
    )
    contract_id = None
    contract_data = _safe_json(contract_resp)
    if isinstance(contract_data, dict):
        contract_id = contract_data.get("id")

    suite.check("list contracts", "GET", "/api/v1/contracts", [200])
    suite.check("contract stats", "GET", "/api/v1/contracts/stats", [200])
    suite.check("sam sync status", "GET", "/api/v1/contracts/sam/status", [200])
    suite.check("sam sync trigger", "POST", "/api/v1/contracts/sam/sync", [200])
    if contract_id:
        suite.check("get contract", "GET", f"/api/v1/contracts/{contract_id}", [200])
        suite.check(
            "patch contract",
            "PATCH",
            f"/api/v1/contracts/{contract_id}",
            [200],
            json={"status": "submitted", "analysis_notes": "Updated in smoke test"},
        )

    subtask_resp = suite.check(
        "subtask preview",
        "POST",
        "/api/v1/subtasks/preview",
        [200],
        json={**report_payload, "use_ai_subtasks": False},
    )
    if subtask_resp.status_code == 200:
        subtask_data = _safe_json(subtask_resp)
        if not isinstance(subtask_data, dict) or "module_subtasks" not in subtask_data:
            suite.results.append(
                CheckResult(
                    name="subtask preview shape",
                    ok=False,
                    status_code=subtask_resp.status_code,
                    expected={200},
                    detail="response missing module_subtasks",
                )
            )
            print("[FAIL] subtask preview shape: response missing module_subtasks")

    subtasks_job_resp = suite.check(
        "queue subtask preview job",
        "POST",
        "/api/v1/subtasks/preview/jobs",
        [200],
        json={**report_payload, "use_ai_subtasks": False},
    )
    subtasks_job_id = None
    subtasks_job_data = _safe_json(subtasks_job_resp)
    if isinstance(subtasks_job_data, dict):
        subtasks_job_id = subtasks_job_data.get("job_id")
    if subtasks_job_id:
        suite.check("get subtask preview job", "GET", f"/api/v1/subtasks/preview/jobs/{subtasks_job_id}", [200])

    proposal_payload = {
        "title": "Smoke Proposal",
        "payload": {"estimation": estimate_data, "meta": {"source": "smoke-test"}},
    }
    proposal_resp = suite.check("create proposal", "POST", "/api/v1/proposals", [200], json=proposal_payload)
    proposal_id = None
    public_id = None
    proposal_data = _safe_json(proposal_resp)
    if isinstance(proposal_data, dict):
        proposal_id = proposal_data.get("id")
        public_id = proposal_data.get("public_id")

    if proposal_id and public_id:
        suite.check("get public proposal", "GET", f"/api/v1/proposals/public/{public_id}", [200])
        suite.check("create proposal version", "POST", f"/api/v1/proposals/{proposal_id}/versions", [200], json={
            "title": "Smoke Proposal v2",
            "payload": {"revision": 2, "meta": {"source": "smoke-test"}},
        })
        suite.check("list proposal versions", "GET", f"/api/v1/proposals/{proposal_id}/versions", [200])
        suite.check("get proposal version 1", "GET", f"/api/v1/proposals/{proposal_id}/versions/1", [200])
        suite.check(
            "diff proposal versions",
            "GET",
            f"/api/v1/proposals/{proposal_id}/diff",
            [200],
            params={"from_version": 1, "to_version": 2},
        )
        suite.check("list proposal documents", "GET", f"/api/v1/proposals/{proposal_id}/documents", [200])

        upload_resp = suite.check(
            "upload proposal document",
            "POST",
            f"/api/v1/proposals/{proposal_id}/documents",
            [200, 400],
            files={"file": ("smoke.txt", b"smoke test", "text/plain")},
            data={"kind": "attachment"},
        )
        upload_data = _safe_json(upload_resp)
        if upload_resp.status_code == 200 and isinstance(upload_data, dict) and upload_data.get("id"):
            suite.check(
                "delete uploaded document",
                "DELETE",
                f"/api/v1/proposals/{proposal_id}/documents/{upload_data['id']}",
                [200],
            )
        else:
            suite.check(
                "delete missing document",
                "DELETE",
                f"/api/v1/proposals/{proposal_id}/documents/nonexistent",
                [404],
            )

    suite.check("list reports", "GET", "/api/v1/reports", [200])
    suite.check("get missing report payload", "GET", "/api/v1/reports/nonexistent/payload", [400, 404])
    suite.check("delete missing report", "DELETE", "/api/v1/reports/nonexistent", [400, 404])

    magic_resp = suite.check(
        "auth request link",
        "POST",
        "/api/v1/auth/request_link",
        [200, 403],
        json={"email": "smoke.local@example.com"},
    )
    magic_data = _safe_json(magic_resp)
    if magic_resp.status_code == 200 and isinstance(magic_data, dict) and magic_data.get("token"):
        suite.check(
            "auth exchange",
            "POST",
            "/api/v1/auth/exchange",
            [200],
            json={"token": magic_data["token"]},
        )

    return suite.summary()


if __name__ == "__main__":
    raise SystemExit(main())
