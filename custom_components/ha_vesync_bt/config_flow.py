"""Config flow for HA-VeSync-BT."""

from __future__ import annotations

from typing import Any, override

import voluptuous as vol

from homeassistant.components.bluetooth import (
    BluetoothServiceInfoBleak,
    async_discovered_service_info,
)
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_ADDRESS

from .const import DOMAIN, SUPPORTED_LOCAL_NAME


def _is_supported(info: BluetoothServiceInfoBleak) -> bool:
    local_name = (info.name or "").strip()
    return info.connectable and local_name == SUPPORTED_LOCAL_NAME


class HaVesyncConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle HA-VeSync-BT setup."""

    VERSION = 1

    def __init__(self) -> None:
        self._discovery_info: BluetoothServiceInfoBleak | None = None
        self._devices: dict[str, BluetoothServiceInfoBleak] = {}

    @override
    async def async_step_bluetooth(
        self,
        discovery_info: BluetoothServiceInfoBleak,
    ) -> ConfigFlowResult:
        """Handle Bluetooth discovery."""
        if not _is_supported(discovery_info):
            return self.async_abort(reason="not_supported")

        await self.async_set_unique_id(discovery_info.address)
        self._abort_if_unique_id_configured()

        self._discovery_info = discovery_info
        self.context["title_placeholders"] = {
            "name": SUPPORTED_LOCAL_NAME,
        }
        return await self.async_step_bluetooth_confirm()

    async def async_step_bluetooth_confirm(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> ConfigFlowResult:
        """Confirm discovered scale."""
        assert self._discovery_info is not None

        if user_input is not None:
            return self._create_entry(self._discovery_info)

        self._set_confirm_only()
        return self.async_show_form(
            step_id="bluetooth_confirm",
            description_placeholders={
                "name": SUPPORTED_LOCAL_NAME,
            },
        )

    @override
    async def async_step_user(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> ConfigFlowResult:
        """Pick a currently discovered scale."""
        if user_input is not None:
            address = user_input[CONF_ADDRESS]
            info = self._devices[address]
            await self.async_set_unique_id(address, raise_on_progress=False)
            self._abort_if_unique_id_configured()
            return self._create_entry(info)

        current_ids = self._async_current_ids(include_ignore=False)
        self._devices = {
            info.address: info
            for info in async_discovered_service_info(self.hass, False)
            if _is_supported(info) and info.address not in current_ids
        }

        if not self._devices:
            return self.async_abort(reason="no_devices_found")

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_ADDRESS): vol.In(
                        {
                            address: f"{SUPPORTED_LOCAL_NAME} ({address})"
                            for address in self._devices
                        }
                    )
                }
            ),
        )

    def _create_entry(
        self,
        info: BluetoothServiceInfoBleak,
    ) -> ConfigFlowResult:
        return self.async_create_entry(
            title=SUPPORTED_LOCAL_NAME,
            data={CONF_ADDRESS: info.address},
        )
