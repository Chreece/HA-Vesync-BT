"""Pure helpers for the VeSync BT_ETEKCITY_V3 firmware protocol.

The CNS-R002S-S selects this protocol through FirmwareUpdateType.BT_ETEKCITY_V3.
This module intentionally contains no BLE I/O. It mirrors the proven VeSync
request/state-machine byte layout so transport integration can be validated
separately before firmware writes are exposed in Home Assistant.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum

CMD_OTA_DATA = 0x8031
CMD_OTA_LOAD_RESULT = 0x8032
CMD_OTA_UPDATE_RESULT = 0x8033
CMD_OTA_REQUEST = 0x8034

OTA_INITIAL_FLAGS = 0x23
OTA_REPLY_FLAGS = 0x13
OTA_COMMAND_VERSION = 1
OTA_SUB_INDEX = 0
OTA_INITIAL_SEQUENCE = 0
OTA_K0 = 0
OTA_K1 = 1

PLUGIN_FIELD_LENGTH = 9
INITIAL_PAYLOAD_LENGTH = 20
JAVA_BYTE_MIN = -0x80
JAVA_BYTE_MAX = 0x7F
MAX_JAVA_INT_FILE_SIZE = 0x7FFFFFFF


class OtaV3UpdatePermission(IntEnum):
    """Status byte returned at offset 9 of the 0x8034 response."""

    CAN_UPDATE = 0
    NOT_SUPPORTED = 1
    CANNOT_UPDATE = 2
    SYSTEM_ERROR = 3


class OtaV3LoadStatus(IntEnum):
    """First byte of a 0x8032 device request."""

    SUCCESS = 0
    FAIL = 1
    TIMEOUT = 2


class OtaV3UpdateStatus(IntEnum):
    """First byte of a 0x8033 device request."""

    SUCCESS = 0
    FAIL = 1
    CHECK_FAIL = 2


@dataclass(frozen=True, slots=True)
class OtaV3Command:
    """One logical VSV3 command emitted by the OTA state machine."""

    command: int
    sequence: int
    payload: bytes
    key_type: int
    flags: int
    command_version: int = OTA_COMMAND_VERSION
    sub_index: int = OTA_SUB_INDEX


@dataclass(frozen=True, slots=True)
class OtaV3InitialResponse:
    """Parsed 0x8034 payload."""

    prefix: bytes
    status: int
    max_chunk_size: int

    @property
    def can_update(self) -> bool:
        """Return whether the device accepted the update request."""

        return self.status == OtaV3UpdatePermission.CAN_UPDATE


@dataclass(frozen=True, slots=True)
class OtaV3LoadResult:
    """Parsed 0x8032 payload."""

    status: int
    burn_time_seconds: int | None

    @property
    def successful(self) -> bool:
        """Return whether the device loaded the firmware data."""

        return self.status == OtaV3LoadStatus.SUCCESS


@dataclass(frozen=True, slots=True)
class OtaV3FinalResult:
    """Parsed 0x8033 payload."""

    status: int

    @property
    def successful(self) -> bool:
        """Return whether the device reports a successful firmware update."""

        return self.status == OtaV3UpdateStatus.SUCCESS


def build_initial_payload(
    *,
    plugin_name: str,
    firmware_version: str,
    file_size: int,
    last_component: bool,
) -> bytes:
    """Build the exact 20-byte body used by VeSync for command 0x8034."""

    plugin = plugin_name.encode("utf-8")
    if len(plugin) > PLUGIN_FIELD_LENGTH:
        raise ValueError("plugin_name must encode to at most 9 bytes")

    version_parts = firmware_version.split(".")
    if len(version_parts) != 3:
        raise ValueError(
            "firmware_version must contain exactly three numeric parts"
        )

    try:
        major, minor, patch = (int(part, 10) for part in version_parts)
    except ValueError as err:
        raise ValueError(
            "firmware_version must contain exactly three numeric parts"
        ) from err

    # VeSync uses java.lang.Byte.parseByte() for each component.
    if any(
        part < JAVA_BYTE_MIN or part > JAVA_BYTE_MAX
        for part in (major, minor, patch)
    ):
        raise ValueError(
            "firmware version components must fit java.lang.Byte"
        )

    # The source obtains this from FileInputStream.available(), which is int.
    if file_size < 0 or file_size > MAX_JAVA_INT_FILE_SIZE:
        raise ValueError("file_size must fit a non-negative Java int")

    payload = bytearray(INITIAL_PAYLOAD_LENGTH)
    payload[: len(plugin)] = plugin

    payload[9] = 0
    payload[10] = 2

    # Version is encoded patch, minor, major.
    payload[11] = patch & 0xFF
    payload[12] = minor & 0xFF
    payload[13] = major & 0xFF
    payload[14:18] = file_size.to_bytes(4, "little")

    # Source uses 0 for the last update component and 1 otherwise.
    payload[18] = 0 if last_component else 1
    payload[19] = 0xFF
    return bytes(payload)


def build_data_payload(
    firmware: bytes,
    *,
    offset: int,
    max_chunk_size: int,
) -> bytes:
    """Build a 0x8031 response payload for the device-requested file offset."""

    if offset < 0 or offset > len(firmware):
        raise ValueError("offset is outside the firmware image")
    if max_chunk_size <= 0 or max_chunk_size > 0xFFFF:
        raise ValueError("max_chunk_size must be between 1 and 65535")

    chunk = firmware[offset : offset + max_chunk_size]
    chunk_len = len(chunk)

    payload = bytearray(7 + chunk_len)

    # Exact source behavior: 0 for a full device-sized chunk, 1 for a shorter
    # chunk (including a possible zero-length terminal request).
    payload[0] = 0 if chunk_len == max_chunk_size else 1
    payload[1:5] = offset.to_bytes(4, "little")
    payload[5:7] = chunk_len.to_bytes(2, "little")
    payload[7:] = chunk
    return bytes(payload)


def parse_initial_response(payload: bytes) -> OtaV3InitialResponse:
    """Parse the fields VeSync consumes from a 0x8034 device response."""

    if len(payload) < 12:
        raise ValueError("0x8034 response payload is shorter than 12 bytes")
    return OtaV3InitialResponse(
        prefix=payload[:9],
        status=payload[9],
        max_chunk_size=int.from_bytes(payload[10:12], "little"),
    )


def parse_data_request(payload: bytes) -> int:
    """Return the little-endian firmware offset requested by command 0x8031."""

    if len(payload) < 4:
        raise ValueError("0x8031 request payload is shorter than 4 bytes")
    return int.from_bytes(payload[:4], "little")


def parse_load_result(
    payload: bytes,
    *,
    last_component: bool,
) -> OtaV3LoadResult:
    """Parse command 0x8032 using the fields consumed by the VeSync client."""

    if not payload:
        raise ValueError("0x8032 request payload is empty")

    burn_time_seconds = None
    if last_component and len(payload) >= 3:
        burn_time_seconds = int.from_bytes(payload[1:3], "little")

    return OtaV3LoadResult(
        status=payload[0],
        burn_time_seconds=burn_time_seconds,
    )


def parse_final_result(payload: bytes) -> OtaV3FinalResult:
    """Parse command 0x8033 using the field consumed by the VeSync client."""

    if not payload:
        raise ValueError("0x8033 request payload is empty")
    return OtaV3FinalResult(status=payload[0])


def _reply_key_type(command: int, incoming_key_type: int) -> int:
    """Mirror LOW_SECURITY key selection used by the VeSync VSV3 serializer."""

    if command == CMD_OTA_DATA and incoming_key_type == OTA_K0:
        return OTA_K0
    return OTA_K1


def build_initial_command(
    *,
    plugin_name: str,
    firmware_version: str,
    file_size: int,
    last_component: bool,
) -> OtaV3Command:
    """Build the logical first 0x8034 command."""

    return OtaV3Command(
        command=CMD_OTA_REQUEST,
        sequence=OTA_INITIAL_SEQUENCE,
        payload=build_initial_payload(
            plugin_name=plugin_name,
            firmware_version=firmware_version,
            file_size=file_size,
            last_component=last_component,
        ),
        key_type=OTA_K1,
        flags=OTA_INITIAL_FLAGS,
    )


def build_data_reply(
    firmware: bytes,
    *,
    offset: int,
    max_chunk_size: int,
    sequence: int,
    incoming_key_type: int,
) -> OtaV3Command:
    """Build the response-style 0x8031 command for one requested offset."""

    _validate_sequence(sequence)
    return OtaV3Command(
        command=CMD_OTA_DATA,
        sequence=sequence,
        payload=build_data_payload(
            firmware,
            offset=offset,
            max_chunk_size=max_chunk_size,
        ),
        key_type=_reply_key_type(CMD_OTA_DATA, incoming_key_type),
        flags=OTA_REPLY_FLAGS,
    )


def build_load_ack(*, sequence: int, incoming_key_type: int) -> OtaV3Command:
    """Build the empty response-style acknowledgement for command 0x8032."""

    _validate_sequence(sequence)
    return OtaV3Command(
        command=CMD_OTA_LOAD_RESULT,
        sequence=sequence,
        payload=b"",
        key_type=_reply_key_type(
            CMD_OTA_LOAD_RESULT, incoming_key_type
        ),
        flags=OTA_REPLY_FLAGS,
    )


def build_final_ack(*, sequence: int, incoming_key_type: int) -> OtaV3Command:
    """Build the empty response-style acknowledgement for command 0x8033."""

    _validate_sequence(sequence)
    return OtaV3Command(
        command=CMD_OTA_UPDATE_RESULT,
        sequence=sequence,
        payload=b"",
        key_type=_reply_key_type(
            CMD_OTA_UPDATE_RESULT, incoming_key_type
        ),
        flags=OTA_REPLY_FLAGS,
    )


def _validate_sequence(sequence: int) -> None:
    if sequence < 0 or sequence > 0xFF:
        raise ValueError("sequence must fit one byte")
