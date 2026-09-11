"""AI food-scan result model and validation."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Mapping

from .protocol.nutrition import NUTRIENT_NAMES, Nutrition

SCAN_BASES = (
    "nutrition_label",
    "known_food",
    "visual_estimate",
    "unknown",
)


def _number(value: Any) -> float:
    """Return one non-negative finite float."""
    try:
        result = float(value)
    except (TypeError, ValueError):
        return 0.0
    if result != result or result in (float("inf"), float("-inf")):
        return 0.0
    return max(0.0, result)


@dataclass(frozen=True, slots=True)
class FoodScanResult:
    """One AI food-recognition result normalized for the scale."""

    identified: bool
    name: str
    confidence: float
    basis: str
    warning: str
    nutrition: Nutrition
    camera_entity: str
    ai_task_entity: str | None
    scanned_at: str

    def as_dict(self) -> dict[str, Any]:
        """Return a serializable service/sensor representation."""
        return {
            "identified": self.identified,
            "name": self.name,
            "confidence": self.confidence,
            "basis": self.basis,
            "warning": self.warning,
            "reference_weight_g": 100.0,
            "camera_entity": self.camera_entity,
            "ai_task_entity": self.ai_task_entity,
            "scanned_at": self.scanned_at,
            **self.nutrition.as_dict(),
        }


def parse_food_scan_data(
    data: Mapping[str, Any],
    *,
    camera_entity: str,
    ai_task_entity: str | None,
    scanned_at: str | None = None,
) -> FoodScanResult:
    """Validate AI structured output and normalize it for a 100 g reference."""
    identified = str(data.get("identified", "no")).strip().lower() == "yes"

    name = str(data.get("name") or "").strip()
    # The scale's food-name field is limited to 20 characters by the native client.
    name = name[:20]
    if not name:
        name = "Unknown"
        identified = False

    confidence = min(100.0, _number(data.get("confidence", 0.0)))

    basis = str(data.get("basis") or "unknown").strip().lower()
    if basis not in SCAN_BASES:
        basis = "unknown"

    warning = str(data.get("warning") or "").strip()[:500]

    nutrition = Nutrition(
        **{
            field: _number(data.get(field, 0.0))
            for field in NUTRIENT_NAMES
        }
    )

    return FoodScanResult(
        identified=identified,
        name=name,
        confidence=confidence,
        basis=basis,
        warning=warning,
        nutrition=nutrition,
        camera_entity=camera_entity,
        ai_task_entity=ai_task_entity,
        scanned_at=scanned_at
        or datetime.now(timezone.utc).isoformat(timespec="seconds"),
    )
