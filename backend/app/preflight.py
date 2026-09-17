"""Production startup guard for the AquaSense inference model."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

from .detector import get_adapter

EXPECTED_CLASSES = {
    0: "shipwreck",
    1: "submarine_pipeline",
    2: "cylinder",
    3: "ghost_net",
    4: "ghost_pot_trap",
    5: "plastic_debris",
    6: "metal_debris",
}
DEFAULT_MODEL_SHA256 = "342954fdd4ef6a24b89797f68dbeda8ffd9180b1cc7f7f291324c5cee5898f53"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def require_model() -> dict:
    """Raise before API startup when production inference is not trustworthy."""
    adapter = get_adapter()
    if not adapter.is_ready:
        raise RuntimeError(
            f"AquaSense model is required but unavailable: {adapter.describe()}"
        )

    model_path = Path(adapter.config.model_path)
    if not model_path.is_file():
        raise RuntimeError(f"AquaSense model file does not exist: {model_path}")

    expected_sha = os.getenv("AQUASENSE_MODEL_SHA256", DEFAULT_MODEL_SHA256)
    actual_sha = _sha256(model_path)
    if expected_sha and actual_sha != expected_sha:
        raise RuntimeError(
            f"AquaSense model checksum mismatch: expected {expected_sha}, got {actual_sha}"
        )

    names = getattr(adapter._model, "names", None)
    if names != EXPECTED_CLASSES:
        raise RuntimeError(
            f"AquaSense model class mapping mismatch: expected {EXPECTED_CLASSES}, got {names}"
        )

    return {
        "status": "ready",
        "model_path": str(model_path),
        "model_sha256": actual_sha,
        "classes": names,
        "backend": adapter.describe()["backend"],
    }


def main() -> None:
    print(json.dumps(require_model(), sort_keys=True))


if __name__ == "__main__":
    main()
