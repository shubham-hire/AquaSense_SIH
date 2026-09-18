"""Survey identifiers must never be able to influence filesystem paths."""
from __future__ import annotations

import io
from pathlib import Path

import pytest
from PIL import Image
from fastapi import HTTPException
from fastapi.testclient import TestClient

import app.main as main_module
from app.repository import Repository


@pytest.fixture()
def isolated_client(tmp_path: Path):
    main_module.DATA_DIR = tmp_path
    main_module.UPLOAD_DIR = tmp_path / "uploads"
    main_module.ARTIFACT_DIR = tmp_path / "artifacts"
    main_module.MODELS_DIR = tmp_path / "models"
    for directory in (
        main_module.DATA_DIR,
        main_module.UPLOAD_DIR,
        main_module.ARTIFACT_DIR,
        main_module.MODELS_DIR,
    ):
        directory.mkdir(parents=True, exist_ok=True)
    main_module.repository = Repository(tmp_path / "survey_id_test.sqlite3")
    with TestClient(main_module.app) as client:
        yield client


@pytest.mark.parametrize(
    "survey_id",
    [
        "mission-001",
        "SURVEY_SAGAR_NIDHI_09",
        "survey.2026.09",
        "a",
        "m" * 128,
    ],
)
def test_accepts_expected_identifiers(survey_id: str):
    assert main_module.validate_survey_id(survey_id) == survey_id


@pytest.mark.parametrize(
    "survey_id",
    [
        "..",
        "../../etc/passwd",
        "survey/../../secret",
        "survey/nested",
        "survey\\nested",
        "-leading-hyphen",
        ".hidden",
        "survey id",
        "survey\nid",
        "survey;rm",
        "",
        "m" * 129,
    ],
)
def test_rejects_unsafe_identifiers(survey_id: str):
    with pytest.raises(HTTPException) as error:
        main_module.validate_survey_id(survey_id)
    assert error.value.status_code == 422


def test_contained_path_rejects_escape(tmp_path: Path):
    with pytest.raises(HTTPException) as error:
        main_module._contained_path(tmp_path, "../escaped.png")
    assert error.value.status_code == 422


def test_contained_path_allows_direct_child(tmp_path: Path):
    resolved = main_module._contained_path(tmp_path, "survey-001.png")
    assert resolved.parent == tmp_path.resolve()


def test_ingest_rejects_unsafe_identifier(isolated_client: TestClient, tmp_path: Path):
    image_buffer = io.BytesIO()
    Image.new("L", (32, 32), color=90).save(image_buffer, format="PNG")
    # %5C decodes to a backslash, which still matches the route but must be refused.
    response = isolated_client.post(
        "/v1/surveys/bad%5C..%5Cid/ingest",
        files={"file": ("scan.png", image_buffer.getvalue(), "image/png")},
    )
    assert response.status_code == 422
    assert not any((tmp_path / "uploads").iterdir())


def test_read_endpoints_reject_unsafe_identifier(isolated_client: TestClient):
    for path in (
        "/v1/surveys/bad%5Cid/detections",
        "/v1/surveys/bad%5Cid/navigation",
        "/v1/surveys/bad%5Cid/sonar",
        "/v1/surveys/bad%5Cid/waterfall.png",
        "/v1/surveys/bad%5Cid/processing",
        "/v1/surveys/bad%5Cid/report.json",
    ):
        assert isolated_client.get(path).status_code == 422, path


def test_valid_identifier_still_ingests(isolated_client: TestClient, tmp_path: Path):
    image_buffer = io.BytesIO()
    Image.new("L", (32, 32), color=90).save(image_buffer, format="PNG")
    response = isolated_client.post(
        "/v1/surveys/mission-safe-001/ingest",
        files={"file": ("scan.png", image_buffer.getvalue(), "image/png")},
    )
    assert response.status_code == 200
    stored = list((tmp_path / "uploads").iterdir())
    assert len(stored) == 1
    assert stored[0].name.startswith("mission-safe-001-")
