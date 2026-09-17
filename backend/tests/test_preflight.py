from pathlib import Path
from types import SimpleNamespace

import pytest

import app.preflight as preflight


class FakeAdapter:
    def __init__(self, path: Path, ready=True, names=None):
        self.is_ready = ready
        self.config = SimpleNamespace(model_path=path)
        self._model = SimpleNamespace(
            names=preflight.EXPECTED_CLASSES if names is None else names
        )

    def describe(self):
        return {"status": "ready" if self.is_ready else "unavailable", "backend": "ultralytics"}


def test_preflight_refuses_missing_model(monkeypatch, tmp_path):
    adapter = FakeAdapter(tmp_path / "missing.pt", ready=False)
    monkeypatch.setattr(preflight, "get_adapter", lambda: adapter)
    with pytest.raises(RuntimeError, match="required but unavailable"):
        preflight.require_model()


def test_preflight_refuses_wrong_classes(monkeypatch, tmp_path):
    model = tmp_path / "best.pt"
    model.write_bytes(b"test-model")
    adapter = FakeAdapter(model, names={0: "wrong"})
    monkeypatch.setattr(preflight, "get_adapter", lambda: adapter)
    monkeypatch.setenv("AQUASENSE_MODEL_SHA256", preflight._sha256(model))
    with pytest.raises(RuntimeError, match="class mapping mismatch"):
        preflight.require_model()


def test_preflight_accepts_verified_model(monkeypatch, tmp_path):
    model = tmp_path / "best.pt"
    model.write_bytes(b"test-model")
    adapter = FakeAdapter(model)
    monkeypatch.setattr(preflight, "get_adapter", lambda: adapter)
    monkeypatch.setenv("AQUASENSE_MODEL_SHA256", preflight._sha256(model))
    result = preflight.require_model()
    assert result["status"] == "ready"
    assert result["classes"] == preflight.EXPECTED_CLASSES
