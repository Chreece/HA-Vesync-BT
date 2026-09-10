"""Binary sensor entities for HA-VeSync-BT."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import HaVesyncCoordinator
from .entity import HaVesyncEntity


@dataclass(frozen=True, kw_only=True)
class HaVesyncBinaryDescription(BinarySensorEntityDescription):
    """Describe a HA-VeSync-BT binary sensor."""

    value_fn: Any
    always_available: bool = False


BINARY_SENSORS = (
    HaVesyncBinaryDescription(
        key="connected",
        translation_key="connected",
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda state: state.connected,
        always_available=True,
    ),
    HaVesyncBinaryDescription(
        key="stable",
        translation_key="stable",
        value_fn=lambda state: state.stable,
    ),
    HaVesyncBinaryDescription(
        key="tare",
        translation_key="tare",
        value_fn=lambda state: state.tare,
    ),
    HaVesyncBinaryDescription(
        key="object_present",
        translation_key="object_present",
        value_fn=lambda state: state.object_present,
    ),
    HaVesyncBinaryDescription(
        key="low_battery",
        translation_key="low_battery",
        device_class=BinarySensorDeviceClass.BATTERY,
        value_fn=lambda state: state.low_voltage,
    ),
    HaVesyncBinaryDescription(
        key="overload",
        translation_key="overload",
        device_class=BinarySensorDeviceClass.PROBLEM,
        value_fn=lambda state: state.overload,
    ),
    HaVesyncBinaryDescription(
        key="charging",
        translation_key="charging",
        device_class=BinarySensorDeviceClass.BATTERY_CHARGING,
        value_fn=lambda state: state.charging,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up binary sensors."""
    coordinator: HaVesyncCoordinator = entry.runtime_data
    async_add_entities(
        HaVesyncBinarySensor(coordinator, description)
        for description in BINARY_SENSORS
    )


class HaVesyncBinarySensor(HaVesyncEntity, BinarySensorEntity):
    """One HA-VeSync-BT binary sensor."""

    entity_description: HaVesyncBinaryDescription

    def __init__(
        self,
        coordinator: HaVesyncCoordinator,
        description: HaVesyncBinaryDescription,
    ) -> None:
        super().__init__(coordinator, description.key)
        self.entity_description = description

    @property
    def is_on(self) -> bool | None:
        """Return state."""
        value = self.entity_description.value_fn(self.coordinator.data)
        return None if value is None else bool(value)

    @property
    def available(self) -> bool:
        """Return availability."""
        if self.entity_description.always_available:
            return True
        return super().available
