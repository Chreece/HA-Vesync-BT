"""COSORI CNS-R002S-S native BLE implementation."""
from __future__ import annotations

import asyncio
from collections.abc import Callable
from dataclasses import replace
import datetime as dt
import logging
import time

from bleak.backends.device import BLEDevice

from ..protocol.models import DeviceButtonEvent, QuickFood, ScaleState
from ..protocol.nutrition import Nutrition, decode_nutrition, encode_nutrition
from ..protocol.vsv3 import VSV3Transport

_LOGGER = logging.getLogger(__name__)

CMD_SET_TIME = 0xA081
CMD_FIRMWARE = 0xA08A
CMD_QUERY_BATTERY, CMD_BATTERY_REPORT = 0xA100, 0xA101
CMD_QUERY_STANDBY, CMD_SET_STANDBY = 0xA102, 0xA104
CMD_SET_BRIGHTNESS, CMD_QUERY_BRIGHTNESS = 0xA105, 0xA106
CMD_SET_UNIT, CMD_QUERY_UNIT, CMD_UNIT_REPORT = 0xA180, 0xA181, 0xA182
CMD_SET_TARE, CMD_TARE_REPORT = 0xA185, 0xA186
CMD_LIVE_MEASUREMENT, CMD_QUERY_STATUS = 0xA187, 0xA188
CMD_SET_UNIT_CONFIG, CMD_QUERY_UNIT_CONFIG = 0x4102, 0x4103
CMD_ADD_QUICK_FOOD, CMD_SORT_QUICK_FOOD = 0x4441, 0x4442
CMD_QUERY_QUICK_FOOD, CMD_SET_FOOD_CONTEXT = 0x4443, 0x4444
CMD_SELECTED_FOOD_REPORT = 0x4445
CMD_SET_LANGUAGE, CMD_QUERY_LANGUAGE, CMD_BUTTON_REPORT = 0x4447, 0x4448, 0x444A

LANGUAGE_CODES = {
    1: "English (US)", 2: "English (UK)", 3: "German",
    4: "French", 5: "Italian", 6: "Spanish",
}
LANGUAGE_VALUES = {v: k for k, v in LANGUAGE_CODES.items()}
BRIGHTNESS_VALUES = {"Low": 40, "Medium": 60, "High": 90}
BRIGHTNESS_CODES = {v: k for k, v in BRIGHTNESS_VALUES.items()}
STANDBY_VALUES = (30, 45, 60, 120, 180, 300)
UNIT_PAYLOADS = {
    "oz": b"\x00\x00", "lb:oz": b"\x01\x00", "g": b"\x02\x00",
    "mL water": b"\x03\x01", "mL milk": b"\x03\x02",
    "fl oz water": b"\x04\x01", "fl oz milk": b"\x04\x02",
}
PAYLOAD_UNITS = {v: k for k, v in UNIT_PAYLOADS.items()}
WEIGHT_UNIT_CODES = {
    0x0000: "oz", 0x0001: "lb:oz", 0x0002: "g",
    0x0103: "mL water", 0x0203: "mL milk",
    0x0104: "fl oz water", 0x0204: "fl oz milk",
}
UNIT_CONFIG_BITS = (
    "oz", "lb:oz", "fl oz water", "fl oz milk", "g", "mL water", "mL milk"
)


def _u24le(data: bytes) -> int:
    if len(data) != 3:
        raise ValueError("uint24 requires exactly three bytes")
    return data[0] | data[1] << 8 | data[2] << 16


def _put_u24le(value: int) -> bytes:
    if not 0 <= value <= 0xFFFFFF:
        raise ValueError("value does not fit uint24")
    return bytes((value & 0xFF, value >> 8 & 0xFF, value >> 16 & 0xFF))


class CnsR002sDevice:
    """Native CNS-R002S-S client using only proven device commands."""

    def __init__(
        self,
        address: str,
        *,
        state_callback: Callable[[ScaleState], None] | None = None,
        event_callback: Callable[[DeviceButtonEvent], None] | None = None,
    ) -> None:
        self.address = address.upper()
        self.state = ScaleState(address=self.address)
        self._state_callback = state_callback
        self._event_callback = event_callback
        self._transport = VSV3Transport(
            self.address,
            disconnected_callback=self._on_disconnected,
            unsolicited_callback=self._on_unsolicited,
        )

    @property
    def connected(self) -> bool:
        return self._transport.connected

    async def connect(self, ble_device: BLEDevice, name: str) -> None:
        await self._transport.connect(ble_device, name)
        self._set_state(connected=True)
        await self.refresh_all()

    async def disconnect(self) -> None:
        await self._transport.disconnect()
        self._set_state(connected=False)

    async def refresh_all(self) -> None:
        for query in (
            self.query_firmware, self.query_status, self.query_unit_config,
            self.query_language, self.query_battery, self.query_brightness,
            self.query_current_unit, self.query_standby, self.query_quick_foods,
            self.sync_time,
        ):
            try:
                await query()
            except Exception:  # noqa: BLE001
                _LOGGER.debug("CNS refresh step %s failed", query.__name__, exc_info=True)

    async def query_firmware(self) -> str | None:
        payload = await self._transport.request(CMD_FIRMWARE, b"\x00")
        runs, current = [], bytearray()
        for byte in payload:
            if 32 <= byte <= 126:
                current.append(byte)
            else:
                if len(current) >= 3:
                    runs.append(current.decode("ascii", "replace"))
                current.clear()
        if len(current) >= 3:
            runs.append(current.decode("ascii", "replace"))
        value = " / ".join(runs) or payload.hex()
        self._set_state(firmware=value)
        return value

    async def query_status(self) -> ScaleState:
        self._set_state(**self._parse_status(await self._transport.request(CMD_QUERY_STATUS)))
        return self.state

    async def query_battery(self) -> int | None:
        payload = await self._transport.request(CMD_QUERY_BATTERY)
        value = payload[0] if payload else None
        self._set_state(battery_percent=value)
        return value

    async def query_brightness(self) -> str | None:
        payload = await self._transport.request(CMD_QUERY_BRIGHTNESS)
        raw = payload[0] if payload else None
        value = BRIGHTNESS_CODES.get(raw)
        self._set_state(brightness=value, brightness_raw=raw)
        return value

    async def query_language(self) -> str | None:
        payload = await self._transport.request(CMD_QUERY_LANGUAGE)
        value = LANGUAGE_CODES.get(payload[0]) if payload else None
        self._set_state(language=value)
        return value

    async def query_current_unit(self) -> str | None:
        payload = await self._transport.request(CMD_QUERY_UNIT)
        value = PAYLOAD_UNITS.get(payload[:2])
        self._set_state(current_unit=value)
        return value

    async def query_unit_config(self) -> tuple[str, ...]:
        payload = await self._transport.request(CMD_QUERY_UNIT_CONFIG)
        mask = payload[0] if payload else 0
        value = tuple(u for bit, u in enumerate(UNIT_CONFIG_BITS) if mask & 1 << bit)
        self._set_state(enabled_units=value)
        return value

    async def query_standby(self) -> int | None:
        payload = await self._transport.request(CMD_QUERY_STANDBY)
        value = int.from_bytes(payload[:2], "little") if len(payload) >= 2 else None
        self._set_state(standby_timeout=value)
        return value

    async def query_quick_foods(self) -> tuple[QuickFood, ...]:
        foods: list[QuickFood] = []
        page = 1
        for _ in range(10):
            payload = await self._transport.request(CMD_QUERY_QUICK_FOOD, bytes([page]), timeout=8)
            current, total, page_foods = self._parse_quick_food_page(payload)
            foods.extend(page_foods)
            if current >= total:
                break
            page += 1
        else:
            raise ValueError("Quick Food pagination safety limit reached")
        value = tuple(foods)
        self._set_state(quick_foods=value)
        return value

    async def set_unit(self, unit: str) -> None:
        await self._transport.request(CMD_SET_UNIT, UNIT_PAYLOADS[unit], response_optional=True)
        await asyncio.sleep(0.1)
        await self.query_current_unit()

    async def set_enabled_units(self, units: list[str]) -> None:
        if not units:
            raise ValueError("At least one unit must remain enabled")
        unknown = set(units) - set(UNIT_CONFIG_BITS)
        if unknown:
            raise ValueError(f"Unsupported units: {sorted(unknown)}")
        mask = sum(1 << bit for bit, unit in enumerate(UNIT_CONFIG_BITS) if unit in units)
        await self._transport.request(CMD_SET_UNIT_CONFIG, bytes([mask, 0]), response_optional=True)
        await asyncio.sleep(0.1)
        await self.query_unit_config()

    async def set_brightness(self, label: str) -> None:
        await self._transport.request(CMD_SET_BRIGHTNESS, bytes([BRIGHTNESS_VALUES[label]]), response_optional=True)
        await asyncio.sleep(0.1)
        await self.query_brightness()

    async def set_standby(self, seconds: int) -> None:
        if seconds not in STANDBY_VALUES:
            raise ValueError(f"Unsupported standby timeout: {seconds}")
        await self._transport.request(CMD_SET_STANDBY, seconds.to_bytes(2, "little"), response_optional=True)
        await asyncio.sleep(0.1)
        await self.query_standby()

    async def set_language(self, language: str) -> None:
        await self._transport.request(CMD_SET_LANGUAGE, bytes([LANGUAGE_VALUES[language]]), response_optional=True, timeout=2)

    async def tare(self) -> None:
        await self._transport.request(CMD_SET_TARE, response_optional=True)

    async def sync_time(self) -> None:
        epoch = int(time.time()) & 0xFFFFFFFF
        offset = dt.datetime.now().astimezone().utcoffset() or dt.timedelta()
        hours = int(offset.total_seconds() / 3600)
        await self._transport.request(CMD_SET_TIME, epoch.to_bytes(4, "little") + bytes([hours & 0xFF]), response_optional=True)

    async def add_quick_food(self, name: str, daily_food_weight_g: float, nutrition: Nutrition) -> None:
        current = await self.query_quick_foods()
        if len(current) >= 50:
            raise ValueError("The scale already contains 50 Quick Foods")
        sequence = max((f.sequence for f in current), default=0) + 1
        food = QuickFood(sequence, name, daily_food_weight_g, nutrition)
        await self._transport.request(CMD_ADD_QUICK_FOOD, self._encode_quick_food(food), response_optional=True)
        await asyncio.sleep(0.2)
        await self.query_quick_foods()

    async def remove_quick_food(self, sequence: int) -> None:
        current = await self.query_quick_foods()
        retained = [f.sequence for f in current if f.sequence != sequence]
        if len(retained) == len(current):
            raise ValueError(f"Quick Food sequence {sequence} was not found")
        await self._transport.request(CMD_SORT_QUICK_FOOD, bytes(retained), response_optional=True)
        await asyncio.sleep(0.2)
        await self.query_quick_foods()

    async def reorder_quick_foods(self, sequences: list[int]) -> None:
        current = await self.query_quick_foods()
        if set(sequences) != {f.sequence for f in current} or len(sequences) != len(current):
            raise ValueError("Reorder list must contain every current Quick Food sequence once")
        await self._transport.request(CMD_SORT_QUICK_FOOD, bytes(sequences), response_optional=True)
        await asyncio.sleep(0.2)
        await self.query_quick_foods()

    async def set_food_context(self, name: str, nutrition: Nutrition) -> None:
        encoded = self._encode_name(name)
        await self._transport.request(CMD_SET_FOOD_CONTEXT, bytes([len(encoded)]) + encoded + encode_nutrition(nutrition), response_optional=True)

    def _on_unsolicited(self, command: int, payload: bytes) -> None:
        if command == CMD_LIVE_MEASUREMENT:
            self._set_state(**self._parse_measurement(payload))
        elif command == CMD_BATTERY_REPORT and payload:
            self._set_state(battery_percent=payload[0])
        elif command == CMD_BUTTON_REPORT and len(payload) >= 3:
            for pressed, name in zip(payload[:3], ("set", "left", "right"), strict=True):
                if pressed == 1:
                    self._emit_button(name)
        elif command == CMD_UNIT_REPORT:
            unit = PAYLOAD_UNITS.get(payload[:2])
            if unit is not None:
                self._set_state(current_unit=unit)
            self._emit_button("unit")
        elif command == CMD_TARE_REPORT:
            if payload:
                self._set_state(tare=payload[0] == 1)
            self._emit_button("tare")
        elif command == CMD_SELECTED_FOOD_REPORT:
            try:
                self._set_state(selected_food=self._parse_selected_food(payload))
            except ValueError:
                _LOGGER.debug("Unable to parse selected-food report", exc_info=True)

    def _on_disconnected(self) -> None:
        self._set_state(connected=False)

    def _emit_button(self, button: str) -> None:
        if self._event_callback:
            self._event_callback(DeviceButtonEvent(button))

    def _set_state(self, **changes: object) -> None:
        self.state = replace(self.state, **changes)
        if self._state_callback:
            self._state_callback(self.state)

    @staticmethod
    def _parse_measurement(payload: bytes) -> dict[str, object]:
        if len(payload) < 7:
            raise ValueError("Measurement payload is too short")
        raw, code = _u24le(payload[1:4]), int.from_bytes(payload[4:6], "little")
        unit = WEIGHT_UNIT_CODES.get(code, f"0x{code:04X}")
        value = raw / (10.0 if unit in {"g", "mL water", "mL milk"} else 100.0)
        if payload[0] == 1:
            value = -value
        return {"measurement": value, "unit": unit, "stable": payload[6] == 1}

    def _parse_status(self, payload: bytes) -> dict[str, object]:
        if len(payload) < 9:
            raise ValueError("Status payload is too short")
        result = self._parse_measurement(payload[:7])
        result["tare"] = payload[7] == 1
        code = payload[8]
        low = overload = present = charging = None
        if code in (0, 1):
            low, overload, present, charging = False, False, True, False
        elif code == 2:
            low, overload, present, charging = False, True, True, False
        elif code == 3:
            low = True
        elif code == 4:
            charging = True
        result.update(low_voltage=low, overload=overload, object_present=present, charging=charging)
        return result

    @staticmethod
    def _parse_quick_food_page(payload: bytes) -> tuple[int, int, list[QuickFood]]:
        if len(payload) < 3:
            raise ValueError("Quick Food response is too short")
        current, total, count, pos = payload[0], payload[1], payload[2], 3
        foods: list[QuickFood] = []
        for _ in range(count):
            if pos + 2 > len(payload):
                raise ValueError("Truncated Quick Food entry header")
            sequence, name_len = payload[pos], payload[pos + 1]
            pos += 2
            if pos + name_len + 36 > len(payload):
                raise ValueError("Truncated Quick Food entry")
            name = payload[pos:pos + name_len].decode("utf-8", "replace")
            pos += name_len
            daily = _u24le(payload[pos:pos + 3]) / 10.0
            pos += 3
            nutrition = decode_nutrition(payload[pos:pos + 33])
            pos += 33
            foods.append(QuickFood(sequence, name, daily, nutrition))
        return current, total, foods

    @staticmethod
    def _parse_selected_food(payload: bytes) -> QuickFood:
        if not payload:
            raise ValueError("Selected-food payload is empty")
        name_len, pos = payload[0], 1
        if pos + name_len + 36 > len(payload):
            raise ValueError("Selected-food payload is truncated")
        name = payload[pos:pos + name_len].decode("utf-8", "replace")
        pos += name_len
        daily = _u24le(payload[pos:pos + 3]) / 10.0
        pos += 3
        return QuickFood(0, name, daily, decode_nutrition(payload[pos:pos + 33]))

    @classmethod
    def _encode_quick_food(cls, food: QuickFood) -> bytes:
        name = cls._encode_name(food.name)
        return bytes([food.sequence & 0xFF, len(name)]) + name + _put_u24le(round(food.daily_food_weight_g * 10)) + encode_nutrition(food.nutrition)

    @staticmethod
    def _encode_name(name: str) -> bytes:
        encoded = name[:20].encode("utf-8")
        if len(encoded) > 255:
            raise ValueError("Quick Food name is too long in UTF-8")
        return encoded
