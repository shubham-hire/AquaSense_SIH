"""Canonical class order for the production AquaSense YOLO checkpoint.

Class IDs are part of the model contract: changing their order requires a new
checkpoint and a matching training dataset.  Import this module rather than
redeclaring the mapping in inference, preflight, or training code.
"""
from __future__ import annotations


MODEL_CLASS_NAMES: tuple[str, ...] = (
    "shipwreck",
    "submarine_pipeline",
    "cylinder",
    "ghost_net",
    "ghost_pot_trap",
    "plastic_debris",
    "metal_debris",
)

# Ultralytics exposes checkpoint names as an integer-keyed dictionary.
CLASS_NAMES: dict[int, str] = dict(enumerate(MODEL_CLASS_NAMES))

