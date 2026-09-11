"""HA-VeSync-BT Bluetooth coordinator."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from dataclasses import replace
import logging
from time import monotonic

from homeassistant.components import bluetooth
from homeassistant.components.bluetooth import (
    BluetoothChange,
    BluetoothScanningMode,
    BluetoothServiceInfoBleak,
    async_ble_device_from_address,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import STATE_THROTTLE_SECONDS, SUPPORTED_LOCAL_NAME
from .devices.cns_r002s_s import CnsR002sDevice
from .food_cursor import advance_quick_food_cursor
from .protocol.exceptions import VeSyncConnectionError
from .protocol.models import DeviceButtonEvent, ScaleState
from .protocol.nutrition import Nutrition

_LOGGER = logging.getLogger(__name__)


class HaVesyncCoordinator(DataUpdateCoordinator[ScaleState]):
    """Coordinate one VeSync BLE device."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        address: str,
    ) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=f"HA-VeSync-BT {address}",
            update_interval=None,
        )
        self.entry = entry
        self.address = address.upper()
        self.device = CnsR002sDevice(
            self.address,
            state_callback=self._handle_device_state,
            event_callback=self._handle_device_event,
        )
        self.data = self.device.state

        self._cancel_bluetooth: Callable[[], None] | None = None
        self._connect_lock = asyncio.Lock()
        self._event_listeners: set[Callable[[DeviceButtonEvent], None]] = set()
        self._last_publish = 0.0
        self._food_cursor_index: int | None = None

    async def async_start(self) -> None:
        """Start discovery/reconnect handling."""
        self._cancel_bluetooth = bluetooth.async_register_callback(
            self.hass,
            self._async_bluetooth_callback,
            {"address": self.address},
            BluetoothScanningMode.PASSIVE,
        )

        if async_ble_device_from_address(
            self.hass,
            self.address,
            connectable=True,
        ):
            self.entry.async_create_background_task(
                self.hass,
                self._async_connect(),
                "ha_vesync_bt_initial_connect",
            )

    async def async_shutdown(self) -> None:
        """Stop coordinator."""
        if self._cancel_bluetooth is not None:
            self._cancel_bluetooth()
            self._cancel_bluetooth = None
        await self.device.disconnect()

    async def async_ensure_connected(self) -> None:
        """Ensure an active connection for a user action."""
        if self.device.connected:
            return
        await self._async_connect()
        if not self.device.connected:
            raise VeSyncConnectionError(
                "Wake the scale and keep it in Bluetooth range"
            )

    @callback
    def async_subscribe_events(
        self,
        listener: Callable[[DeviceButtonEvent], None],
    ) -> Callable[[], None]:
        """Subscribe to physical control events."""
        self._event_listeners.add(listener)

        @callback
        def _remove() -> None:
            self._event_listeners.discard(listener)

        return _remove

    async def async_refresh_all(self) -> None:
        """Refresh device state."""
        await self.async_ensure_connected()
        await self.device.refresh_all()

    async def async_tare(self) -> None:
        """Tare."""
        await self.async_ensure_connected()
        await self.device.tare()

    async def async_sync_time(self) -> None:
        """Sync time."""
        await self.async_ensure_connected()
        await self.device.sync_time()

    async def async_set_unit(self, unit: str) -> None:
        """Set unit."""
        await self.async_ensure_connected()
        await self.device.set_unit(unit)

    async def async_set_enabled_units(self, units: list[str]) -> None:
        """Set enabled-unit mask."""
        await self.async_ensure_connected()
        await self.device.set_enabled_units(units)

    async def async_set_language(self, language: str) -> None:
        """Set language."""
        await self.async_ensure_connected()
        await self.device.set_language(language)

    async def async_set_brightness(self, brightness: str) -> None:
        """Set brightness."""
        await self.async_ensure_connected()
        await self.device.set_brightness(brightness)

    async def async_set_standby(self, seconds: int) -> None:
        """Set timeout."""
        await self.async_ensure_connected()
        await self.device.set_standby(seconds)

    async def async_add_quick_food(
        self,
        name: str,
        daily_food_weight_g: float,
        nutrition: Nutrition,
    ) -> None:
        """Add Quick Food."""
        await self.async_ensure_connected()
        await self.device.add_quick_food(
            name,
            daily_food_weight_g,
            nutrition,
        )

    async def async_remove_quick_food(self, sequence: int) -> None:
        """Remove Quick Food."""
        await self.async_ensure_connected()
        await self.device.remove_quick_food(sequence)

    async def async_reorder_quick_foods(self, sequences: list[int]) -> None:
        """Reorder Quick Foods."""
        await self.async_ensure_connected()
        await self.device.reorder_quick_foods(sequences)

    async def async_set_food_context(
        self,
        name: str,
        nutrition: Nutrition,
    ) -> None:
        """Set current app food context."""
        await self.async_ensure_connected()
        await self.device.set_food_context(name, nutrition)

    @callback
    def _async_bluetooth_callback(
        self,
        service_info: BluetoothServiceInfoBleak,
        _change: BluetoothChange,
    ) -> None:
        if not service_info.connectable:
            return
        if not self.device.connected:
            self.entry.async_create_background_task(
                self.hass,
                self._async_connect(),
                "ha_vesync_bt_reconnect",
            )

    async def _async_connect(self) -> None:
        async with self._connect_lock:
            if self.device.connected:
                return

            ble_device = async_ble_device_from_address(
                self.hass,
                self.address,
                connectable=True,
            )
            if ble_device is None:
                return

            try:
                await self.device.connect(
                    ble_device,
                    ble_device.name or SUPPORTED_LOCAL_NAME,
                )
            except Exception:  # noqa: BLE001
                _LOGGER.debug(
                    "Unable to connect to HA-VeSync-BT device %s",
                    self.address,
                    exc_info=True,
                )

    @callback
    def _handle_device_state(self, state: ScaleState) -> None:
        now = monotonic()
        previous = self.data

        if not state.connected:
            self._food_cursor_index = None
            if state.selected_food is not None:
                state = replace(state, selected_food=None)
                self.device.state = state

        quick_foods_changed = state.quick_foods != previous.quick_foods

        if state.selected_food is not None and (
            quick_foods_changed or state.selected_food != previous.selected_food
        ):
            matched = self._match_quick_food_index(state)
            if matched is not None:
                self._food_cursor_index = matched
                canonical = state.quick_foods[matched]
                if state.selected_food != canonical:
                    state = replace(state, selected_food=canonical)
                    self.device.state = state
            elif quick_foods_changed:
                self._food_cursor_index = None
                state = replace(state, selected_food=None)
                self.device.state = state

        selected_food_changed = state.selected_food != previous.selected_food
        self.data = state
        if (
            selected_food_changed
            or not state.connected
            or now - self._last_publish >= STATE_THROTTLE_SECONDS
        ):
            self._last_publish = now
            self.async_set_updated_data(state)

    @callback
    def _handle_device_event(self, event: DeviceButtonEvent) -> None:
        if event.button in {"left", "right"}:
            self._advance_food_cursor(event.button)

        for listener in tuple(self._event_listeners):
            listener(event)

    def _advance_food_cursor(self, direction: str) -> None:
        foods = self.device.state.quick_foods
        next_index = advance_quick_food_cursor(
            self._food_cursor_index,
            len(foods),
            direction,
        )
        self._food_cursor_index = next_index
        selected_food = foods[next_index] if next_index is not None else None

        state = replace(self.device.state, selected_food=selected_food)
        self.device.state = state
        self.data = state
        self._last_publish = monotonic()
        self.async_set_updated_data(state)

    @staticmethod
    def _match_quick_food_index(state: ScaleState) -> int | None:
        selected = state.selected_food
        if selected is None:
            return None

        matches = [
            index
            for index, food in enumerate(state.quick_foods)
            if (
                food.name == selected.name
                and food.daily_food_weight_g == selected.daily_food_weight_g
                and food.nutrition == selected.nutrition
            )
        ]
        return matches[0] if len(matches) == 1 else None
