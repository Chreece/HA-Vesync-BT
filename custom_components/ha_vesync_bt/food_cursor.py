"""Quick Food cursor behavior proven on CNS-R002S-S hardware."""

from __future__ import annotations


def advance_quick_food_cursor(
    current_index: int | None,
    food_count: int,
    direction: str,
) -> int | None:
    """Advance the physical Quick Food cursor for one LEFT/RIGHT press.

    The scale has a real no-food slot at both ends of the ordered Quick Food
    list. From that slot RIGHT enters the first food and LEFT enters the last.
    Moving past either end returns to the no-food slot.
    """
    if food_count <= 0:
        return None

    if current_index is not None and not 0 <= current_index < food_count:
        raise ValueError("Quick Food cursor index is out of range")

    if direction == "right":
        if current_index is None:
            return 0
        return current_index + 1 if current_index + 1 < food_count else None

    if direction == "left":
        if current_index is None:
            return food_count - 1
        return current_index - 1 if current_index > 0 else None

    raise ValueError(f"Unsupported Quick Food cursor direction: {direction}")
