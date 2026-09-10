"""Pure vectors for the BT_ETEKCITY_V3 OTA codec."""

from __future__ import annotations

import importlib.util
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
PROTOCOL = ROOT / "custom_components" / "ha_vesync_bt" / "protocol"


def _load(name: str):
    spec = importlib.util.spec_from_file_location(name, PROTOCOL / f"{name}.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


ota = _load("ota_v3")
frame = _load("frame")


def test_ota_v3_initial_payload_vector() -> None:
    payload = ota.build_initial_payload(
        plugin_name="scale",
        firmware_version="1.2.3",
        file_size=0x12345678,
        last_component=True,
    )
    assert payload.hex() == "7363616c650000000000020302017856341200ff"


def test_ota_v3_initial_payload_non_last_component() -> None:
    payload = ota.build_initial_payload(
        plugin_name="abcdefghi",
        firmware_version="127.0.1",
        file_size=1,
        last_component=False,
    )
    assert payload.hex() == "616263646566676869000201007f0100000001ff"


def test_ota_v3_signed_java_byte_version_vector() -> None:
    payload = ota.build_initial_payload(
        plugin_name="scale",
        firmware_version="-1.2.3",
        file_size=1,
        last_component=True,
    )
    assert payload[13] == 0xFF


def test_ota_v3_data_payload_full_and_short_chunks() -> None:
    firmware = bytes(range(12))

    full = ota.build_data_payload(
        firmware,
        offset=2,
        max_chunk_size=4,
    )
    assert full.hex() == "0002000000040002030405"

    short = ota.build_data_payload(
        firmware,
        offset=10,
        max_chunk_size=4,
    )
    assert short.hex() == "010a00000002000a0b"


def test_ota_v3_initial_response_parser() -> None:
    response = ota.parse_initial_response(
        bytes.fromhex("00112233445566778800f401")
    )
    assert response.prefix == bytes.fromhex("001122334455667788")
    assert response.status == ota.OtaV3UpdatePermission.CAN_UPDATE
    assert response.can_update
    assert response.max_chunk_size == 500


def test_ota_v3_device_request_parsers() -> None:
    assert ota.parse_data_request(bytes.fromhex("78563412")) == 0x12345678

    load = ota.parse_load_result(
        bytes.fromhex("003412"),
        last_component=True,
    )
    assert load.successful
    assert load.burn_time_seconds == 0x1234

    final = ota.parse_final_result(bytes.fromhex("00"))
    assert final.successful


def test_ota_v3_reply_flags_sequence_and_key_policy() -> None:
    firmware = bytes(range(16))

    data_plain = ota.build_data_reply(
        firmware,
        offset=0,
        max_chunk_size=8,
        sequence=0x2A,
        incoming_key_type=0,
    )
    assert data_plain.flags == 0x13
    assert data_plain.sequence == 0x2A
    assert data_plain.key_type == 0

    data_k1 = ota.build_data_reply(
        firmware,
        offset=0,
        max_chunk_size=8,
        sequence=0x2A,
        incoming_key_type=1,
    )
    assert data_k1.key_type == 1

    load_ack = ota.build_load_ack(sequence=0x2A, incoming_key_type=0)
    final_ack = ota.build_final_ack(sequence=0x7F, incoming_key_type=0)
    assert load_ack.key_type == 1
    assert final_ack.key_type == 1


def test_ota_v3_empty_ack_physical_frame_vectors() -> None:
    load = ota.build_load_ack(sequence=0x2A, incoming_key_type=0)
    load_frame = frame.build_frame(
        command=load.command,
        sequence=load.sequence,
        payload=load.payload,
        key_type=load.key_type,
        flags=load.flags,
        command_version=load.command_version,
        sub_index=load.sub_index,
    )
    assert load_frame.hex() == "a5132a0500640132800001"
    assert frame.checksum_ok(load_frame)

    final = ota.build_final_ack(sequence=0x7F, incoming_key_type=1)
    final_frame = frame.build_frame(
        command=final.command,
        sequence=final.sequence,
        payload=final.payload,
        key_type=final.key_type,
        flags=final.flags,
        command_version=final.command_version,
        sub_index=final.sub_index,
    )
    assert final_frame.hex() == "a5137f05000e0133800001"
    assert frame.checksum_ok(final_frame)


def test_ota_v3_validation() -> None:
    invalid_initial_values = (
        {
            "plugin_name": "0123456789",
            "firmware_version": "1.2.3",
            "file_size": 1,
            "last_component": True,
        },
        {
            "plugin_name": "scale",
            "firmware_version": "128.2.3",
            "file_size": 1,
            "last_component": True,
        },
        {
            "plugin_name": "scale",
            "firmware_version": "1.2.3",
            "file_size": 0x80000000,
            "last_component": True,
        },
    )
    for values in invalid_initial_values:
        try:
            ota.build_initial_payload(**values)
        except ValueError:
            pass
        else:
            raise AssertionError(f"expected validation failure for {values}")

    try:
        ota.build_data_payload(b"abc", offset=4, max_chunk_size=1)
    except ValueError:
        pass
    else:
        raise AssertionError("out-of-range offset must fail")
