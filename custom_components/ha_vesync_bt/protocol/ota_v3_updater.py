"""Internal BT_ETEKCITY_V3 firmware-update state machine.

This module is deliberately not exposed as a Home Assistant service or entity.
It implements only the reverse-engineered VeSync transfer behavior and is kept
separate from firmware discovery/download policy.
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from dataclasses import dataclass
from typing import Protocol

from .frame import VSV3Frame
from .ota_v3 import (
    CMD_OTA_DATA,
    CMD_OTA_LOAD_RESULT,
    CMD_OTA_UPDATE_RESULT,
    OtaV3Command,
    OtaV3FinalResult,
    OtaV3LoadResult,
    build_data_reply,
    build_final_ack,
    build_initial_command,
    build_load_ack,
    parse_data_request,
    parse_final_result,
    parse_initial_response,
    parse_load_result,
)

INITIAL_RESPONSE_TIMEOUT = 3.0
TRANSFER_INACTIVITY_TIMEOUT = 10.0
FINAL_ACK_DELAY = 0.020

FrameListener = Callable[[VSV3Frame, bytes], None]
ProgressCallback = Callable[[int, int], None]


class OtaV3Transport(Protocol):
    """Transport operations required by :class:`OtaV3Updater`."""

    async def request(
        self,
        command: int,
        payload: bytes = b"",
        *,
        key_type: int = 1,
        timeout: float = 6.0,
        response_optional: bool = False,
        sequence: int | None = None,
        flags: int = 0x23,
        command_version: int = 1,
        sub_index: int = 0,
    ) -> bytes:
        """Send a VSV3 request and await its matching response."""

    async def send_frame(
        self,
        command: int,
        payload: bytes = b"",
        *,
        key_type: int = 1,
        sequence: int,
        flags: int,
        command_version: int = 1,
        sub_index: int = 0,
    ) -> None:
        """Send one explicit VSV3 frame without awaiting a response."""

    def add_frame_listener(self, callback: FrameListener) -> None:
        """Register a decoded-frame listener."""

    def remove_frame_listener(self, callback: FrameListener) -> None:
        """Remove a decoded-frame listener."""


class OtaV3Error(Exception):
    """Base class for internal BT_ETEKCITY_V3 update failures."""


class OtaV3RejectedError(OtaV3Error):
    """The device rejected the initial firmware update request."""


class OtaV3TransferError(OtaV3Error):
    """The device reported a transfer/load/final update failure."""


class OtaV3TimeoutError(OtaV3Error):
    """The device stopped producing expected OTA traffic."""


@dataclass(frozen=True, slots=True)
class OtaV3UpdateResult:
    """Successful transfer result."""

    bytes_total: int
    load_result: OtaV3LoadResult | None
    final_result: OtaV3FinalResult


class OtaV3Updater:
    """Run one device-driven BT_ETEKCITY_V3 firmware transfer."""

    def __init__(
        self,
        transport: OtaV3Transport,
        *,
        progress_callback: ProgressCallback | None = None,
    ) -> None:
        self._transport = transport
        self._progress_callback = progress_callback

    async def update(
        self,
        firmware: bytes,
        *,
        plugin_name: str,
        firmware_version: str,
        last_component: bool,
    ) -> OtaV3UpdateResult:
        """Transfer one already-authorized firmware image.

        This method does not discover, download, authenticate, or select
        firmware. The caller must supply the exact official image/metadata.
        """

        if not firmware:
            raise ValueError("firmware image must not be empty")

        queue: asyncio.Queue[tuple[VSV3Frame, bytes]] = asyncio.Queue()

        def _listener(frame: VSV3Frame, payload: bytes) -> None:
            if frame.command in (
                CMD_OTA_DATA,
                CMD_OTA_LOAD_RESULT,
                CMD_OTA_UPDATE_RESULT,
            ):
                queue.put_nowait((frame, payload))

        # Register before 0x8034: the first 0x8031 may follow immediately.
        self._transport.add_frame_listener(_listener)
        try:
            initial = build_initial_command(
                plugin_name=plugin_name,
                firmware_version=firmware_version,
                file_size=len(firmware),
                last_component=last_component,
            )
            initial_payload = await self._transport.request(
                initial.command,
                initial.payload,
                key_type=initial.key_type,
                timeout=INITIAL_RESPONSE_TIMEOUT,
                sequence=initial.sequence,
                flags=initial.flags,
                command_version=initial.command_version,
                sub_index=initial.sub_index,
            )
            initial_response = parse_initial_response(initial_payload)
            if not initial_response.can_update:
                raise OtaV3RejectedError(
                    "device rejected 0x8034 update request "
                    f"with status {initial_response.status}"
                )
            if initial_response.max_chunk_size <= 0:
                raise OtaV3TransferError(
                    "device returned an invalid zero OTA chunk size"
                )

            wait_timeout = TRANSFER_INACTIVITY_TIMEOUT
            load_result: OtaV3LoadResult | None = None
            expected_offset = 0

            while True:
                frame, payload = await self._wait_for_device_frame(
                    queue,
                    wait_timeout,
                )

                if frame.command == CMD_OTA_DATA:
                    offset = parse_data_request(payload)
                    if offset != expected_offset:
                        raise OtaV3TransferError(
                            "device requested a non-sequential firmware offset: "
                            f"{offset}, expected {expected_offset}"
                        )

                    reply = build_data_reply(
                        firmware,
                        offset=offset,
                        max_chunk_size=initial_response.max_chunk_size,
                        sequence=frame.sequence,
                        incoming_key_type=frame.key_type,
                    )
                    self._report_progress(offset, len(firmware))
                    await self._send(reply)
                    expected_offset += len(reply.payload) - 7
                    wait_timeout = TRANSFER_INACTIVITY_TIMEOUT
                    continue

                if frame.command == CMD_OTA_LOAD_RESULT:
                    load_result = parse_load_result(
                        payload,
                        last_component=last_component,
                    )

                    # VeSync acknowledges 0x8032 before evaluating success.
                    await self._send(
                        build_load_ack(
                            sequence=frame.sequence,
                            incoming_key_type=frame.key_type,
                        )
                    )

                    if not load_result.successful:
                        raise OtaV3TransferError(
                            "device reported 0x8032 load failure "
                            f"with status {load_result.status}"
                        )

                    wait_timeout = TRANSFER_INACTIVITY_TIMEOUT
                    if (
                        last_component
                        and load_result.burn_time_seconds is not None
                    ):
                        wait_timeout += load_result.burn_time_seconds
                    continue

                final_result = parse_final_result(payload)

                # VeSync sleeps 20 ms before the empty 0x8033 acknowledgement.
                await asyncio.sleep(FINAL_ACK_DELAY)
                await self._send(
                    build_final_ack(
                        sequence=frame.sequence,
                        incoming_key_type=frame.key_type,
                    )
                )

                if not final_result.successful:
                    raise OtaV3TransferError(
                        "device reported 0x8033 update failure "
                        f"with status {final_result.status}"
                    )

                return OtaV3UpdateResult(
                    bytes_total=len(firmware),
                    load_result=load_result,
                    final_result=final_result,
                )
        finally:
            self._transport.remove_frame_listener(_listener)

    async def _send(self, command: OtaV3Command) -> None:
        await self._transport.send_frame(
            command.command,
            command.payload,
            key_type=command.key_type,
            sequence=command.sequence,
            flags=command.flags,
            command_version=command.command_version,
            sub_index=command.sub_index,
        )

    async def _wait_for_device_frame(
        self,
        queue: asyncio.Queue[tuple[VSV3Frame, bytes]],
        timeout: float,
    ) -> tuple[VSV3Frame, bytes]:
        try:
            return await asyncio.wait_for(queue.get(), timeout=timeout)
        except TimeoutError as err:
            raise OtaV3TimeoutError(
                f"no OTA device request received for {timeout:.3f} seconds"
            ) from err

    def _report_progress(self, transferred: int, total: int) -> None:
        if self._progress_callback is not None:
            self._progress_callback(transferred, total)
