"""Regression tests for the proven CNS-R002S-S Quick Food cursor."""

from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODULE = ROOT / "custom_components" / "ha_vesync_bt" / "food_cursor.py"

spec = importlib.util.spec_from_file_location("_food_cursor_test", MODULE)
assert spec is not None and spec.loader is not None
food_cursor = importlib.util.module_from_spec(spec)
spec.loader.exec_module(food_cursor)

advance = food_cursor.advance_quick_food_cursor


def test_right_cycle_includes_none_boundaries() -> None:
    """v40 proved <none> -> 1 -> 2 -> 3 -> 4 -> 5 -> <none>."""
    index = None
    observed = []
    for _ in range(6):
        index = advance(index, 5, "right")
        observed.append(index)

    assert observed == [0, 1, 2, 3, 4, None]


def test_left_cycle_includes_none_boundaries() -> None:
    """v40 proved <none> -> 5 -> 4 -> 3 -> 2 -> 1 -> <none>."""
    index = None
    observed = []
    for _ in range(6):
        index = advance(index, 5, "left")
        observed.append(index)

    assert observed == [4, 3, 2, 1, 0, None]


def test_empty_food_list_stays_none() -> None:
    assert advance(None, 0, "right") is None
    assert advance(None, 0, "left") is None


def test_invalid_direction_and_index_are_rejected() -> None:
    import pytest

    with pytest.raises(ValueError):
        advance(None, 5, "set")
    with pytest.raises(ValueError):
        advance(5, 5, "right")
