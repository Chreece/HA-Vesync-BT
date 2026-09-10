"""HA-VeSync-BT integration."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_ADDRESS, Platform
from homeassistant.core import HomeAssistant

from .coordinator import HaVesyncCoordinator
from .services import async_setup_services

PLATFORMS = (
    Platform.SENSOR,
    Platform.BINARY_SENSOR,
    Platform.SELECT,
    Platform.BUTTON,
    Platform.EVENT,
)


async def async_setup(hass: HomeAssistant, _config: dict) -> bool:
    """Set up integration-level actions."""
    await async_setup_services(hass)
    return True


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
) -> bool:
    """Set up one VeSync BLE device."""
    address = entry.data[CONF_ADDRESS]
    coordinator = HaVesyncCoordinator(hass, entry, address)
    entry.runtime_data = coordinator

    await coordinator.async_start()
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
) -> bool:
    """Unload one VeSync BLE device."""
    unloaded = await hass.config_entries.async_unload_platforms(
        entry,
        PLATFORMS,
    )
    if unloaded:
        coordinator: HaVesyncCoordinator = entry.runtime_data
        await coordinator.async_shutdown()
    return unloaded
