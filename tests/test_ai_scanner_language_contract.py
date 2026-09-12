"""Regression tests for AI food-scanner language and confidence semantics."""

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


def test_confidence_is_requested_as_percent_not_probability() -> None:
    """Providers get an explicit 0..100 contract instead of an ambiguous number."""
    assert "Confidence contract:" in AI_SCANNER
    assert "MUST be a percentage on the 0..100 scale" in AI_SCANNER
    assert "NOT a probability on" in AI_SCANNER
    assert "Return 95 for 95 percent confidence" in AI_SCANNER
    assert "NEVER return 0.95 to mean 95 percent" in AI_SCANNER
    assert "never use 1 to mean 100 percent" in AI_SCANNER
