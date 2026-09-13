"""
test_review.py — Operator Review system tests.

Coverage:
  - ReviewDecision schema validation (outcome rules, corrected_class constraints,
    note length, nav_trustworthy, reviewed_by, reviewed_at default)
  - Repository: save_review / get_review / delete_review / reviews_for_survey
  - REST endpoints: PUT / GET / DELETE /v1/detections/{id}/review
  - Export enrichment: JSON report, CSV report, GeoJSON report
  - Edge cases: double-review overwrite, delete then re-add
"""
from __future__ import annotations

import csv
import io
import json
from datetime import datetime, timezone
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.repository import Repository
from app.schemas import ReviewDecision


# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------

SURVEY_ID = "test-survey-review"
DET_ID = "det-001"

_MINIMAL_DETECTION = {
    "id": DET_ID,
    "survey_id": SURVEY_ID,
    "classification": "plastic_debris",
    "confidence_percent": 72,
    "bounding_box": {"x": 0.1, "y": 0.2, "width_m": 3.0, "height_m": 2.0},
    "segmentation_mask": None,
    "position": {
        "latitude": 12.345,
        "longitude": 76.543,
        "position_source": "GPS_FIX",
        "refusal_reason": None,
    },
    "calibrated": True,
    "low_data_quality": False,
    "motion_uncorrected": False,
    "model_version": "yolo26n-test",
    "dsp_applied": True,
    "ping_timestamp": "2026-01-01T00:00:00",
    "ping_index": 0,
    "threat_level": "MEDIUM",
    "verification_features": {"targetContrast": 0.75, "shadowRatio": 0.5, "shadowSideConsistent": True},
    "feature_weights": {"targetContrast": 0.3},
    "provenance": {"pipeline_version": "0.1.0"},
}

_UNLOCATED_DETECTION = {
    **_MINIMAL_DETECTION,
    "id": "det-002",
    "position": {
        "latitude": None,
        "longitude": None,
        "position_source": "UNAVAILABLE",
        "refusal_reason": "No GPS fix during ping",
    },
}


@pytest.fixture()
def repo(tmp_path: Path) -> Repository:
    r = Repository(tmp_path / "test.db")
    r.ensure_survey(SURVEY_ID)
    r.replace_detections(SURVEY_ID, [_MINIMAL_DETECTION, _UNLOCATED_DETECTION])
    return r


@pytest.fixture()
def client(tmp_path: Path):
    """TestClient with a fresh, isolated Repository per test."""
    import app.main as main_module

    fresh_repo = Repository(tmp_path / "test.db")
    fresh_repo.ensure_survey(SURVEY_ID)
    fresh_repo.replace_detections(SURVEY_ID, [_MINIMAL_DETECTION, _UNLOCATED_DETECTION])
    fresh_repo.save_ingest(
        SURVEY_ID,
        str(tmp_path / "fake.xtf"),
        {
            "survey_id": SURVEY_ID,
            "file_name": "fake.xtf",
            "format": "XTF",
            "file_size_bytes": 1024,
            "ping_count": 10,
            "dynamic_range_db": 30.0,
            "speckle_index": 0.1,
            "dropout_ratio_percent": 0.0,
            "motion_artifact_rows": [],
            "resolution_meters_per_pixel": 0.1,
            "status": "PASS",
            "recommendations": [],
        },
    )
    original = main_module.repository
    main_module.repository = fresh_repo
    try:
        yield TestClient(main_module.app)
    finally:
        main_module.repository = original



# ---------------------------------------------------------------------------
# 1. Schema: ReviewDecision
# ---------------------------------------------------------------------------

class TestReviewDecisionSchema:
    def test_confirmed_valid(self):
        rv = ReviewDecision(outcome="CONFIRMED")
        assert rv.outcome == "CONFIRMED"
        assert rv.corrected_class is None
        assert rv.nav_trustworthy is True
        assert rv.reviewed_by == "operator"
        assert isinstance(rv.reviewed_at, datetime)

    def test_rejected_fp_valid(self):
        rv = ReviewDecision(outcome="REJECTED_FP", nav_trustworthy=False)
        assert rv.outcome == "REJECTED_FP"
        assert rv.nav_trustworthy is False

    def test_corrected_requires_corrected_class(self):
        with pytest.raises(ValueError, match="corrected_class is required"):
            ReviewDecision(outcome="CORRECTED")

    def test_corrected_with_class_valid(self):
        rv = ReviewDecision(outcome="CORRECTED", corrected_class="metal_drum_scrap")
        assert rv.corrected_class == "metal_drum_scrap"

    def test_corrected_class_rejected_for_non_corrected(self):
        with pytest.raises(ValueError, match="corrected_class must be null"):
            ReviewDecision(outcome="CONFIRMED", corrected_class="plastic_debris")

    def test_note_max_length_enforced(self):
        with pytest.raises(ValueError):
            ReviewDecision(outcome="CONFIRMED", note="x" * 1001)

    def test_note_at_max_length_allowed(self):
        rv = ReviewDecision(outcome="CONFIRMED", note="x" * 1000)
        assert len(rv.note) == 1000

    def test_reviewed_by_custom(self):
        rv = ReviewDecision(outcome="CONFIRMED", reviewed_by="alice")
        assert rv.reviewed_by == "alice"

    def test_reviewed_at_default_is_utc(self):
        rv = ReviewDecision(outcome="CONFIRMED")
        assert rv.reviewed_at.tzinfo is not None

    def test_reviewed_at_explicit(self):
        ts = datetime(2026, 6, 15, 12, 0, 0, tzinfo=timezone.utc)
        rv = ReviewDecision(outcome="CONFIRMED", reviewed_at=ts)
        assert rv.reviewed_at == ts


# ---------------------------------------------------------------------------
# 2. Repository: save / get / delete / reviews_for_survey
# ---------------------------------------------------------------------------

class TestReviewRepository:
    def test_get_review_returns_none_when_unreviewed(self, repo: Repository):
        assert repo.get_review(DET_ID) is None

    def test_save_and_get_round_trip(self, repo: Repository):
        rv = ReviewDecision(outcome="CONFIRMED", note="looks real")
        repo.save_review(DET_ID, rv.model_dump(mode="json"))
        stored = repo.get_review(DET_ID)
        assert stored is not None
        assert stored["outcome"] == "CONFIRMED"
        assert stored["note"] == "looks real"

    def test_save_overwrite_replaces_previous(self, repo: Repository):
        repo.save_review(DET_ID, ReviewDecision(outcome="CONFIRMED").model_dump(mode="json"))
        repo.save_review(DET_ID, ReviewDecision(outcome="REJECTED_FP").model_dump(mode="json"))
        assert repo.get_review(DET_ID)["outcome"] == "REJECTED_FP"

    def test_delete_existing_review(self, repo: Repository):
        repo.save_review(DET_ID, ReviewDecision(outcome="CONFIRMED").model_dump(mode="json"))
        deleted = repo.delete_review(DET_ID)
        assert deleted is True
        assert repo.get_review(DET_ID) is None

    def test_delete_nonexistent_review_returns_false(self, repo: Repository):
        assert repo.delete_review("det-nonexistent") is False

    def test_delete_then_re_add(self, repo: Repository):
        repo.save_review(DET_ID, ReviewDecision(outcome="CONFIRMED").model_dump(mode="json"))
        repo.delete_review(DET_ID)
        repo.save_review(DET_ID, ReviewDecision(outcome="REJECTED_FP").model_dump(mode="json"))
        assert repo.get_review(DET_ID)["outcome"] == "REJECTED_FP"

    def test_reviews_for_survey_empty_when_none(self, repo: Repository):
        assert repo.reviews_for_survey(SURVEY_ID) == {}

    def test_reviews_for_survey_returns_saved(self, repo: Repository):
        repo.save_review(DET_ID, ReviewDecision(outcome="CORRECTED", corrected_class="metal_drum_scrap").model_dump(mode="json"))
        rv_map = repo.reviews_for_survey(SURVEY_ID)
        assert DET_ID in rv_map
        assert rv_map[DET_ID]["corrected_class"] == "metal_drum_scrap"

    def test_reviews_for_survey_only_includes_that_survey(self, repo: Repository):
        """Reviews from another survey must not bleed into this survey's map."""
        other = "other-survey"
        repo.ensure_survey(other)
        other_det = {**_MINIMAL_DETECTION, "id": "det-other", "survey_id": other}
        repo.replace_detections(other, [other_det])
        repo.save_review("det-other", ReviewDecision(outcome="CONFIRMED").model_dump(mode="json"))
        rv_map = repo.reviews_for_survey(SURVEY_ID)
        assert "det-other" not in rv_map


# ---------------------------------------------------------------------------
# 3. REST endpoints
# ---------------------------------------------------------------------------

class TestReviewEndpoints:
    def test_put_review_confirmed(self, client: TestClient):
        resp = client.put(
            f"/v1/detections/{DET_ID}/review",
            json={"outcome": "CONFIRMED", "nav_trustworthy": True},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["ok"] is True
        assert body["outcome"] == "CONFIRMED"

    def test_put_review_corrected(self, client: TestClient):
        resp = client.put(
            f"/v1/detections/{DET_ID}/review",
            json={"outcome": "CORRECTED", "corrected_class": "metal_drum_scrap", "nav_trustworthy": True},
        )
        assert resp.status_code == 200

    def test_put_review_rejected_fp_with_note(self, client: TestClient):
        resp = client.put(
            f"/v1/detections/{DET_ID}/review",
            json={"outcome": "REJECTED_FP", "note": "shadow artifact", "nav_trustworthy": False},
        )
        assert resp.status_code == 200

    def test_put_review_unknown_detection_returns_404(self, client: TestClient):
        resp = client.put(
            "/v1/detections/nonexistent/review",
            json={"outcome": "CONFIRMED", "nav_trustworthy": True},
        )
        assert resp.status_code == 404

    def test_get_review_after_put(self, client: TestClient):
        client.put(
            f"/v1/detections/{DET_ID}/review",
            json={"outcome": "CONFIRMED", "note": "verified by sonar", "nav_trustworthy": True},
        )
        resp = client.get(f"/v1/detections/{DET_ID}/review")
        assert resp.status_code == 200
        body = resp.json()
        assert body["outcome"] == "CONFIRMED"
        assert body["note"] == "verified by sonar"
        assert body["nav_trustworthy"] is True

    def test_get_review_not_yet_submitted_returns_404(self, client: TestClient):
        resp = client.get(f"/v1/detections/{DET_ID}/review")
        assert resp.status_code == 404

    def test_delete_review(self, client: TestClient):
        client.put(f"/v1/detections/{DET_ID}/review", json={"outcome": "CONFIRMED", "nav_trustworthy": True})
        resp = client.delete(f"/v1/detections/{DET_ID}/review")
        assert resp.status_code == 200
        assert resp.json()["ok"] is True
        # Subsequent GET must return 404.
        get_resp = client.get(f"/v1/detections/{DET_ID}/review")
        assert get_resp.status_code == 404

    def test_delete_nonexistent_review_returns_404(self, client: TestClient):
        resp = client.delete(f"/v1/detections/{DET_ID}/review")
        assert resp.status_code == 404

    def test_put_overwrite_updates_outcome(self, client: TestClient):
        client.put(f"/v1/detections/{DET_ID}/review", json={"outcome": "CONFIRMED", "nav_trustworthy": True})
        client.put(f"/v1/detections/{DET_ID}/review", json={"outcome": "REJECTED_FP", "nav_trustworthy": False})
        body = client.get(f"/v1/detections/{DET_ID}/review").json()
        assert body["outcome"] == "REJECTED_FP"

    def test_put_schema_validation_error_returns_422(self, client: TestClient):
        # Missing corrected_class when outcome == CORRECTED
        resp = client.put(
            f"/v1/detections/{DET_ID}/review",
            json={"outcome": "CORRECTED", "nav_trustworthy": True},
        )
        assert resp.status_code == 422


# ---------------------------------------------------------------------------
# 4. Export enrichment
# ---------------------------------------------------------------------------

class TestExportEnrichment:
    def _submit_review(self, client: TestClient, outcome: str = "CONFIRMED", **kwargs):
        client.put(
            f"/v1/detections/{DET_ID}/review",
            json={"outcome": outcome, "nav_trustworthy": True, **kwargs},
        )

    def test_json_report_review_field_null_when_unreviewed(self, client: TestClient):
        resp = client.get(f"/v1/surveys/{SURVEY_ID}/report.json")
        assert resp.status_code == 200
        payload = resp.json()
        det = next(d for d in payload["detections"] if d["id"] == DET_ID)
        assert det["review"] is None

    def test_json_report_contains_review_when_reviewed(self, client: TestClient):
        self._submit_review(client, outcome="CONFIRMED")
        resp = client.get(f"/v1/surveys/{SURVEY_ID}/report.json")
        payload = resp.json()
        det = next(d for d in payload["detections"] if d["id"] == DET_ID)
        assert det["review"]["outcome"] == "CONFIRMED"

    def test_json_report_metadata_counts(self, client: TestClient):
        self._submit_review(client, outcome="REJECTED_FP")
        payload = client.get(f"/v1/surveys/{SURVEY_ID}/report.json").json()
        meta = payload["report_metadata"]
        assert meta["reviewed_count"] == 1
        assert meta["rejected_fp_count"] == 1
        assert meta["confirmed_count"] == 0

    def test_csv_report_review_columns_empty_when_unreviewed(self, client: TestClient):
        resp = client.get(f"/v1/surveys/{SURVEY_ID}/report.csv")
        reader = csv.DictReader(io.StringIO(resp.text))
        rows = list(reader)
        row = next(r for r in rows if r["detection_id"] == DET_ID)
        assert row["review_outcome"] == ""
        assert row["corrected_class"] == ""

    def test_csv_report_review_columns_populated_when_reviewed(self, client: TestClient):
        self._submit_review(client, outcome="CORRECTED", corrected_class="metal_drum_scrap", note="re-class")
        resp = client.get(f"/v1/surveys/{SURVEY_ID}/report.csv")
        reader = csv.DictReader(io.StringIO(resp.text))
        rows = list(reader)
        row = next(r for r in rows if r["detection_id"] == DET_ID)
        assert row["review_outcome"] == "CORRECTED"
        assert row["corrected_class"] == "metal_drum_scrap"
        assert row["operator_note"] == "re-class"

    def test_csv_report_has_six_review_columns(self, client: TestClient):
        resp = client.get(f"/v1/surveys/{SURVEY_ID}/report.csv")
        reader = csv.DictReader(io.StringIO(resp.text))
        headers = reader.fieldnames or []
        for col in ("review_outcome", "corrected_class", "nav_trustworthy", "operator_note", "reviewed_at", "reviewed_by"):
            assert col in headers, f"Missing CSV column: {col}"

    def test_geojson_review_fields_in_properties(self, client: TestClient):
        self._submit_review(client, outcome="CONFIRMED")
        resp = client.get(f"/v1/surveys/{SURVEY_ID}/geojson")
        fc = resp.json()
        feature = next(f for f in fc["features"] if f["properties"]["id"] == DET_ID)
        assert feature["properties"]["review_outcome"] == "CONFIRMED"
        assert feature["properties"]["nav_trustworthy"] is True

    def test_geojson_review_null_when_unreviewed(self, client: TestClient):
        resp = client.get(f"/v1/surveys/{SURVEY_ID}/geojson")
        fc = resp.json()
        feature = next(f for f in fc["features"] if f["properties"]["id"] == DET_ID)
        assert feature["properties"]["review_outcome"] is None
