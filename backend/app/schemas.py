from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator


class BoundingBox(BaseModel):
    x: float = Field(ge=0)
    y: float = Field(ge=0)
    width_m: float = Field(gt=0)
    height_m: float = Field(gt=0)


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
