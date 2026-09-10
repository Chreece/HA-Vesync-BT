"""Sensor entities for HA-VeSync-BT."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from homeassistant.components.sensor import (
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE, EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import HaVesyncCoordinator
from .entity import HaVesyncEntity


@dataclass(frozen=True, kw_only=True)
class HaVesyncSensorDescription(SensorEntityDescription):
    """Describe a HA-VeSync-BT sensor."""

    value_fn: Any
    attrs_fn: Any | None = None


SENSORS = (
    HaVesyncSensorDescription(
        key="measurement",
        translation_key="measurement",
        value_fn=lambda state: state.measurement,
    ),
    HaVesyncSensorDescription(
        key="battery",
        translation_key="battery",
        native_unit_of_measurement=PERCENTAGE,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda state: state.battery_percent,
    ),
    HaVesyncSensorDescription(
        key="quick_food_count",
        translation_key="quick_food_count",
        value_fn=lambda state: len(state.quick_foods),
        attrs_fn=lambda state: {
            "foods": [
                {"sequence": food.sequence, "name": food.name}
                for food in state.quick_foods
            ]
        },
    ),
    HaVesyncSensorDescription(
        key="selected_food",
        translation_key="selected_food",
        value_fn=lambda state: (
            state.selected_food.name if state.selected_food is not None else None
        ),
        attrs_fn=lambda state: (
            {
                "daily_food_weight_g": state.selected_food.daily_food_weight_g,
                **state.selected_food.nutrition.as_dict(),
            }
            if state.selected_food is not None
            else {}
        ),
    ),
    HaVesyncSensorDescription(
        key="enabled_units",
        translation_key="enabled_units",
        value_fn=lambda state: len(state.enabled_units),
        attrs_fn=lambda state: {"units": list(state.enabled_units)},
    ),
    HaVesyncSensorDescription(
        key="firmware",
        translation_key="firmware",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda state: state.firmware,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up HA-VeSync-BT sensors."""
    coordinator: HaVesyncCoordinator = entry.runtime_data
    async_add_entities(
        HaVesyncSensor(coordinator, description)
        for description in SENSORS
    )


class HaVesyncSensor(HaVesyncEntity, SensorEntity):
    """One HA-VeSync-BT sensor."""

    entity_description: HaVesyncSensorDescription

    def __init__(
        self,
        coordinator: HaVesyncCoordinator,
        description: HaVesyncSensorDescription,
    ) -> None:
        super().__init__(coordinator, description.key)
        self.entity_description = description

    @property
    def native_value(self) -> Any:
        """Return sensor value."""
        return self.entity_description.value_fn(self.coordinator.data)

    @property
    def native_unit_of_measurement(self) -> str | None:
        """Return dynamic measurement unit when applicable."""
        if self.entity_description.key == "measurement":
            return self.coordinator.data.unit
        return self.entity_description.native_unit_of_measurement

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return compact attributes."""
        if self.entity_description.attrs_fn is None:
            return None
        return self.entity_description.attrs_fn(self.coordinator.data)
