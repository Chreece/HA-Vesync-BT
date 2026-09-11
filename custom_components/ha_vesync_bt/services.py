"""Service actions for VeSync Local BT."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.const import ATTR_DEVICE_ID
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import device_registry as dr

from .const import (
    ATTR_DAILY_FOOD_WEIGHT_G,
    ATTR_NAME,
    ATTR_SEQUENCE,
    ATTR_SEQUENCES,
    ATTR_UNITS,
    DOMAIN,
    NUTRIENT_FIELDS,
    SERVICE_ADD_QUICK_FOOD,
    SERVICE_REMOVE_QUICK_FOOD,
    SERVICE_REORDER_QUICK_FOODS,
    SERVICE_SET_ENABLED_UNITS,
    SERVICE_SET_FOOD_CONTEXT,
)
from .coordinator import HaVesyncCoordinator
from .devices.cns_r002s_s import UNIT_CONFIG_BITS
from .protocol.nutrition import Nutrition


DEVICE_FIELD = {vol.Required(ATTR_DEVICE_ID): cv.string}

NUTRITION_SCHEMA = {
    vol.Optional(field, default=0.0): vol.Coerce(float)
    for field in NUTRIENT_FIELDS
}

ADD_QUICK_FOOD_SCHEMA = vol.Schema(
    {
        **DEVICE_FIELD,
        vol.Required(ATTR_NAME): vol.All(str, vol.Length(min=1, max=20)),
        vol.Optional(ATTR_DAILY_FOOD_WEIGHT_G, default=100.0): vol.All(
            vol.Coerce(float),
            vol.Range(min=0, max=5000),
        ),
        **NUTRITION_SCHEMA,
    }
)

REMOVE_QUICK_FOOD_SCHEMA = vol.Schema(
    {
        **DEVICE_FIELD,
        vol.Required(ATTR_SEQUENCE): vol.All(
            vol.Coerce(int),
            vol.Range(min=1, max=255),
        ),
    }
)

REORDER_QUICK_FOODS_SCHEMA = vol.Schema(
    {
        **DEVICE_FIELD,
        vol.Required(ATTR_SEQUENCES): vol.All(
            cv.ensure_list,
            [vol.All(vol.Coerce(int), vol.Range(min=1, max=255))],
        ),
    }
)

SET_ENABLED_UNITS_SCHEMA = vol.Schema(
    {
        **DEVICE_FIELD,
        vol.Required(ATTR_UNITS): vol.All(
            cv.ensure_list,
            [vol.In(UNIT_CONFIG_BITS)],
        ),
    }
)

SET_FOOD_CONTEXT_SCHEMA = vol.Schema(
    {
        **DEVICE_FIELD,
        vol.Required(ATTR_NAME): vol.All(str, vol.Length(min=1, max=20)),
        **NUTRITION_SCHEMA,
    }
)


def _nutrition(data: dict[str, Any]) -> Nutrition:
    return Nutrition(
        **{
            field: float(data.get(field, 0.0))
            for field in NUTRIENT_FIELDS
        }
    )


def _coordinator_from_call(
    hass: HomeAssistant,
    call: ServiceCall,
) -> HaVesyncCoordinator:
    device_id = call.data[ATTR_DEVICE_ID]
    device = dr.async_get(hass).async_get(device_id)
    if device is None:
        raise ServiceValidationError(f"Unknown device_id: {device_id}")

    for entry_id in device.config_entries:
        entry = hass.config_entries.async_get_entry(entry_id)
        if entry and entry.domain == DOMAIN and entry.runtime_data is not None:
            return entry.runtime_data

    raise ServiceValidationError(
        "Selected device does not belong to VeSync Local BT"
    )


async def async_setup_services(hass: HomeAssistant) -> None:
    """Register integration actions."""

    async def add_quick_food(call: ServiceCall) -> None:
        coordinator = _coordinator_from_call(hass, call)
        await coordinator.async_add_quick_food(
            call.data[ATTR_NAME],
            float(call.data[ATTR_DAILY_FOOD_WEIGHT_G]),
            _nutrition(call.data),
        )

    async def remove_quick_food(call: ServiceCall) -> None:
        coordinator = _coordinator_from_call(hass, call)
        await coordinator.async_remove_quick_food(
            int(call.data[ATTR_SEQUENCE])
        )

    async def reorder_quick_foods(call: ServiceCall) -> None:
        coordinator = _coordinator_from_call(hass, call)
        await coordinator.async_reorder_quick_foods(
            [int(value) for value in call.data[ATTR_SEQUENCES]]
        )

    async def set_enabled_units(call: ServiceCall) -> None:
        coordinator = _coordinator_from_call(hass, call)
        await coordinator.async_set_enabled_units(
            list(call.data[ATTR_UNITS])
        )

    async def set_food_context(call: ServiceCall) -> None:
        coordinator = _coordinator_from_call(hass, call)
        await coordinator.async_set_food_context(
            call.data[ATTR_NAME],
            _nutrition(call.data),
        )

    hass.services.async_register(
        DOMAIN,
        SERVICE_ADD_QUICK_FOOD,
        add_quick_food,
        schema=ADD_QUICK_FOOD_SCHEMA,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_REMOVE_QUICK_FOOD,
        remove_quick_food,
        schema=REMOVE_QUICK_FOOD_SCHEMA,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_REORDER_QUICK_FOODS,
        reorder_quick_foods,
        schema=REORDER_QUICK_FOODS_SCHEMA,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_SET_ENABLED_UNITS,
        set_enabled_units,
        schema=SET_ENABLED_UNITS_SCHEMA,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_SET_FOOD_CONTEXT,
        set_food_context,
        schema=SET_FOOD_CONTEXT_SCHEMA,
    )
