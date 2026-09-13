"""
detector.py — YOLO26 Nano Model Integration Adapter
=====================================================
AquaSense PS 26057 | SIH 2026

Public contract
---------------
    from .detector import Yolo26Adapter, DetectorConfig, RawDetection

    cfg    = DetectorConfig(model_path=Path("models_checkpoints/yolo26n_aquasense_marine.pt"))
    model  = Yolo26Adapter(cfg)          # safe to call even when weights missing
    model.load()                         # no-op when already loaded; raises if weights corrupt

    results: list[list[RawDetection]] = model.run_batch(tiles)   # tiles: list of np.ndarray HWC uint8

Key properties
--------------
* Model path, confidence, IoU, and batch size are all config-driven; nothing is hardcoded.
* When the model file does not exist or ``ultralytics`` is not installed the adapter
  returns an empty list and sets ``model.status == "unavailable"``.
* ONNX Runtime inference path (Jetson / CPU-only demo) is activated automatically
  when weights are a ``.onnx`` file.
* All returned ``RawDetection`` objects carry the model's own logit before any
  threshold is applied, so Platt scaling can be applied downstream without needing the adapter.
* The adapter is a drop-in replacement for the heuristic source in ``pipeline.py``
  (``iter_pipeline`` already documents this contract).
"""
from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

import numpy as np

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Class-index → PS 26057 class-name mapping
# Must match the order used during training (sonar_debris_yolo26.yaml `names`).
# ---------------------------------------------------------------------------
CLASS_NAMES: dict[int, str] = {
    0: "human_artifact_wreck",
    1: "electrical_cable",
    2: "electronic_hazard",
    3: "plastic_debris",
    4: "metal_drum_scrap",
    5: "biological_geological_exclusion",
}

# Minimum physical size (metres) for a valid detection.
# Candidates smaller than this are treated as noise artefacts.
MIN_WIDTH_M: float = 0.05
MIN_HEIGHT_M: float = 0.05

# Default resolution injected during tiling when no calibration metadata is present.
DEFAULT_RESOLUTION_M_PER_PX: float = 0.1

ModelStatus = Literal["not_loaded", "ready", "unavailable"]


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

@dataclass
class DetectorConfig:
    """All knobs that control detection behaviour.

    All fields have safe defaults so callers only need to override what differs
    from the standard deployment.
    """

    # ---- model source ----
    model_path: Path = field(
        default_factory=lambda: Path(
            os.getenv(
                "AQUASENSE_MODEL_PATH",
                "models_checkpoints/yolo26n_aquasense_marine.pt",
            )
        )
    )
    """Path to YOLO26n weights (.pt) or ONNX export (.onnx).

    Resolved relative to ``backend/`` when not absolute.
    The value can also be set via the ``AQUASENSE_MODEL_PATH`` environment
    variable (useful for CI / Docker deployments without touching code).
    """

    # ---- inference thresholds ----
    # Use None as sentinel so __post_init__ can read env vars at *instantiation*
    # time rather than at module-import time, keeping monkeypatch working in tests.
    confidence_threshold: float | None = None
    """Raw model score threshold. Kept *low* (0.10) so the 10-feature
    verification filter can reject false positives rather than the detector
    itself; this preserves recall at tile level.
    Default: env ``AQUASENSE_CONF_THRESH`` → 0.10."""

    iou_threshold: float | None = None
    """NMS IoU threshold. YOLO26's NMS-free end-to-end inference makes this
    less critical, but the parameter is retained for ONNX fallback which runs
    its own NMS post-processing step.
    Default: env ``AQUASENSE_IOU_THRESH`` → 0.45."""

    # ---- tiling / batching ----
    tile_size: int | None = None
    """Inference resolution; must match the resolution used during training.
    Default: env ``AQUASENSE_TILE_SIZE`` → 640."""

    batch_size: int | None = None
    """Number of tiles to forward in a single model call.  Reduce to 1 on
    Jetson Orin Nano INT8 with <8 GB VRAM headroom.
    Default: env ``AQUASENSE_BATCH_SIZE`` → 4."""

    # ---- device ----
    device: str | None = None
    """``'cpu'``, ``'cuda:0'``, ``'mps'``, or ``'0'`` (Ultralytics shorthand).
    Default: env ``AQUASENSE_DEVICE`` → 'cpu'."""

    # ---- resolution metadata (injected from QC report at call-site) ----
    resolution_m_per_px: float = DEFAULT_RESOLUTION_M_PER_PX

    def __post_init__(self) -> None:
        # Env-var defaults resolved here (not at class-body evaluation time)
        # so that os.environ changes (e.g. monkeypatch in tests) take effect.
        if self.confidence_threshold is None:
            self.confidence_threshold = float(os.getenv("AQUASENSE_CONF_THRESH", "0.10"))
        if self.iou_threshold is None:
            self.iou_threshold = float(os.getenv("AQUASENSE_IOU_THRESH", "0.45"))
        if self.tile_size is None:
            self.tile_size = int(os.getenv("AQUASENSE_TILE_SIZE", "640"))
        if self.batch_size is None:
            self.batch_size = int(os.getenv("AQUASENSE_BATCH_SIZE", "4"))
        if self.device is None:
            self.device = os.getenv("AQUASENSE_DEVICE", "cpu")
        # Resolve relative model paths: check repo root, persistent data dir, or models dir.
        if not self.model_path.is_absolute():
            repo_candidate = (
                Path(__file__).resolve().parent.parent / self.model_path
            ).resolve()
            data_dir = Path(os.getenv("AQUASENSE_DATA_DIR", repo_candidate.parent / "data"))
            data_candidate = (data_dir / self.model_path).resolve()
            models_candidate = (data_dir / "models" / self.model_path.name).resolve()
            if repo_candidate.exists():
                self.model_path = repo_candidate
            elif data_candidate.exists():
                self.model_path = data_candidate
            elif models_candidate.exists():
                self.model_path = models_candidate
            else:
                self.model_path = repo_candidate

    def is_onnx(self) -> bool:
        return self.model_path.suffix.lower() == ".onnx"


# ---------------------------------------------------------------------------
# Raw detection (adapter output before verification)
# ---------------------------------------------------------------------------

@dataclass
class RawDetection:
    """One candidate bounding-box detection returned by the model.

    This is deliberately *minimal*: it carries only what the model emits.
    Geolocation, calibration status, provenance, and segmentation masks are
    added by downstream pipeline stages.
    """
    tile_index: int
    """Index of the tile within the batch this detection came from."""

    class_id: int
    """Detector class index.  Map via ``CLASS_NAMES[class_id]``."""

    classification: str
    """Human-readable class name resolved from ``class_id``."""

    raw_logit: float
    """Raw model confidence score *before* any threshold is applied.
    Required for Platt scaling calibration."""

    confidence_percent: int
    """``int(round(raw_logit * 100))``.  Convenience field."""

    # Normalised bounding box [0, 1] in (cx, cy, w, h) YOLO format.
    box_xywh_norm: tuple[float, float, float, float]
    """Normalised (cx, cy, w, h) in [0, 1] — preserved for debugging."""

    x_norm: float
    """Top-left x normalised to [0, 1]."""
    y_norm: float
    """Top-left y normalised to [0, 1]."""
    width_m: float
    """Physical width in metres (computed from tile resolution)."""
    height_m: float
    """Physical height in metres (computed from tile resolution)."""

    seg_mask: dict | None = None
    """Polygon or RLE segmentation mask when the segmentation head is active;
    ``None`` for the box-only head or when ONNX export omits mask outputs."""

    model_version: str = ""
    """Populated by the adapter from the loaded weights metadata."""


# ---------------------------------------------------------------------------
# Adapter
# ---------------------------------------------------------------------------

class Yolo26Adapter:
    """Swappable detector backend for AquaSense.

    Lifecycle
    ---------
    1. Instantiate with a ``DetectorConfig`` — safe even without weights.
    2. Call ``load()`` once (idempotent).
    3. Call ``run_batch(tiles)`` for inference.

    Thread / async safety
    ---------------------
    The adapter is *not* thread-safe for concurrent ``load()`` calls.
    Acquire a lock or call ``load()`` once at startup before forking workers.
    """

    def __init__(self, config: DetectorConfig | None = None) -> None:
        self.config: DetectorConfig = config or DetectorConfig()
        self.status: ModelStatus = "not_loaded"
        self._model = None          # Ultralytics YOLO object or ONNX InferenceSession
        self._model_version: str = "not_loaded"

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @property
    def is_ready(self) -> bool:
        return self.status == "ready"

    def load(self) -> "Yolo26Adapter":
        """Load model weights.  Idempotent — safe to call multiple times.

        Raises
        ------
        RuntimeError
            If the weights file exists but is corrupt or incompatible.
        """
        if self.status == "ready":
            return self

        cfg = self.config

        if not cfg.model_path.exists():
            logger.warning(
                "YOLO26 weights not found at '%s'. "
                "The adapter will return empty detection lists. "
                "Run training or copy weights to this path to enable ML inference.",
                cfg.model_path,
            )
            self.status = "unavailable"
            self._model_version = f"not_installed ({cfg.model_path.name})"
            return self

        try:
            if cfg.is_onnx():
                self._load_onnx(cfg)
            else:
                self._load_ultralytics(cfg)
            self.status = "ready"
            logger.info(
                "YOLO26 adapter ready — backend=%s device=%s conf=%.2f iou=%.2f batch=%d",
                "onnx" if cfg.is_onnx() else "ultralytics",
                cfg.device,
                cfg.confidence_threshold,
                cfg.iou_threshold,
                cfg.batch_size,
            )
        except Exception as exc:
            logger.error("Failed to load YOLO26 weights: %s", exc, exc_info=True)
            self.status = "unavailable"
            self._model_version = f"load_error ({type(exc).__name__})"
            raise RuntimeError(
                f"YOLO26 weights at '{cfg.model_path}' could not be loaded: {exc}"
            ) from exc

        return self

    def run_batch(
        self,
        tiles: list[np.ndarray],
        resolution_m_per_px: float | None = None,
    ) -> list[list[RawDetection]]:
        """Run inference on a batch of tiles.

        Parameters
        ----------
        tiles:
            List of HWC uint8 NumPy arrays, each ``(tile_size, tile_size, 3)``.
            Accepts single-channel arrays — they are broadcast to 3 channels.
        resolution_m_per_px:
            Override the config value for physical size calculation.  Pass the
            ``resolution_meters_per_pixel`` field from the QC report.

        Returns
        -------
        ``list[list[RawDetection]]`` — one inner list per input tile,
        preserving order.  Empty inner lists mean *no detections* (not an error).
        When the model is unavailable every inner list is empty.
        """
        if not tiles:
            return []

        res = resolution_m_per_px or self.config.resolution_m_per_px

        if self.status == "not_loaded":
            self.load()

        if not self.is_ready:
            logger.debug(
                "Detector unavailable — returning empty results for %d tiles.", len(tiles)
            )
            return [[] for _ in tiles]

        # Normalise to 3-channel RGB
        prepared = [self._ensure_rgb(tile) for tile in tiles]

        results_per_tile: list[list[RawDetection]] = [[] for _ in tiles]

        # Process in sub-batches to respect VRAM limits
        for batch_start in range(0, len(prepared), self.config.batch_size):
            batch = prepared[batch_start : batch_start + self.config.batch_size]
            batch_indices = list(range(batch_start, batch_start + len(batch)))

            try:
                if self.config.is_onnx():
                    raw_outputs = self._infer_onnx(batch)
                else:
                    raw_outputs = self._infer_ultralytics(batch)
            except Exception as exc:
                logger.error(
                    "Inference error on batch starting at tile %d: %s",
                    batch_start, exc, exc_info=True,
                )
                continue

            for tile_result, tile_idx in zip(raw_outputs, batch_indices):
                for raw in tile_result:
                    raw.tile_index = tile_idx
                    raw.model_version = self._model_version
                    # Convert normalised w/h → physical metres
                    raw.width_m  = max(raw.box_xywh_norm[2] * self.config.tile_size * res, MIN_WIDTH_M)
                    raw.height_m = max(raw.box_xywh_norm[3] * self.config.tile_size * res, MIN_HEIGHT_M)
                    results_per_tile[tile_idx].append(raw)

        return results_per_tile

    # ------------------------------------------------------------------
    # Loader helpers
    # ------------------------------------------------------------------

    def _load_ultralytics(self, cfg: DetectorConfig) -> None:
        try:
            from ultralytics import YOLO  # type: ignore[import]
        except ImportError as exc:
            raise RuntimeError(
                "The 'ultralytics' package is not installed. "
                "Install it with: pip install ultralytics>=8.3"
            ) from exc

        self._model = YOLO(str(cfg.model_path))
        # Warm-up pass to surface weight incompatibility immediately
        dummy = np.zeros((cfg.tile_size, cfg.tile_size, 3), dtype=np.uint8)
        self._model.predict(
            source=[dummy],
            conf=cfg.confidence_threshold,
            iou=cfg.iou_threshold,
            device=cfg.device,
            verbose=False,
        )
        self._model_version = f"yolo26n-ultralytics ({cfg.model_path.name})"

    def _load_onnx(self, cfg: DetectorConfig) -> None:
        try:
            import onnxruntime as ort  # type: ignore[import]
        except ImportError as exc:
            raise RuntimeError(
                "The 'onnxruntime' package is not installed. "
                "Install it with: pip install onnxruntime"
            ) from exc

        providers = ["CUDAExecutionProvider", "CPUExecutionProvider"]
        self._model = ort.InferenceSession(str(cfg.model_path), providers=providers)
        self._model_version = f"yolo26n-onnx ({cfg.model_path.name})"

    # ------------------------------------------------------------------
    # Inference helpers
    # ------------------------------------------------------------------

    def _infer_ultralytics(self, batch: list[np.ndarray]) -> list[list[RawDetection]]:
        cfg = self.config
        results = self._model.predict(
            source=batch,
            conf=cfg.confidence_threshold,
            iou=cfg.iou_threshold,
            device=cfg.device,
            imgsz=cfg.tile_size,
            verbose=False,
            stream=False,
        )
        output: list[list[RawDetection]] = []
        for result in results:
            detections: list[RawDetection] = []
            if result.boxes is not None:
                boxes_np   = result.boxes.xywhn.cpu().numpy()   # (N, 4) cx,cy,w,h normalised
                confs_np   = result.boxes.conf.cpu().numpy()    # (N,)
                classes_np = result.boxes.cls.cpu().numpy()     # (N,)

                seg_masks: list[dict | None] = [None] * len(boxes_np)
                if result.masks is not None:
                    for i, poly_xy in enumerate(result.masks.xy):
                        if poly_xy is not None and len(poly_xy):
                            seg_masks[i] = {"type": "polygon", "data": poly_xy.tolist()}

                for box, conf, cls_id, mask in zip(boxes_np, confs_np, classes_np, seg_masks):
                    class_idx  = int(cls_id)
                    raw_logit  = float(conf)
                    cx, cy, w, h = float(box[0]), float(box[1]), float(box[2]), float(box[3])
                    x_norm = max(cx - w / 2, 0.0)
                    y_norm = max(cy - h / 2, 0.0)
                    detections.append(
                        RawDetection(
                            tile_index=0,   # overwritten by caller
                            class_id=class_idx,
                            classification=CLASS_NAMES.get(class_idx, f"unknown_{class_idx}"),
                            raw_logit=raw_logit,
                            confidence_percent=int(round(raw_logit * 100)),
                            box_xywh_norm=(cx, cy, w, h),
                            x_norm=x_norm,
                            y_norm=y_norm,
                            width_m=0.0,    # filled in by run_batch
                            height_m=0.0,
                            seg_mask=mask,
                        )
                    )
            output.append(detections)
        return output

    def _infer_onnx(self, batch: list[np.ndarray]) -> list[list[RawDetection]]:
        """ONNX Runtime inference path (Jetson CPU / Apple MPS demo fallback).

        Expected output schema: ``output0`` shape ``[B, 4+C, N]`` where
        columns are ``(cx, cy, w, h, cls0_score, cls1_score, ...)``.
        """
        cfg = self.config
        tensor = np.stack(
            [t.transpose(2, 0, 1).astype(np.float32) / 255.0 for t in batch],
            axis=0,
        )

        input_name = self._model.get_inputs()[0].name
        raw_output  = self._model.run(None, {input_name: tensor})[0]   # (B, 4+C, N)

        output: list[list[RawDetection]] = []
        for b_idx in range(raw_output.shape[0]):
            preds    = raw_output[b_idx]           # (4+C, N)
            boxes    = preds[:4, :].T              # (N, 4)
            scores   = preds[4:, :].T              # (N, C)
            class_ids = scores.argmax(axis=1)
            confs     = scores[np.arange(len(scores)), class_ids]

            keep = confs >= cfg.confidence_threshold
            detections: list[RawDetection] = []
            for box, conf, cls_id in zip(boxes[keep], confs[keep], class_ids[keep]):
                cx, cy, w, h = float(box[0]), float(box[1]), float(box[2]), float(box[3])
                x_norm = max(cx - w / 2, 0.0)
                y_norm = max(cy - h / 2, 0.0)
                class_idx = int(cls_id)
                detections.append(
                    RawDetection(
                        tile_index=0,
                        class_id=class_idx,
                        classification=CLASS_NAMES.get(class_idx, f"unknown_{class_idx}"),
                        raw_logit=float(conf),
                        confidence_percent=int(round(float(conf) * 100)),
                        box_xywh_norm=(cx, cy, w, h),
                        x_norm=x_norm,
                        y_norm=y_norm,
                        width_m=0.0,
                        height_m=0.0,
                        seg_mask=None,
                    )
                )
            output.append(detections)
        return output

    # ------------------------------------------------------------------
    # Static helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _ensure_rgb(tile: np.ndarray) -> np.ndarray:
        """Broadcast a single-channel or 4-channel array to 3-channel RGB."""
        if tile.ndim == 2:
            return np.stack([tile, tile, tile], axis=-1)
        if tile.shape[2] == 1:
            return np.concatenate([tile, tile, tile], axis=-1)
        if tile.shape[2] == 4:
            return tile[:, :, :3]
        return tile

    def describe(self) -> dict:
        """Return a human-readable status dict — suitable for the ``/health`` endpoint."""
        cfg = self.config
        return {
            "status": self.status,
            "model_version": self._model_version,
            "model_path": str(cfg.model_path),
            "confidence_threshold": cfg.confidence_threshold,
            "iou_threshold": cfg.iou_threshold,
            "tile_size": cfg.tile_size,
            "batch_size": cfg.batch_size,
            "device": cfg.device,
            "backend": "onnx" if cfg.is_onnx() else "ultralytics",
        }


# ---------------------------------------------------------------------------
# Module-level singleton (lazy-initialised, one load per process)
# ---------------------------------------------------------------------------

_default_adapter: Yolo26Adapter | None = None


def get_adapter() -> Yolo26Adapter:
    """Return the module-level singleton adapter, loading weights on first access.

    Recommended usage in pipeline.py::

        from .detector import get_adapter

        adapter = get_adapter()
        if adapter.is_ready:
            raw_detections = adapter.run_batch(tiles, resolution_m_per_px=0.1)
        else:
            # Fall back to heuristic baseline
            ...

    The singleton ensures weights are loaded exactly once per process.
    """
    global _default_adapter
    if _default_adapter is None:
        _default_adapter = Yolo26Adapter()
        try:
            _default_adapter.load()
        except RuntimeError:
            pass   # status already set to "unavailable"; callers check is_ready
    return _default_adapter
