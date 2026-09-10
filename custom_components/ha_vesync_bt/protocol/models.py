"""Shared VeSync device models."""

from __future__ import annotations

from dataclasses import dataclass, field

from .nutrition import Nutrition


@dataclass(frozen=True, slots=True)
class QuickFood:
    """One Quick Food entry."""

    sequence: int
    name: str
    daily_food_weight_g: float
    nutrition: Nutrition


@dataclass(frozen=True, slots=True)
class ScaleState:
    """Current in-memory CNS-R002S-S state."""

    address: str
    connected: bool = False

    measurement: float | None = None
    unit: str | None = None
    stable: bool | None = None
    tare: bool | None = None
    object_present: bool | None = None
    low_voltage: bool | None = None
    overload: bool | None = None
    charging: bool | None = None
    battery_percent: int | None = None

    current_unit: str | None = None
    enabled_units: tuple[str, ...] = ()
    language: str | None = None
    brightness: str | None = None
    brightness_raw: int | None = None
    standby_timeout: int | None = None

    firmware: str | None = None
    quick_foods: tuple[QuickFood, ...] = ()
    selected_food: QuickFood | None = None

    extra: dict[str, object] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class DeviceButtonEvent:
    """A physical control event."""

    button: str
