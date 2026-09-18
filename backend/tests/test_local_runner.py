"""The local runner is the primary way AquaSense is operated, so its
guarantees are tested: the bundled checkpoint must match the verified build,
the environment must point only at local paths, and required runtime packages
must stay in sync with backend/requirements.txt.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
RUNNER_PATH = REPO_ROOT / "scripts" / "run_local.py"


def load_runner():
    specification = importlib.util.spec_from_file_location("run_local", RUNNER_PATH)
    assert specification is not None and specification.loader is not None
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def runner():
    return load_runner()


def test_runner_script_is_present() -> None:
    assert RUNNER_PATH.is_file()


def test_bundled_checkpoint_matches_the_verified_build(runner) -> None:
    # Catches a corrupted or swapped checkpoint before an operator sees
    # detections from a model nobody validated.
    assert runner.CHECKPOINT.is_file()
    assert runner.file_sha256(runner.CHECKPOINT) == runner.CHECKPOINT_SHA256
    assert runner.checkpoint_problem() is None


def test_environment_defaults_stay_on_this_machine(runner) -> None:
    environment = runner.local_environment({})
    assert Path(environment["AQUASENSE_MODEL_PATH"]) == runner.CHECKPOINT
    assert Path(environment["AQUASENSE_DATA_DIR"]) == runner.DATA_DIR
    assert environment["AQUASENSE_DEVICE"] == "cpu"
    # Ultralytics must never try to pip install anything at runtime.
    assert environment["YOLO_AUTOINSTALL"] == "false"
    for key, value in environment.items():
        if key.startswith("AQUASENSE_") and key != "AQUASENSE_MODEL_SHA256":
            assert "onrender.com" not in value
            assert "http://" not in value and "https://" not in value


def test_operator_overrides_are_preserved(runner) -> None:
    environment = runner.local_environment(
        {"AQUASENSE_DEVICE": "cuda", "AQUASENSE_CONF_THRESH": "0.25"}
    )
    assert environment["AQUASENSE_DEVICE"] == "cuda"
    assert environment["AQUASENSE_CONF_THRESH"] == "0.25"
    assert environment["YOLO_AUTOINSTALL"] == "false"


def test_required_modules_cover_backend_requirements(runner) -> None:
    requirements = (REPO_ROOT / "backend" / "requirements.txt").read_text()
    declared = {
        line.split(">")[0].split("=")[0].split("[")[0].strip().lower()
        for line in requirements.splitlines()
        if line.strip() and not line.strip().startswith("#")
    }
    checked = {
        package.split("[")[0].strip().lower()
        for package in runner.REQUIRED_MODULES.values()
    }
    # Every installed runtime dependency should be preflighted by the runner.
    assert declared <= checked


def test_check_mode_passes_when_nothing_is_missing(runner, monkeypatch, capsys) -> None:
    # CI intentionally runs without ultralytics installed, so the dependency
    # probe is stubbed to isolate the checkpoint and reporting behaviour.
    monkeypatch.setattr(runner, "missing_modules", lambda: [])
    assert runner.main(["--check"]) == 0
    assert "No cloud services are required" in capsys.readouterr().out


def test_check_mode_reports_every_missing_package(runner, monkeypatch, capsys) -> None:
    monkeypatch.setattr(runner, "missing_modules", lambda: ["ultralytics", "pyxtf"])
    assert runner.main(["--check"]) == 1
    error_output = capsys.readouterr().err
    assert "ultralytics" in error_output
    assert "pyxtf" in error_output
    assert "backend/requirements.txt" in error_output


def test_missing_checkpoint_is_reported_clearly(runner, monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(runner, "CHECKPOINT", tmp_path / "absent.pt")
    problem = runner.checkpoint_problem()
    assert problem is not None
    assert "missing" in problem


def test_corrupted_checkpoint_is_reported_with_both_hashes(
    runner, monkeypatch, tmp_path
) -> None:
    impostor = tmp_path / "best.pt"
    impostor.write_bytes(b"not the real checkpoint")
    monkeypatch.setattr(runner, "CHECKPOINT", impostor)
    problem = runner.checkpoint_problem()
    assert problem is not None
    assert runner.CHECKPOINT_SHA256 in problem
    assert runner.file_sha256(impostor) in problem
