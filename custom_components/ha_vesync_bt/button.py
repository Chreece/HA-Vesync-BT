"""Button entities for HA-VeSync-BT."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from homeassistant.components.button import (
    ButtonEntity,
    ButtonEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import HaVesyncCoordinator
from .entity import HaVesyncEntity


@dataclass(frozen=True, kw_only=True)
class HaVesyncButtonDescription(ButtonEntityDescription):
    """Describe a button."""

    press_fn: Any


BUTTONS = (
    HaVesyncButtonDescription(
        key="tare",
        translation_key="tare_button",
        press_fn=lambda coordinator: coordinator.async_tare(),
    ),
    HaVesyncButtonDescription(
        key="sync_time",
        translation_key="sync_time",
        press_fn=lambda coordinator: coordinator.async_sync_time(),
    ),
    HaVesyncButtonDescription(
        key="refresh",
        translation_key="refresh",
        press_fn=lambda coordinator: coordinator.async_refresh_all(),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up buttons."""
    coordinator: HaVesyncCoordinator = entry.runtime_data
    async_add_entities(
        HaVesyncButton(coordinator, description)
        for description in BUTTONS
    )


class HaVesyncButton(HaVesyncEntity, ButtonEntity):
    """One HA-VeSync-BT button."""

    entity_description: HaVesyncButtonDescription

    def __init__(
        self,
        coordinator: HaVesyncCoordinator,
        description: HaVesyncButtonDescription,
    ) -> None:
        super().__init__(coordinator, description.key)
        self.entity_description = description

    async def async_press(self) -> None:
        """Press button."""
        try:
            await self.entity_description.press_fn(self.coordinator)
        except Exception as err:
            raise HomeAssistantError(str(err)) from err
