"""Diagnostics for HA-VeSync-BT."""

from __future__ import annotations

from dataclasses import asdict

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .coordinator import HaVesyncCoordinator

REDACT = {"address", "quick_foods", "selected_food"}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant,
    entry: ConfigEntry,
) -> dict:
    """Return privacy-safe diagnostics."""
    coordinator: HaVesyncCoordinator = entry.runtime_data
    state = asdict(coordinator.data)

    # Food names/nutrition may reveal personal diet information.
    state["quick_food_count"] = len(coordinator.data.quick_foods)
    state["quick_foods"] = "<redacted>"
    state["selected_food"] = "<redacted>"

    return async_redact_data(
        {
            "entry": {
                "title": entry.title,
                "data": dict(entry.data),
            },
            "state": state,
        },
        REDACT,
    )
