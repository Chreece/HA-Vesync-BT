"""Physical-control event entity for HA-VeSync-BT."""

from __future__ import annotations

from homeassistant.components.event import (
    ButtonEventType,
    EventDeviceClass,
    EventEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import HaVesyncCoordinator
from .entity import HaVesyncEntity
from .protocol.models import DeviceButtonEvent


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up physical-control event entity."""
    coordinator: HaVesyncCoordinator = entry.runtime_data
    async_add_entities([HaVesyncControlsEvent(coordinator)])


class HaVesyncControlsEvent(HaVesyncEntity, EventEntity):
    """Physical scale controls."""

    _attr_translation_key = "physical_controls"
    _attr_device_class = EventDeviceClass.BUTTON
    _attr_event_types = [ButtonEventType.PRESS_END]

    def __init__(self, coordinator: HaVesyncCoordinator) -> None:
        super().__init__(coordinator, "physical_controls")

    async def async_added_to_hass(self) -> None:
        """Subscribe to protocol events."""
        await super().async_added_to_hass()
        self.async_on_remove(
            self.coordinator.async_subscribe_events(self._handle_event)
        )

    @callback
    def _handle_event(self, event: DeviceButtonEvent) -> None:
        self._trigger_event(
            ButtonEventType.PRESS_END,
            {"button": event.button},
        )
        self.async_write_ha_state()
