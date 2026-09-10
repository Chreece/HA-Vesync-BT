"""Select entities for HA-VeSync-BT."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from homeassistant.components.select import (
    SelectEntity,
    SelectEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import HaVesyncCoordinator
from .devices.cns_r002s_s import (
    BRIGHTNESS_VALUES,
    LANGUAGE_VALUES,
    STANDBY_VALUES,
    UNIT_PAYLOADS,
)
from .entity import HaVesyncEntity


@dataclass(frozen=True, kw_only=True)
class HaVesyncSelectDescription(SelectEntityDescription):
    """Describe a select."""

    options_fn: Any
    value_fn: Any
    select_fn: Any


SELECTS = (
    HaVesyncSelectDescription(
        key="unit",
        translation_key="unit",
        options_fn=lambda: list(UNIT_PAYLOADS),
        value_fn=lambda state: state.current_unit,
        select_fn=lambda coordinator, value: coordinator.async_set_unit(value),
    ),
    HaVesyncSelectDescription(
        key="language",
        translation_key="language",
        options_fn=lambda: list(LANGUAGE_VALUES),
        value_fn=lambda state: state.language,
        select_fn=lambda coordinator, value: coordinator.async_set_language(value),
    ),
    HaVesyncSelectDescription(
        key="brightness",
        translation_key="brightness",
        options_fn=lambda: list(BRIGHTNESS_VALUES),
        value_fn=lambda state: state.brightness,
        select_fn=lambda coordinator, value: coordinator.async_set_brightness(value),
    ),
    HaVesyncSelectDescription(
        key="standby_timeout",
        translation_key="standby_timeout",
        options_fn=lambda: [str(value) for value in STANDBY_VALUES],
        value_fn=lambda state: (
            str(state.standby_timeout)
            if state.standby_timeout is not None
            else None
        ),
        select_fn=lambda coordinator, value: coordinator.async_set_standby(
            int(value)
        ),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up selects."""
    coordinator: HaVesyncCoordinator = entry.runtime_data
    async_add_entities(
        HaVesyncSelect(coordinator, description)
        for description in SELECTS
    )


class HaVesyncSelect(HaVesyncEntity, SelectEntity):
    """One HA-VeSync-BT select."""

    entity_description: HaVesyncSelectDescription

    def __init__(
        self,
        coordinator: HaVesyncCoordinator,
        description: HaVesyncSelectDescription,
    ) -> None:
        super().__init__(coordinator, description.key)
        self.entity_description = description
        self._attr_options = description.options_fn()

    @property
    def current_option(self) -> str | None:
        """Return selected option."""
        return self.entity_description.value_fn(self.coordinator.data)

    async def async_select_option(self, option: str) -> None:
        """Select an option."""
        try:
            await self.entity_description.select_fn(self.coordinator, option)
        except Exception as err:
            raise HomeAssistantError(str(err)) from err
