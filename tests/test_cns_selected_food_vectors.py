"""Captured CNS-R002S-S selected-food protocol vectors."""

from __future__ import annotations

import importlib.util
from pathlib import Path
import sys
import types

ROOT = Path(__file__).resolve().parents[1]
COMPONENT = ROOT / "custom_components" / "ha_vesync_bt"
PROTOCOL = COMPONENT / "protocol"
DEVICES = COMPONENT / "devices"
PACKAGE = "_cns_selected_food_testpkg"

# The parser itself has no Bluetooth dependency. Stub the runtime-only imports so
# CI can validate captured device vectors without installing Home Assistant/Bleak.
bleak_mod = types.ModuleType("bleak")
bleak_backends_mod = types.ModuleType("bleak.backends")
bleak_device_mod = types.ModuleType("bleak.backends.device")


class BLEDevice:
    """Test BLEDevice stub."""


bleak_device_mod.BLEDevice = BLEDevice
sys.modules["bleak"] = bleak_mod
sys.modules["bleak.backends"] = bleak_backends_mod
sys.modules["bleak.backends.device"] = bleak_device_mod

root_pkg = types.ModuleType(PACKAGE)
root_pkg.__path__ = [str(COMPONENT)]
sys.modules[PACKAGE] = root_pkg

protocol_pkg = types.ModuleType(f"{PACKAGE}.protocol")
protocol_pkg.__path__ = [str(PROTOCOL)]
sys.modules[f"{PACKAGE}.protocol"] = protocol_pkg

devices_pkg = types.ModuleType(f"{PACKAGE}.devices")
devices_pkg.__path__ = [str(DEVICES)]
sys.modules[f"{PACKAGE}.devices"] = devices_pkg


def _load(fq_name: str, path: Path):
    spec = importlib.util.spec_from_file_location(fq_name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[fq_name] = module
    spec.loader.exec_module(module)
    return module


_load(f"{PACKAGE}.protocol.nutrition", PROTOCOL / "nutrition.py")
_load(f"{PACKAGE}.protocol.models", PROTOCOL / "models.py")

vsv3_stub = types.ModuleType(f"{PACKAGE}.protocol.vsv3")


class VSV3Transport:
    """Import-only transport stub."""


vsv3_stub.VSV3Transport = VSV3Transport
sys.modules[f"{PACKAGE}.protocol.vsv3"] = vsv3_stub

device = _load(
    f"{PACKAGE}.devices.cns_r002s_s",
    DEVICES / "cns_r002s_s.py",
)

# Captured live on 2026-09-10 by v31r2. Every payload was emitted immediately
# after physical LEFT/RIGHT navigation + SET, with nothing placed on the scale.
# The accented vector proves the first byte counts UTF-8 bytes, not characters.
VECTORS = (
    (
        "Banane",
        "0642616e616e65e803007a03000b0000030000010000000000e500001a00007a00000000000a0000030000",
        89.0,
        1.1,
    ),
    (
        "Hühnchenbrust",
        "0e48c3bc686e6368656e6272757374e803007206003601002400000a0000000000000000000000000000520300e402000a0000",
        165.0,
        31.0,
    ),
    (
        "Blaubeere",
        "09426c61756265657265e803004c02000000000000000000000000009300000000004a0000000000000000000000",
        58.8,
        0.0,
    ),
    (
        "Avocado",
        "0741766f6361646fe80300400600140000930000150000000000550000430000060000000000460000050000",
        160.0,
        2.0,
    ),
    (
        "Ei",
        "024569e803009605007e0000600000200000600000080000000000040000880e008c0500120000",
        143.0,
        12.6,
    ),
)


def test_selected_food_live_vectors() -> None:
    """Parse every captured 0x4445 payload exactly at its byte boundaries."""
    for name, raw_hex, calories, protein in VECTORS:
        payload = bytes.fromhex(raw_hex)
        parsed = device.CnsR002sDevice._parse_selected_food(payload)

        assert payload[0] == len(name.encode("utf-8"))
        assert len(payload) == 1 + payload[0] + 36
        assert parsed.name == name
        assert parsed.daily_food_weight_g == 100.0
        assert parsed.nutrition.calories_kcal == calories
        assert parsed.nutrition.protein_g == protein


def test_selected_food_utf8_length_is_bytes() -> None:
    """The live Hühnchenbrust payload declares UTF-8 byte length 14."""
    name = "Hühnchenbrust"
    assert len(name) == 13
    assert len(name.encode("utf-8")) == 14
    assert bytes.fromhex(VECTORS[1][1])[0] == 14
