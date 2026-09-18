from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator


class ImageBox(BaseModel):
    """Top-left normalized box used to render a detection on its source image."""
    left: float = Field(ge=0, le=1)
    top: float = Field(ge=0, le=1)
    width: float = Field(ge=0, le=1)
    height: float = Field(ge=0, le=1)


class BoundingBox(BaseModel):
    """Detection geometry.

    ``x`` and ``y`` are the normalized centre of the detection and the metre
    fields are measurement data.  ``image_box`` is deliberately separate so a
    client never has to mistake a physical measurement for screen pixels.
    """
    x: float = Field(ge=0)
    y: float = Field(ge=0)
    width_m: float = Field(gt=0)
    height_m: float = Field(gt=0)
    image_box: ImageBox | None = None


class Position(BaseModel):
    latitude: float | None = None
    longitude: float | None = None
    position_source: Literal["GPS_FIX", "UNAVAILABLE"]
    refusal_reason: str | None = None

    @field_validator("longitude")
    @classmethod
    def longitude_is_valid(cls, value: float | None) -> float | None:
        if value is not None and not -180 <= value <= 180:
            raise ValueError("longitude must be in [-180, 180]")
        return value

    @model_validator(mode="after")
    def enforce_navigation_refusal(self) -> "Position":
        """Coordinates can only leave the service when a GPS fix is declared."""
        has_any_coordinate = self.latitude is not None or self.longitude is not None
        if self.position_source == "UNAVAILABLE" and has_any_coordinate:
            raise ValueError("unavailable navigation must not include coordinates")
        if self.position_source == "GPS_FIX" and (self.latitude is None or self.longitude is None):
            raise ValueError("GPS_FIX requires both latitude and longitude")
        if self.position_source == "UNAVAILABLE" and not self.refusal_reason:
            raise ValueError("unavailable navigation requires a refusal reason")
        return self


# ---------------------------------------------------------------------------
# Operator Review
# ---------------------------------------------------------------------------

ReviewOutcome = Literal["CONFIRMED", "REJECTED_FP", "CORRECTED"]


class ReviewDecision(BaseModel):
    """Operator review attached to a single detection contact.

    - CONFIRMED     — operator agrees with the model's classification.
    - REJECTED_FP   — operator marks the detection as a false positive.
    - CORRECTED     — operator provides the true class via corrected_class.

    nav_trustworthy: operator attests that the GPS fix for this contact is
    valid.  This is an additional flag; it does NOT override the structural
    Position refusal invariant in the backend.
    """

    outcome: ReviewOutcome
    corrected_class: str | None = Field(
        default=None,
        description="Required when outcome == CORRECTED; must be a known class key.",
    )
    note: str | None = Field(
        default=None,
        max_length=1000,
        description="Free-text operator note (max 1000 characters).",
    )
    nav_trustworthy: bool = Field(
        default=True,
        description="Operator attestation that the GPS location is trustworthy.",
    )
    reviewed_by: str = Field(
        default="operator",
        max_length=128,
        description="Operator identifier (free-text, no auth required yet).",
    )
    reviewed_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
    )

    @model_validator(mode="after")
    def corrected_class_required_when_corrected(self) -> "ReviewDecision":
        if self.outcome == "CORRECTED" and not self.corrected_class:
            raise ValueError("corrected_class is required when outcome is CORRECTED")
        if self.outcome != "CORRECTED" and self.corrected_class is not None:
            raise ValueError("corrected_class must be null unless outcome is CORRECTED")
        return self


class Detection(BaseModel):
    id: str
    survey_id: str
    classification: str
    confidence_percent: int = Field(ge=0, le=100)
    bounding_box: BoundingBox
    segmentation_mask: dict | None = None
    position: Position
    calibrated: bool
    low_data_quality: bool
    motion_uncorrected: bool
    model_version: str
    dsp_applied: bool
    ping_timestamp: datetime
    ping_index: int = Field(ge=0)
    threat_level: Literal["CRITICAL", "HIGH", "MEDIUM", "LOW"]
    verification_features: dict[str, float | bool]
    feature_weights: dict[str, float]
    provenance: dict[str, str | int | float | bool | None]
    # Optional — populated after the operator reviews the contact.
    review: ReviewDecision | None = None


class QcReport(BaseModel):
    survey_id: str
    file_name: str
    format: Literal["XTF", "JSF", "SL2", "GEOTIFF", "IMAGE"]
    file_size_bytes: int = Field(ge=0)
    ping_count: int = Field(ge=0)
    dynamic_range_db: float = Field(ge=0)
    speckle_index: float = Field(ge=0)
    dropout_ratio_percent: float = Field(ge=0, le=100)
    motion_artifact_rows: list[int]
    resolution_meters_per_pixel: float = Field(gt=0)
    status: Literal["PASS", "WARNING", "CORRUPTED"]
    recommendations: list[str]
