"""Protocol vector tests that do not require Home Assistant."""

from __future__ import annotations

import hashlib
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


frame = _load("frame")
crypto = _load("crypto")
nutrition = _load("nutrition")


def test_vsv3_4201_frame_vector() -> None:
    payload = bytes.fromhex(
        "436aa16a"
        "d0"
        "06"
        "05e01508eace"
        "27ac"
        "1d"
        "1087"
    )
    built = frame.build_frame(
        command=0x4201,
        sequence=0,
        payload=payload,
        key_type=0,
    )
    assert built.hex() == (
        "a5230016000e01014200"
        "00"
        "436aa16ad00605e01508eace27ac1d1087"
    )
    assert frame.checksum_ok(built)


def test_vsv3_dh_k1_vector() -> None:
    prime = 44071
    base = 29
    private = 13
    device_public = 26808
    mac_reversed = bytes.fromhex("05e01508eace")

    assert pow(base, private, prime) == 34576
    shared = pow(device_public, private, prime)
    assert shared == 8304

    k1 = crypto.derive_k1(shared, mac_reversed)
    assert k1.hex() == "cae40bb1e8cfbbe9174196c11573e010"
    assert hashlib.sha256(k1).hexdigest() == (
        "f6ff6a688fe4a8c4463a2f4b6e8e89c"
        "168ba22fb1fb2d6555ff07135b3e7a18a"
    )


def test_nutrition_roundtrip() -> None:
    value = nutrition.Nutrition(
        calories_kcal=123.4,
        protein_g=5.6,
        total_fat_g=7.8,
        saturated_fat_g=1.1,
        trans_fat_g=0.2,
        total_carbs_g=12.3,
        dietary_fiber_g=3.4,
        sugars_g=4.5,
        cholesterol_mg=6.7,
        sodium_mg=89.0,
        iron_mg=2.3,
    )
    encoded = nutrition.encode_nutrition(value)
    assert len(encoded) == 33
    assert nutrition.decode_nutrition(encoded) == value
