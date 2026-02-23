#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _python_has_modules(python_exe: Path, modules: list[str]) -> bool:
    probe = (
        "import importlib.util, sys;"
        f"mods={modules!r};"
        "missing=[m for m in mods if importlib.util.find_spec(m) is None];"
        "sys.exit(0 if not missing else 1)"
    )
    proc = subprocess.run([str(python_exe), "-c", probe], cwd=str(ROOT))
    return proc.returncode == 0


def _resolve_backend_python() -> Path:
    backend_dir = ROOT / "backend"
    candidates = [
        backend_dir / "venv_311" / "Scripts" / "python.exe",
        backend_dir / ".venv" / "Scripts" / "python.exe",
        backend_dir / "venv" / "Scripts" / "python.exe",
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate

    venv_dir = backend_dir / ".venv"
    print("Creating backend virtual environment (.venv)...")
    _run_command([sys.executable, "-m", "venv", str(venv_dir)], ROOT)
    return venv_dir / "Scripts" / "python.exe"


def _ensure_backend_dependencies(python_exe: Path) -> None:
    required_modules = ["uvicorn", "fastapi", "jose"]
    if _python_has_modules(python_exe, required_modules):
        return
    print("Installing backend dependencies...")
    _run_command([str(python_exe), "-m", "pip", "install", "--upgrade", "pip"], ROOT)
    _run_command([str(python_exe), "-m", "pip", "install", "-r", "backend/requirements.txt"], ROOT)


def _wait_for_health(url: str, timeout_seconds: float) -> bool:
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        try:
            req = urllib.request.Request(url, method="GET")
            with urllib.request.urlopen(req, timeout=2) as resp:
                if 200 <= resp.status < 500:
                    return True
        except (urllib.error.URLError, TimeoutError):
            pass
        time.sleep(0.5)
    return False


def _shutdown(proc: subprocess.Popen[str], name: str) -> None:
    if proc.poll() is not None:
        return
    print(f"Stopping {name}...")
    proc.terminate()
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait(timeout=5)


def _run_command(cmd: list[str], cwd: Path) -> None:
    subprocess.run(cmd, cwd=str(cwd), check=True)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run local backend + frontend using local resources only.",
    )
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--backend-port", type=int, default=8000)
    parser.add_argument("--frontend-port", type=int, default=3000)
    parser.add_argument(
        "--backend-target",
        choices=["legacy", "next"],
        default="next",
        help="Frontend backend target (legacy|next).",
    )
    parser.add_argument(
        "--frontend-install",
        action="store_true",
        help="Run npm ci in frontend before starting dev server.",
    )
    parser.add_argument(
        "--backend-install",
        action="store_true",
        help="Force reinstall backend dependencies from backend/requirements.txt.",
    )
    args = parser.parse_args()

    frontend_dir = ROOT / "frontend"
    if args.frontend_install or not (frontend_dir / "node_modules").exists():
        print("Installing frontend dependencies...")
        _run_command(["npm", "ci"], frontend_dir)

    backend_python = _resolve_backend_python()
    if args.backend_install:
        print("Installing backend dependencies...")
        _run_command([str(backend_python), "-m", "pip", "install", "--upgrade", "pip"], ROOT)
        _run_command([str(backend_python), "-m", "pip", "install", "-r", "backend/requirements.txt"], ROOT)
    else:
        _ensure_backend_dependencies(backend_python)

    backend_env = os.environ.copy()
    backend_env.update(
        {
            "AUTH_REQUIRED": "false",
            "DEV_DEFAULT_USER_EMAIL": "local-dev@example.com",
            "DATABASE_URL": "sqlite:///./backend/local.dev.db",
            "REPORT_JOB_SELF_INVOKE": "false",
            "REPORTS_TABLE_NAME": "",
            "S3_BUCKET": "",
            "S3_REPORT_BUCKET": "",
            "COGNITO_REGION": "",
            "COGNITO_USER_POOL_ID": "",
            "COGNITO_CLIENT_ID": "",
            "SAM_API_KEY": "",
            "ALLOWED_ORIGINS": (
                f"http://{args.host}:{args.frontend_port},"
                f"http://localhost:{args.frontend_port},"
                f"http://127.0.0.1:{args.frontend_port}"
            ),
        }
    )

    frontend_env = os.environ.copy()
    frontend_env.update(
        {
            "VITE_API_URL": f"http://{args.host}:{args.frontend_port}",
            "VITE_BACKEND_TARGET": args.backend_target,
            "VITE_DISABLE_AUTH": "true",
            "VITE_APP_ENV": "local",
            "VITE_COGNITO_REGION": "",
            "VITE_COGNITO_CLIENT_ID": "",
            "VITE_DEV_BACKEND_ORIGIN": f"http://{args.host}:{args.backend_port}",
        }
    )

    backend_cmd = [
        str(backend_python),
        "-m",
        "uvicorn",
        "backend.app.main:app",
        "--reload",
        "--host",
        args.host,
        "--port",
        str(args.backend_port),
    ]
    frontend_cmd = [
        "npm",
        "run",
        "dev",
        "--",
        "--host",
        args.host,
        "--port",
        str(args.frontend_port),
    ]

    print("Starting local backend...")
    backend_proc = subprocess.Popen(backend_cmd, cwd=str(ROOT), env=backend_env)

    health_url = f"http://{args.host}:{args.backend_port}/api/health"
    if not _wait_for_health(health_url, timeout_seconds=30):
        _shutdown(backend_proc, "backend")
        print(f"Backend did not become healthy at {health_url}.")
        return 1

    print("Starting local frontend...")
    frontend_proc = subprocess.Popen(frontend_cmd, cwd=str(frontend_dir), env=frontend_env)

    print("")
    print("Local development stack is running:")
    print(f"- Frontend: http://{args.host}:{args.frontend_port}")
    print(f"- Backend:  http://{args.host}:{args.backend_port}")
    print(f"- Health:   {health_url}")
    print("- Resources: local sqlite, no S3/Dynamo/Cognito/App Runner")
    print("")
    print("Press Ctrl+C to stop.")

    exit_code = 0
    try:
        while True:
            backend_rc = backend_proc.poll()
            frontend_rc = frontend_proc.poll()
            if backend_rc is not None:
                print(f"Backend exited with code {backend_rc}.")
                exit_code = backend_rc or 1
                break
            if frontend_rc is not None:
                print(f"Frontend exited with code {frontend_rc}.")
                exit_code = frontend_rc or 1
                break
            time.sleep(0.5)
    except KeyboardInterrupt:
        print("")
        print("Stopping local stack...")
    finally:
        _shutdown(frontend_proc, "frontend")
        _shutdown(backend_proc, "backend")

    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
