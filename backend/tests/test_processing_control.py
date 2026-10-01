"""Processing jobs must be single-flight and expose durable status."""
from __future__ import annotations

import asyncio
from pathlib import Path

import pytest
from fastapi import HTTPException

import app.main as main_module
from app.repository import Repository


def test_processing_status_round_trip(tmp_path: Path) -> None:
    repository = Repository(tmp_path / "status.sqlite3")
    repository.ensure_survey("survey-status")
    payload = {
        "event": "processing.failed",
        "survey_id": "survey-status",
        "detail": "inference failed",
    }

    repository.save_processing_status("survey-status", payload)

    assert repository.get_processing_status("survey-status") == payload


def test_interrupted_persisted_job_is_reported_as_failed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    survey_id = "survey-interrupted"
    repository = Repository(tmp_path / "interrupted.sqlite3")
    repository.ensure_survey(survey_id)
    repository.save_processing_status(
        survey_id,
        {"event": "processing.stage", "survey_id": survey_id, "stage": "detection"},
    )
    monkeypatch.setattr(main_module, "repository", repository)
    main_module.processing_tasks.pop(survey_id, None)
    main_module.event_hub._state.pop(survey_id, None)

    status = main_module.processing_status(survey_id)

    assert status["event"] == "processing.failed"
    assert "interrupted" in status["detail"]
    assert repository.get_processing_status(survey_id) == status


def test_duplicate_processing_request_is_rejected(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    survey_id = "survey-single-flight"
    repository = Repository(tmp_path / "processing.sqlite3")
    source = tmp_path / "source.png"
    source.write_bytes(b"placeholder")
    repository.save_ingest(survey_id, str(source), {"status": "PASS"})
    monkeypatch.setattr(main_module, "repository", repository)
    main_module.processing_tasks.pop(survey_id, None)

    async def scenario() -> None:
        release = asyncio.Event()

        async def slow_process(*_args, **_kwargs) -> None:
            await release.wait()

        monkeypatch.setattr(main_module, "_process_in_background", slow_process)
        started = await main_module.process_survey(survey_id)
        assert started["status"] == "processing_started"

        with pytest.raises(HTTPException) as error:
            await main_module.process_survey(survey_id)
        assert error.value.status_code == 409

        task = main_module.processing_tasks[survey_id]
        release.set()
        await task
        await asyncio.sleep(0)
        assert survey_id not in main_module.processing_tasks

    asyncio.run(scenario())
