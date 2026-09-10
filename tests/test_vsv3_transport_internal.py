"""Internal VSV3 transport tests for explicit OTA frames."""

from __future__ import annotations

import asyncio
import importlib.util
from pathlib import Path
import sys
import types

ROOT = Path(__file__).resolve().parents[1]
PROTOCOL = ROOT / "custom_components" / "ha_vesync_bt" / "protocol"
PACKAGE = "_vsv3_transport_testpkg"

# Stub BLE imports; these tests exercise framing/dispatch only.
bleak_mod = types.ModuleType("bleak")
bleak_backends_mod = types.ModuleType("bleak.backends")
bleak_device_mod = types.ModuleType("bleak.backends.device")


class BLEDevice:
    """Test BLEDevice stub."""


bleak_device_mod.BLEDevice = BLEDevice
sys.modules["bleak"] = bleak_mod
sys.modules["bleak.backends"] = bleak_backends_mod
sys.modules["bleak.backends.device"] = bleak_device_mod

retry_mod = types.ModuleType("bleak_retry_connector")


class BleakClientWithServiceCache:
    """Test Bleak client stub."""


async def establish_connection(*_args, **_kwargs):
    """Fail if a unit test accidentally attempts a real connection."""
    raise AssertionError("connection helper must not run in this unit test")


retry_mod.BleakClientWithServiceCache = BleakClientWithServiceCache
retry_mod.establish_connection = establish_connection
sys.modules["bleak_retry_connector"] = retry_mod

pkg = types.ModuleType(PACKAGE)
pkg.__path__ = [str(PROTOCOL)]
sys.modules[PACKAGE] = pkg


def _load(name: str):
    fq_name = f"{PACKAGE}.{name}"
    spec = importlib.util.spec_from_file_location(
        fq_name,
        PROTOCOL / f"{name}.py",
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[fq_name] = module
    spec.loader.exec_module(module)
    return module


crypto = _load("crypto")
_load("exceptions")
frame_mod = _load("frame")
vsv3 = _load("vsv3")


class FakeChar:
    """Write characteristic stub."""

    max_write_without_response_size = 244


class FakeClient:
    """Connected client that can inject one encrypted response."""

    def __init__(self, transport=None) -> None:
        self.is_connected = True
        self.mtu_size = 247
        self.transport = transport
        self.writes = []
        self.response_payload = None

    async def write_gatt_char(self, _char, data, *, response) -> None:
        assert response is False
        raw = bytes(data)
        self.writes.append(raw)

        if self.response_payload is None:
            return

        response_payload = self.response_payload
        self.response_payload = None
        decoded = frame_mod.decode_frame(raw)
        encrypted = crypto.aes_encrypt(
            self.transport._k1,
            self.transport._session_iv,
            response_payload,
        )
        reply = frame_mod.build_frame(
            command=decoded.command,
            sequence=decoded.sequence,
            payload=encrypted,
            key_type=1,
            flags=0x13,
        )
        self.transport._notification_handler(None, bytearray(reply))


def _transport():
    transport = vsv3.VSV3Transport("CE:EA:08:15:E0:05")
    client = FakeClient(transport)
    transport._client = client
    transport._write_char = FakeChar()
    transport._k1 = bytes(range(16))
    transport._session_iv = bytes(range(16, 32))
    return transport, client


def test_explicit_empty_response_frame_vector() -> None:
    async def _run() -> None:
        transport, client = _transport()
        await transport.send_frame(
            0x8032,
            b"",
            key_type=1,
            sequence=0x2A,
            flags=0x13,
        )
        assert client.writes == [
            bytes.fromhex("a5132a0500640132800001")
        ]

    asyncio.run(_run())


def test_explicit_request_sequence_flags_and_listener_metadata() -> None:
    async def _run() -> None:
        transport, client = _transport()
        listener_events = []
        transport.add_frame_listener(
            lambda frame, payload: listener_events.append(
                (frame, payload)
            )
        )
        expected_response = bytes.fromhex(
            "001122334455667788000400"
        )
        client.response_payload = expected_response
        plaintext = bytes(range(20))

        response = await transport.request(
            0x8034,
            plaintext,
            key_type=1,
            timeout=1,
            sequence=0,
            flags=0x23,
            command_version=1,
            sub_index=0,
        )

        assert response == expected_response
        assert len(client.writes) == 1

        outbound = frame_mod.decode_frame(client.writes[0])
        assert outbound.flags == 0x23
        assert outbound.sequence == 0
        assert outbound.command == 0x8034
        assert outbound.key_type == 1
        assert crypto.aes_decrypt(
            transport._k1,
            transport._session_iv,
            outbound.payload,
        ) == plaintext

        assert len(listener_events) == 1
        inbound, payload = listener_events[0]
        assert inbound.flags == 0x13
        assert inbound.sequence == 0
        assert inbound.command == 0x8034
        assert inbound.key_type == 1
        assert payload == expected_response

    asyncio.run(_run())


def test_explicit_sequence_does_not_advance_normal_sequence() -> None:
    async def _run() -> None:
        transport, client = _transport()
        transport._sequence = 9

        await transport.send_frame(
            0x8032,
            b"",
            key_type=1,
            sequence=0x2A,
            flags=0x13,
        )
        assert transport._sequence == 9

        client.response_payload = b"\x00"
        await transport.request(
            0xA100,
            b"",
            key_type=1,
            timeout=1,
        )
        assert frame_mod.decode_frame(client.writes[-1]).sequence == 9
        assert transport._sequence == 10

    asyncio.run(_run())


def test_frame_listener_failure_does_not_block_pending_response() -> None:
    async def _run() -> None:
        transport, client = _transport()

        def broken_listener(_frame, _payload) -> None:
            raise RuntimeError("listener test")

        transport.add_frame_listener(broken_listener)
        client.response_payload = b"\x00"

        response = await transport.request(
            0xA100,
            b"",
            key_type=1,
            timeout=1,
        )
        assert response == b"\x00"

    asyncio.run(_run())
