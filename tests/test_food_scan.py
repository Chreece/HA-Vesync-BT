"""Tests for AI food-scan normalization."""

from __future__ import annotations

import importlib.util
from pathlib import Path
import sys
import types

ROOT = Path(__file__).resolve().parents[1]
COMPONENT = ROOT / "custom_components" / "ha_vesync_bt"
PROTOCOL = COMPONENT / "protocol"
PACKAGE = "_food_scan_testpkg"

root_pkg = types.ModuleType(PACKAGE)
root_pkg.__path__ = [str(COMPONENT)]
sys.modules[PACKAGE] = root_pkg

protocol_pkg = types.ModuleType(f"{PACKAGE}.protocol")
protocol_pkg.__path__ = [str(PROTOCOL)]
sys.modules[f"{PACKAGE}.protocol"] = protocol_pkg


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


_load(f"{PACKAGE}.protocol.nutrition", PROTOCOL / "nutrition.py")
scan = _load(f"{PACKAGE}.food_scan", COMPONENT / "food_scan.py")


def test_parse_food_scan_normalizes_values() -> None:
    """AI values are bounded and serialized for the 100 g scale contract."""
    result = scan.parse_food_scan_data(
        {
            "identified": "yes",
            "name": "Organic Greek Yogurt Extra Long Name",
            "confidence": 117,
            "basis": "nutrition_label",
            "warning": "",
            "calories_kcal": 73.2,
            "protein_g": 9.8,
            "total_fat_g": -1,
            "sodium_mg": "42.5",
        },
        camera_entity="camera.kitchen",
        ai_task_entity="ai_task.vision",
        scanned_at="2026-09-11T20:00:00+00:00",
    )

    assert result.identified is True
    assert result.name == "Organic Greek Yogurt"[:20]
    assert result.confidence == 100.0
    assert result.basis == "nutrition_label"
    assert result.nutrition.calories_kcal == 73.2
    assert result.nutrition.protein_g == 9.8
    assert result.nutrition.total_fat_g == 0.0
    assert result.nutrition.sodium_mg == 42.5
    assert result.as_dict()["reference_weight_g"] == 100.0


def test_parse_food_scan_unknown_is_safe() -> None:
    """Missing or invalid AI fields stay reviewable and are never negative."""
    result = scan.parse_food_scan_data(
        {
            "identified": "no",
            "name": "",
            "confidence": "not-a-number",
            "basis": "made_up",
            "warning": "Cannot identify the object",
            "iron_mg": float("nan"),
        },
        camera_entity="camera.kitchen",
        ai_task_entity=None,
        scanned_at="2026-09-11T20:00:00+00:00",
    )

    assert result.identified is False
    assert result.name == "Unknown"
    assert result.confidence == 0.0
    assert result.basis == "unknown"
    assert result.nutrition.iron_mg == 0.0
