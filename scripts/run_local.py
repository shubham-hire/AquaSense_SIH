#!/usr/bin/env python3
"""Run AquaSense entirely on this machine.

AquaSense is offline-first: the checkpoint, the SQLite database, the sonar
artifacts, and the exports all live on local disk, so no hosted service is
required to process a survey. This script verifies the setup, then starts the
API and the web console together.

    python3 scripts/run_local.py             # API + web console
    python3 scripts/run_local.py --backend   # API only
    python3 scripts/run_local.py --check     # verify the setup, start nothing
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CHECKPOINT = ROOT / "best.pt"
CHECKPOINT_SHA256 = "342954fdd4ef6a24b89797f68dbeda8ffd9180b1cc7f7f291324c5cee5898f53"
DATA_DIR = ROOT / "data"
BACKEND_HOST = "127.0.0.1"
BACKEND_PORT = 8000
FRONTEND_PORT = 3000

# Runtime packages the API needs before it can serve a single request, mapped
# from import name to the name used to install it.
REQUIRED_MODULES = {
    "fastapi": "fastapi",
    "uvicorn": "uvicorn[standard]",
    "numpy": "numpy",
    "PIL": "Pillow",
    "reportlab": "reportlab",
    "pyxtf": "pyxtf",
    "multipart": "python-multipart",
    "ultralytics": "ultralytics",
}

# Local-first defaults. Every value points at something on this machine, and
# YOLO_AUTOINSTALL is disabled so Ultralytics can never attempt to install a
# dependency mid-survey on a vessel with no uplink.
LOCAL_ENVIRONMENT = {
    "AQUASENSE_MODEL_PATH": str(CHECKPOINT),
    "AQUASENSE_MODEL_SHA256": CHECKPOINT_SHA256,
    "AQUASENSE_DATA_DIR": str(DATA_DIR),
    "AQUASENSE_DEVICE": "cpu",
    "YOLO_AUTOINSTALL": "false",
    "MPLBACKEND": "Agg",
}


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def local_environment(base: dict | None = None) -> dict:
    """Local-first environment, preserving any value the operator already set."""
    environment = dict(os.environ if base is None else base)
    for key, value in LOCAL_ENVIRONMENT.items():
        environment.setdefault(key, value)
    return environment


def missing_modules() -> list:
    """Install names of required Python packages that are not importable."""
    return [
        package
        for module, package in REQUIRED_MODULES.items()
        if importlib.util.find_spec(module) is None
    ]


def checkpoint_problem():
    """Describe why the bundled checkpoint cannot be trusted, else None."""
    if not CHECKPOINT.is_file():
        return (
            "The detection checkpoint is missing at "
            + str(CHECKPOINT)
            + ". It ships with the repository, so restore best.pt before running AquaSense."
        )
    actual = file_sha256(CHECKPOINT)
    if actual != CHECKPOINT_SHA256:
        return (
            "The checkpoint at "
            + str(CHECKPOINT)
            + " does not match the verified build.\n  expected sha256 "
            + CHECKPOINT_SHA256
            + "\n  actual   sha256 "
            + actual
        )
    return None


def check_setup() -> list:
    """Every blocking problem found, described in operator-friendly terms."""
    problems = []
    problem = checkpoint_problem()
    if problem:
        problems.append(problem)
    absent = missing_modules()
    if absent:
        problems.append(
            "Missing Python packages: "
            + ", ".join(absent)
            + "\n  Install them with: python3 -m pip install -r backend/requirements.txt"
        )
    return problems


def start_backend(environment: dict, port: int) -> subprocess.Popen:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    command = [
        sys.executable,
        "-m",
        "uvicorn",
        "backend.app.main:app",
        "--host",
        BACKEND_HOST,
        "--port",
        str(port),
    ]
    return subprocess.Popen(command, cwd=ROOT, env=environment)


def start_frontend(environment: dict):
    npm = shutil.which("npm")
    if npm is None:
        print(
            "npm was not found, so the web console was not started. "
            "The API is still running on its own.",
            file=sys.stderr,
        )
        return None
    if not (ROOT / "node_modules").is_dir():
        print(
            "node_modules is missing. Run 'npm install --legacy-peer-deps' first "
            "to enable the web console.",
            file=sys.stderr,
        )
        return None
    # The Vite dev server proxies /api to the local backend, so the browser
    # never needs an external API origin.
    return subprocess.Popen([npm, "run", "dev"], cwd=ROOT, env=environment)


def main(argv: list | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run AquaSense locally.")
    parser.add_argument("--backend", action="store_true", help="start only the API")
    parser.add_argument("--check", action="store_true", help="verify setup and exit")
    parser.add_argument("--port", type=int, default=BACKEND_PORT, help="API port")
    arguments = parser.parse_args(argv)

    problems = check_setup()
    if problems:
        print("AquaSense cannot start:\n", file=sys.stderr)
        for problem in problems:
            print("- " + problem + "\n", file=sys.stderr)
        return 1

    print("Checkpoint verified:  " + str(CHECKPOINT))
    print("Local data directory: " + str(DATA_DIR))
    if arguments.check:
        print("Setup looks good. No cloud services are required.")
        return 0

    environment = local_environment()
    api_origin = "http://" + BACKEND_HOST + ":" + str(arguments.port)
    console_origin = "http://localhost:" + str(FRONTEND_PORT)

    processes = []
    processes.append(start_backend(environment, arguments.port))
    print("API:          " + api_origin)
    print("API docs:     " + api_origin + "/docs")

    if not arguments.backend:
        # Give uvicorn a moment so the console's first request is not refused.
        time.sleep(1.5)
        frontend = start_frontend(environment)
        if frontend is not None:
            processes.append(frontend)
            print("Web console:  " + console_origin)

    print("\nPress Ctrl+C to stop.")
    exit_code = 0
    try:
        while True:
            for process in processes:
                if process.poll() is not None:
                    exit_code = process.returncode or 0
                    raise KeyboardInterrupt
            time.sleep(0.5)
    except KeyboardInterrupt:
        pass
    finally:
        for process in processes:
            if process.poll() is None:
                process.terminate()
        for process in processes:
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
