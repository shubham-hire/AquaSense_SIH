"""Regression tests for zero-configuration local inference."""
from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys


def test_pipeline_defaults_to_committed_checkpoint() -> None:
    repository_root = Path(__file__).resolve().parents[2]
    expected_model = (repository_root / "best.pt").resolve()
    assert expected_model.is_file(), "the committed AquaSense checkpoint is missing"

    environment = os.environ.copy()
    environment.pop("AQUASENSE_MODEL_PATH", None)
    completed = subprocess.run(
        [
            sys.executable,
            "-c",
            "import os; import app.pipeline; print(os.environ['AQUASENSE_MODEL_PATH'])",
        ],
        cwd=repository_root,
        env=environment,
        text=True,
        capture_output=True,
        check=True,
        timeout=30,
    )

    configured_model = Path(completed.stdout.strip()).resolve()
    assert configured_model == expected_model
