from pathlib import Path

import yaml

from app.detector import CLASS_NAMES as DETECTOR_CLASSES
from app.pipeline import BEST_PT_CLASS_NAMES
from app.preflight import EXPECTED_CLASSES
from app.taxonomy import CLASS_NAMES, MODEL_CLASS_NAMES


def test_runtime_class_maps_share_one_canonical_mapping():
    assert DETECTOR_CLASSES is CLASS_NAMES
    assert BEST_PT_CLASS_NAMES is CLASS_NAMES
    assert EXPECTED_CLASSES is CLASS_NAMES
    assert CLASS_NAMES == dict(enumerate(MODEL_CLASS_NAMES))


def test_training_yaml_matches_the_production_class_order():
    config_path = Path(__file__).resolve().parents[2] / "configs" / "sonar_debris_yolo26.yaml"
    config = yaml.safe_load(config_path.read_text())

    assert config["nc"] == len(MODEL_CLASS_NAMES)
    assert config["names"] == CLASS_NAMES
