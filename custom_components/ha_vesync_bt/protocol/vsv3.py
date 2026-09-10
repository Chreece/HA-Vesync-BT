"""Generic VeSync VSV3 BLE transport."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
import logging
import os
import secrets
import time
from typing import Any

from bleak.backends.device import BLEDevice
from bleak_retry_connector import (
    BleakClientWithServiceCache,
    establish_connection,
)

from .crypto import aes_decrypt, aes_encrypt, derive_k1, random_prime
from .exceptions import (
    VeSyncConnectionError,
    VeSyncNotConnectedError,
    VeSyncProtocolResponseError,
    VeSyncProtocolTimeout,
)
from .frame import build_frame, checksum_ok, decode_frame, pop_frames

_LOGGER = logging.getLogger(__name__)

SERVICE_UUID = "0000fff0-0000-1000-8000-00805f9b34fb"
NOTIFY_UUID = "0000fff1-0000-1000-8000-00805f9b34fb"
WRITE_UUID = "0000fff2-0000-1000-8000-00805f9b34fb"
EXTRA_UUID = "0000fff3-0000-1000-8000-00805f9b34fb"

CMD_KEY_NEGOTIATION = 0x4201
CMD_BIND = 0x4202


class VSV3Transport:
    """One connected VeSync VSV3 session."""

    def __init__(
        self,
        address: str,
        *,
        disconnected_callback: Callable[[], None] | None = None,
        unsolicited_callback: Callable[[int, bytes], None] | None = None,
    ) -> None:
        self.address = address.upper()
        self._client: BleakClientWithServiceCache | None = None
        self._write_char: Any = None

        self._sequence = 0
        self._rx_buffer = bytearray()
        self._pending: dict[tuple[int, int], asyncio.Future[bytes]] = {}
        self._command_lock = asyncio.Lock()

        self._k1: bytes | None = None
        self._session_iv: bytes | None = None

        self._disconnected_callback = disconnected_callback
        self._unsolicited_callback = unsolicited_callback

    @property
    def connected(self) -> bool:
        """Return whether BLE is currently connected."""
        return bool(self._client and self._client.is_connected)

    async def connect(self, ble_device: BLEDevice, name: str) -> None:
        """Connect, subscribe, and establish a fresh VSV3 session."""
        if self.connected:
            return

        try:
            client = await establish_connection(
                BleakClientWithServiceCache,
                ble_device,
                name,
                disconnected_callback=self._handle_disconnect,
                max_attempts=3,
            )
        except Exception as err:
            raise VeSyncConnectionError(str(err)) from err

        self._client = client

        backend = getattr(client, "_backend", None)
        acquire_mtu = getattr(backend, "_acquire_mtu", None)
        if acquire_mtu is not None:
            try:
                await acquire_mtu()
            except Exception:  # noqa: BLE001
                _LOGGER.debug("Could not explicitly acquire BLE MTU", exc_info=True)

        notify_char = client.services.get_characteristic(NOTIFY_UUID)
        write_char = client.services.get_characteristic(WRITE_UUID)
        if notify_char is None or write_char is None:
            await client.disconnect()
            raise VeSyncConnectionError("Expected VSV3 FFF1/FFF2 characteristics not found")

        self._write_char = write_char
        self._rx_buffer.clear()
        self._pending.clear()
        self._sequence = 0
        self._k1 = None
        self._session_iv = None

        try:
            await client.start_notify(notify_char, self._notification_handler)
            await self._handshake()
        except Exception:
            await client.disconnect()
            raise

    async def disconnect(self) -> None:
        """Disconnect and erase ephemeral session material."""
        client = self._client
        self._client = None
        self._write_char = None
        self._k1 = None
        self._session_iv = None

        for future in self._pending.values():
            if not future.done():
                future.cancel()
        self._pending.clear()

        if client and client.is_connected:
            try:
                await client.disconnect()
            except Exception:  # noqa: BLE001
                _LOGGER.debug("BLE disconnect failed", exc_info=True)

    async def request(
        self,
        command: int,
        payload: bytes = b"",
        *,
        key_type: int = 1,
        timeout: float = 6.0,
        response_optional: bool = False,
    ) -> bytes:
        """Send a serialized VSV3 request."""
        if not self.connected or self._write_char is None:
            raise VeSyncNotConnectedError("The scale is not connected")

        async with self._command_lock:
            sequence = self._next_sequence()
            encrypted = self._encrypt_payload(command, payload, key_type)
            frame = build_frame(
                command=command,
                sequence=sequence,
                payload=encrypted,
                key_type=key_type,
            )

            loop = asyncio.get_running_loop()
            future: asyncio.Future[bytes] = loop.create_future()
            self._pending[(command, sequence)] = future

            try:
                await self._write_frame(frame)
                try:
                    return await asyncio.wait_for(future, timeout=timeout)
                except TimeoutError as err:
                    if response_optional:
                        return b""
                    raise VeSyncProtocolTimeout(
                        f"Timed out waiting for 0x{command:04X}"
                    ) from err
            finally:
                self._pending.pop((command, sequence), None)

    def _next_sequence(self) -> int:
        sequence = self._sequence & 0xFF
        self._sequence = (self._sequence + 1) & 0xFF
        return sequence

    async def _write_frame(self, frame: bytes) -> None:
        assert self._client is not None
        assert self._write_char is not None

        sizes: list[int] = []
        try:
            value = int(self._write_char.max_write_without_response_size)
            if value > 0:
                sizes.append(value)
        except Exception:  # noqa: BLE001
            pass

        mtu = int(getattr(self._client, "mtu_size", 0) or 0)
        if mtu >= 23:
            sizes.append(mtu - 3)

        if not sizes:
            raise VeSyncConnectionError(
                "Unable to determine BLE write-without-response size"
            )

        chunk_size = min(sizes)
        if chunk_size < 20:
            raise VeSyncConnectionError(
                f"Invalid BLE write-without-response size: {chunk_size}"
            )

        try:
            for offset in range(0, len(frame), chunk_size):
                await self._client.write_gatt_char(
                    self._write_char,
                    frame[offset : offset + chunk_size],
                    response=False,
                )
                await asyncio.sleep(0)
        except Exception as err:
            raise VeSyncConnectionError(str(err)) from err

    def _notification_handler(self, _sender: Any, data: bytearray) -> None:
        self._rx_buffer.extend(bytes(data))
        for raw in pop_frames(self._rx_buffer):
            try:
                self._handle_frame(raw)
            except Exception:  # noqa: BLE001
                _LOGGER.debug("Unable to process VSV3 frame", exc_info=True)

    def _handle_frame(self, raw: bytes) -> None:
        decoded = decode_frame(raw)
        if not checksum_ok(raw):
            raise VeSyncProtocolResponseError("Invalid VSV3 checksum")

        payload = self._decrypt_payload(
            decoded.command,
            decoded.payload,
            decoded.key_type,
            inbound=True,
        )

        key = (decoded.command, decoded.sequence)
        pending = self._pending.get(key)
        if decoded.is_response and pending and not pending.done():
            pending.set_result(payload)
            return

        if self._unsolicited_callback is not None:
            self._unsolicited_callback(decoded.command, payload)

    def _encrypt_payload(self, command: int, payload: bytes, key_type: int) -> bytes:
        if key_type == 0 or not payload:
            return payload
        if key_type != 1:
            raise VeSyncProtocolResponseError(f"Unsupported outbound key type K{key_type}")
        if self._k1 is None:
            raise VeSyncProtocolResponseError("VSV3 K1 is not established")

        iv = bytes(16) if command == CMD_BIND else self._session_iv
        if iv is None:
            raise VeSyncProtocolResponseError("VSV3 session IV is not established")
        return aes_encrypt(self._k1, iv, payload)

    def _decrypt_payload(
        self,
        command: int,
        payload: bytes,
        key_type: int,
        *,
        inbound: bool,
    ) -> bytes:
        if key_type == 0 or not payload:
            return payload
        if key_type != 1:
            raise VeSyncProtocolResponseError(f"Unsupported inbound key type K{key_type}")
        if self._k1 is None:
            raise VeSyncProtocolResponseError("VSV3 K1 is not established")

        iv = self._session_iv
        if iv is None:
            raise VeSyncProtocolResponseError("VSV3 session IV is not established")
        return aes_decrypt(self._k1, iv, payload)

    async def _handshake(self) -> None:
        rng = secrets.SystemRandom()

        prime = random_prime()
        base = rng.randint(10, 100)
        private = rng.randint(5, 20)
        public = pow(base, private, prime)

        mac_reversed = self._reversed_mac_bytes()
        epoch = int(time.time()) & 0xFFFFFFFF
        timezone_byte = self._vsv3_timezone_byte()

        key_payload = (
            epoch.to_bytes(4, "little")
            + bytes([timezone_byte])
            + bytes([len(mac_reversed)])
            + mac_reversed
            + prime.to_bytes(2, "little")
            + bytes([base])
            + public.to_bytes(2, "little")
        )

        response = await self.request(
            CMD_KEY_NEGOTIATION,
            key_payload,
            key_type=0,
            timeout=8,
        )
        if len(response) < 4 or response[0] != 0:
            raise VeSyncProtocolResponseError(
                f"VSV3 0x4201 failed: {response.hex()}"
            )

        mac_length = response[1]
        if len(response) < 2 + mac_length + 2:
            raise VeSyncProtocolResponseError("Malformed VSV3 0x4201 response")

        response_mac = response[2 : 2 + mac_length]
        if response_mac != mac_reversed:
            raise VeSyncProtocolResponseError("VSV3 0x4201 MAC mismatch")

        device_public = int.from_bytes(
            response[2 + mac_length : 4 + mac_length],
            "little",
        )
        shared = pow(device_public, private, prime)
        self._k1 = derive_k1(shared, mac_reversed)

        self._session_iv = os.urandom(16)
        bind_payload = (
            bytes([12])
            + mac_reversed
            + bytes([16])
            + self._session_iv
        )

        bind_response = await self.request(
            CMD_BIND,
            bind_payload,
            key_type=1,
            timeout=8,
        )
        if not bind_response or bind_response[0] != 0:
            raise VeSyncProtocolResponseError(
                f"VSV3 0x4202 bind failed: {bind_response.hex()}"
            )

    def _reversed_mac_bytes(self) -> bytes:
        clean = self.address.replace(":", "").replace("-", "")
        if len(clean) != 12:
            raise VeSyncProtocolResponseError(
                f"Unexpected Bluetooth address format: {self.address}"
            )
        return bytes.fromhex(clean)[::-1]

    @staticmethod
    def _vsv3_timezone_byte() -> int:
        try:
            time.tzset()
        except AttributeError:
            pass
        raw_offset_seconds_east = -int(time.timezone)
        raw_offset_ms = raw_offset_seconds_east * 1000
        return int((raw_offset_ms * 2) / 3600) & 0xFF

    def _handle_disconnect(self, _client: BleakClientWithServiceCache) -> None:
        self._client = None
        self._write_char = None
        self._k1 = None
        self._session_iv = None

        for future in self._pending.values():
            if not future.done():
                future.cancel()
        self._pending.clear()

        if self._disconnected_callback is not None:
            self._disconnected_callback()
