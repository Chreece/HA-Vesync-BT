"""Regression tests for AI food-scanner language semantics."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
AI_SCANNER = (
    ROOT / "custom_components" / "ha_vesync_bt" / "ai_scanner.py"
).read_text(encoding="utf-8")


def test_food_name_is_always_requested_in_english() -> None:
    """The canonical scale food name must not follow the dashboard locale."""
    assert "The `name` field MUST ALWAYS be an ENGLISH food/product name" in AI_SCANNER
    assert "Always use English regardless of the Home Assistant UI language" in AI_SCANNER
    assert "Never localize this field" in AI_SCANNER
    assert "Return the food name in Home Assistant language" not in AI_SCANNER


def test_warning_follows_home_assistant_ui_language() -> None:
    """User-facing uncertainty text must follow the current HA UI language."""
    assert "The user-facing `warning` field MUST be written in Home Assistant UI language" in AI_SCANNER
    assert "_structure(hass.config.language)" in AI_SCANNER
    assert "_vol_structure(hass.config.language)" in AI_SCANNER
    assert "Write it in Home Assistant UI language" in AI_SCANNER


def test_machine_basis_values_are_not_localized() -> None:
    """Stable protocol-facing basis values remain language-independent."""
    assert "Machine fields such as `basis` keep their fixed schema values" in AI_SCANNER
    for value in ("nutrition_label", "known_food", "visual_estimate", "unknown"):
        assert value in AI_SCANNER
