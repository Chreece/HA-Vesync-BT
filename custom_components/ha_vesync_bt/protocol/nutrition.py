"""Nutrition payload encoding used by VeSync nutrition scales."""

from __future__ import annotations

from dataclasses import asdict, dataclass

NUTRIENT_NAMES = (
    "calories_kcal",
    "protein_g",
    "total_fat_g",
    "saturated_fat_g",
    "trans_fat_g",
    "total_carbs_g",
    "dietary_fiber_g",
    "sugars_g",
    "cholesterol_mg",
    "sodium_mg",
    "iron_mg",
)


@dataclass(frozen=True, slots=True)
class Nutrition:
    """Eleven nutrition values used by the scale."""

    calories_kcal: float = 0.0
    protein_g: float = 0.0
    total_fat_g: float = 0.0
    saturated_fat_g: float = 0.0
    trans_fat_g: float = 0.0
    total_carbs_g: float = 0.0
    dietary_fiber_g: float = 0.0
    sugars_g: float = 0.0
    cholesterol_mg: float = 0.0
    sodium_mg: float = 0.0
    iron_mg: float = 0.0

    def as_dict(self) -> dict[str, float]:
        """Return a serializable mapping."""
        return asdict(self)


def _u24le(value: int) -> bytes:
    if not 0 <= value <= 0xFFFFFF:
        raise ValueError(f"value {value} does not fit in uint24")
    return bytes((value & 0xFF, (value >> 8) & 0xFF, (value >> 16) & 0xFF))


def _read_u24le(data: bytes) -> int:
    if len(data) != 3:
        raise ValueError("uint24 requires exactly three bytes")
    return data[0] | (data[1] << 8) | (data[2] << 16)


def _tenths(value: float) -> int:
    return max(0, int(round(float(value) * 10.0)))


def encode_nutrition(value: Nutrition) -> bytes:
    """Encode the fixed 33-byte scale nutrition block."""
    out = bytearray()
    mapping = value.as_dict()
    for name in NUTRIENT_NAMES:
        out += _u24le(_tenths(mapping[name]))
    return bytes(out)


def decode_nutrition(data: bytes) -> Nutrition:
    """Decode the fixed 33-byte scale nutrition block."""
    if len(data) != 33:
        raise ValueError(f"nutrition block must be 33 bytes, got {len(data)}")

    values = [
        _read_u24le(data[index : index + 3]) / 10.0
        for index in range(0, 33, 3)
    ]
    return Nutrition(**dict(zip(NUTRIENT_NAMES, values, strict=True)))
