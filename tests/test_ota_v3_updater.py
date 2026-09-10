"""Mocked state-machine tests for BT_ETEKCITY_V3."""

from __future__ import annotations

import asyncio
import importlib.util
from pathlib import Path
import sys
import types

ROOT = Path(__file__).resolve().parents[1]
PROTOCOL = ROOT / "custom_components" / "ha_vesync_bt" / "protocol"
PACKAGE = "_ota_protocol_testpkg"

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


frame_mod = _load("frame")
ota = _load("ota_v3")
updater_mod = _load("ota_v3_updater")


class FakeTransport:
    """Minimal device-driven transport simulator."""

    def __init__(
        self,
        *,
        firmware_size: int,
        max_chunk: int = 4,
        initial_status: int = 0,
        load_status: int = 0,
        final_status: int = 0,
        first_offset: int = 0,
        first_data_key_type: int = 1,
    ) -> None:
        self.firmware_size = firmware_size
        self.max_chunk = max_chunk
        self.initial_status = initial_status
        self.load_status = load_status
        self.final_status = final_status
        self.first_offset = first_offset
        self.first_data_key_type = first_data_key_type
        self.listeners = []
        self.requests = []
        self.sent = []
        self.next_sequence = 7
        self._first_data_emitted = False

    def add_frame_listener(self, callback) -> None:
        self.listeners.append(callback)

    def remove_frame_listener(self, callback) -> None:
        self.listeners.remove(callback)

    async def request(self, command, payload=b"", **kwargs):
        self.requests.append((command, payload, kwargs))
        if self.initial_status == 0:
            asyncio.get_running_loop().call_soon(
                self._emit,
                ota.CMD_OTA_DATA,
                self.first_offset.to_bytes(4, "little"),
                self.next_sequence,
                self.first_data_key_type,
            )
        return (
            bytes(9)
            + bytes([self.initial_status])
            + self.max_chunk.to_bytes(2, "little")
        )

    async def send_frame(self, command, payload=b"", **kwargs) -> None:
        self.sent.append((command, payload, kwargs))
        sequence = kwargs["sequence"]

        if command == ota.CMD_OTA_DATA:
            chunk_len = int.from_bytes(payload[5:7], "little")
            offset = int.from_bytes(payload[1:5], "little")
            next_offset = offset + chunk_len
            self.next_sequence = (sequence + 1) & 0xFF
            if next_offset < self.firmware_size:
                asyncio.get_running_loop().call_soon(
                    self._emit,
                    ota.CMD_OTA_DATA,
                    next_offset.to_bytes(4, "little"),
                    self.next_sequence,
                    1,
                )
            else:
                asyncio.get_running_loop().call_soon(
                    self._emit,
                    ota.CMD_OTA_LOAD_RESULT,
                    bytes([self.load_status, 1, 0]),
                    self.next_sequence,
                    0,
                )
        elif command == ota.CMD_OTA_LOAD_RESULT and self.load_status == 0:
            self.next_sequence = (sequence + 1) & 0xFF
            asyncio.get_running_loop().call_soon(
                self._emit,
                ota.CMD_OTA_UPDATE_RESULT,
                bytes([self.final_status]),
                self.next_sequence,
                0,
            )

    def _emit(self, command, payload, sequence, key_type) -> None:
        frame = frame_mod.VSV3Frame(
            flags=0x03,
            sequence=sequence,
            command=command,
            key_type=key_type,
            payload=payload,
            raw=b"",
        )
        for callback in tuple(self.listeners):
            callback(frame, payload)


def test_complete_device_driven_transfer() -> None:
    async def _run() -> None:
        firmware = bytes(range(10))
        transport = FakeTransport(
            firmware_size=len(firmware),
            max_chunk=4,
        )
        progress = []
        updater = updater_mod.OtaV3Updater(
            transport,
            progress_callback=lambda done, total: progress.append(
                (done, total)
            ),
        )

        result = await updater.update(
            firmware,
            plugin_name="scale",
            firmware_version="1.2.3",
            last_component=True,
        )

        assert result.bytes_total == 10
        assert result.load_result is not None
        assert result.load_result.successful
        assert result.load_result.burn_time_seconds == 1
        assert result.final_result.successful
        assert progress == [(0, 10), (4, 10), (8, 10)]

        assert len(transport.requests) == 1
        command, _, kwargs = transport.requests[0]
        assert command == ota.CMD_OTA_REQUEST
        assert kwargs["sequence"] == 0
        assert kwargs["flags"] == 0x23
        assert kwargs["key_type"] == 1
        assert kwargs["timeout"] == 3.0

        assert [item[0] for item in transport.sent] == [
            ota.CMD_OTA_DATA,
            ota.CMD_OTA_DATA,
            ota.CMD_OTA_DATA,
            ota.CMD_OTA_LOAD_RESULT,
            ota.CMD_OTA_UPDATE_RESULT,
        ]
        assert [item[2]["sequence"] for item in transport.sent] == [
            7,
            8,
            9,
            10,
            11,
        ]
        assert all(item[2]["flags"] == 0x13 for item in transport.sent)
        assert all(item[2]["key_type"] == 1 for item in transport.sent)
        assert transport.listeners == []

    asyncio.run(_run())


def test_device_k0_data_request_gets_plain_k0_reply() -> None:
    async def _run() -> None:
        firmware = b"abcd"
        transport = FakeTransport(
            firmware_size=len(firmware),
            max_chunk=4,
            first_data_key_type=0,
        )
        updater = updater_mod.OtaV3Updater(transport)

        await updater.update(
            firmware,
            plugin_name="scale",
            firmware_version="1.2.3",
            last_component=False,
        )

        assert transport.sent[0][0] == ota.CMD_OTA_DATA
        assert transport.sent[0][2]["key_type"] == 0
        assert transport.sent[-2][2]["key_type"] == 1
        assert transport.sent[-1][2]["key_type"] == 1

    asyncio.run(_run())


def test_initial_rejection_removes_listener() -> None:
    async def _run() -> None:
        transport = FakeTransport(
            firmware_size=4,
            initial_status=2,
        )
        updater = updater_mod.OtaV3Updater(transport)

        try:
            await updater.update(
                b"abcd",
                plugin_name="scale",
                firmware_version="1.2.3",
                last_component=True,
            )
        except updater_mod.OtaV3RejectedError as err:
            assert "status 2" in str(err)
        else:
            raise AssertionError("initial rejection must fail")

        assert transport.sent == []
        assert transport.listeners == []

    asyncio.run(_run())


def test_load_failure_is_acknowledged_before_error() -> None:
    async def _run() -> None:
        transport = FakeTransport(
            firmware_size=4,
            max_chunk=4,
            load_status=1,
        )
        updater = updater_mod.OtaV3Updater(transport)

        try:
            await updater.update(
                b"abcd",
                plugin_name="scale",
                firmware_version="1.2.3",
                last_component=True,
            )
        except updater_mod.OtaV3TransferError as err:
            assert "0x8032" in str(err)
        else:
            raise AssertionError("load failure must fail")

        assert [item[0] for item in transport.sent] == [
            ota.CMD_OTA_DATA,
            ota.CMD_OTA_LOAD_RESULT,
        ]
        assert transport.listeners == []

    asyncio.run(_run())


def test_non_sequential_device_offset_aborts() -> None:
    async def _run() -> None:
        transport = FakeTransport(
            firmware_size=8,
            max_chunk=4,
            first_offset=4,
        )
        updater = updater_mod.OtaV3Updater(transport)

        try:
            await updater.update(
                b"abcdefgh",
                plugin_name="scale",
                firmware_version="1.2.3",
                last_component=True,
            )
        except updater_mod.OtaV3TransferError as err:
            assert "non-sequential" in str(err)
        else:
            raise AssertionError("non-sequential request must fail")

        assert transport.sent == []
        assert transport.listeners == []

    asyncio.run(_run())
