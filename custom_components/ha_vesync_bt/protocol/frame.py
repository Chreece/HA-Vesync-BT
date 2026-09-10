"""VeSync VSV3 physical framing."""

from __future__ import annotations

from dataclasses import dataclass

VSV3_HEADER = 0xA5
DEFAULT_FLAGS = 0x23
DEFAULT_COMMAND_VERSION = 1


@dataclass(frozen=True, slots=True)
class VSV3Frame:
    """Decoded VSV3 frame."""

    flags: int
    sequence: int
    command: int
    key_type: int
    payload: bytes
    raw: bytes

    @property
    def is_response(self) -> bool:
        """Return whether this frame is a response."""
        return bool(self.flags & 0x10)

    @property
    def checksum_ok(self) -> bool:
        """Return whether the frame checksum is valid."""
        return checksum_ok(self.raw)


def checksum_ok(frame: bytes) -> bool:
    """Validate the VSV3 physical checksum."""
    return (sum(frame) & 0xFF) == 0xFF


def checksum_byte(frame_with_zero_checksum: bytes | bytearray) -> int:
    """Calculate byte 5 for a frame whose checksum byte is currently zero."""
    return (0xFF - (sum(frame_with_zero_checksum) & 0xFF)) & 0xFF


def build_frame(
    *,
    command: int,
    sequence: int,
    payload: bytes,
    key_type: int,
    flags: int = DEFAULT_FLAGS,
    command_version: int = DEFAULT_COMMAND_VERSION,
    sub_index: int = 0,
) -> bytes:
    """Build one complete physical VSV3 frame."""
    length_field = 5 + len(payload)
    frame = bytearray(11 + len(payload))
    frame[0] = VSV3_HEADER
    frame[1] = flags & 0xFF
    frame[2] = sequence & 0xFF
    frame[3:5] = length_field.to_bytes(2, "little")
    frame[5] = 0
    frame[6] = command_version & 0xFF
    frame[7:9] = command.to_bytes(2, "little")
    frame[9] = sub_index & 0xFF
    frame[10] = key_type & 0xFF
    frame[11:] = payload
    frame[5] = checksum_byte(frame)
    return bytes(frame)


def pop_frames(buffer: bytearray) -> list[bytes]:
    """Pop all complete VSV3 physical frames from an RX buffer."""
    frames: list[bytes] = []
    while buffer:
        try:
            start = buffer.index(VSV3_HEADER)
        except ValueError:
            buffer.clear()
            break

        if start:
            del buffer[:start]

        if len(buffer) < 6:
            break

        length_field = int.from_bytes(buffer[3:5], "little")
        total = length_field + 6
        if total < 11 or total > 8192:
            del buffer[0]
            continue

        if len(buffer) < total:
            break

        frames.append(bytes(buffer[:total]))
        del buffer[:total]

    return frames


def decode_frame(raw: bytes) -> VSV3Frame:
    """Decode a complete VSV3 physical frame without decrypting its payload."""
    if len(raw) < 11:
        raise ValueError("VSV3 frame is too short")
    if raw[0] != VSV3_HEADER:
        raise ValueError("VSV3 frame does not start with 0xA5")

    expected_len = int.from_bytes(raw[3:5], "little") + 6
    if len(raw) != expected_len:
        raise ValueError(
            f"VSV3 frame length mismatch: got {len(raw)}, expected {expected_len}"
        )

    return VSV3Frame(
        flags=raw[1],
        sequence=raw[2],
        command=int.from_bytes(raw[7:9], "little"),
        key_type=raw[10],
        payload=raw[11:],
        raw=raw,
    )
