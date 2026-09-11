# CNS-R002S-S protocol notes

This document contains only behavior currently used by HA-VeSync-BT or behavior
that has been reverse engineered far enough to preserve as non-exposed protocol
evidence.

## BLE

Observed device name:

```text
COSORI Nutrition Scale
```

VSV3 GATT:

```text
Service  FFF0
Notify   FFF1
Write    FFF2
Extra    FFF3
```

The physical test device negotiated ATT MTU 247. The client does not assume
that exact MTU; it splits writes using the active Bleak characteristic's
write-without-response size and `MTU - 3`.

## VSV3 physical frame

```text
byte 0      0xA5
byte 1      flags
byte 2      sequence
bytes 3-4   VSV3 length, little endian
byte 5      checksum
byte 6      command version
bytes 7-8   command ID, little endian
byte 9      sub-index
byte 10     key type
byte 11..   encrypted/plain payload
```

The physical frame length is `length_field + 6`.

Checksum:

```text
sum(all physical-frame bytes) & 0xFF == 0xFF
```

## VSV3 LOW_SECURITY handshake

### `0x4201`

The client generates:

- Prime: 40000..46340
- Base: 10..100
- Private exponent: 5..20
- DH public value: `pow(base, private, prime)`

Request payload:

```text
unix_time_le32
timezone_byte
mac_length = 6
reversed_raw_mac[6]
prime_le16
base_u8
client_public_le16
```

K1:

```text
SHA256(str(shared_secret) + "," + reversed_raw_mac)[:16]
```

### `0x4202`

A fresh 16-byte session IV is generated.

Bind plaintext:

```text
12
reversed_raw_mac[6]
16
session_iv[16]
```

The bind request is AES-CBC/PKCS7 encrypted with K1 and an all-zero IV.
Normal K1 traffic uses the negotiated session IV. VeSync's LOW_SECURITY source
identifies the default cipher mode as `CBC_PKCS5`; with AES's 16-byte block size
this is wire-compatible with the PKCS7 padding already proven by the live native
implementation.

K1, DH private values, shared secrets, and the session IV are never persisted.

## Commands currently implemented

| Command | Meaning |
| --- | --- |
| `0x4201` | VSV3 key negotiation |
| `0x4202` | VSV3 session bind |
| `0xA081` | Set timestamp |
| `0xA08A` | Query firmware |
| `0xA100` | Query battery |
| `0xA101` | Battery report |
| `0xA102` | Query standby timeout |
| `0xA104` | Set standby timeout |
| `0xA105` | Set brightness |
| `0xA106` | Query brightness |
| `0xA180` | Set current unit |
| `0xA181` | Query current unit |
| `0xA182` | Physical unit report |
| `0xA185` | Tare |
| `0xA186` | Tare report |
| `0xA187` | Live measurement report |
| `0xA188` | Query scale status |
| `0x4102` | Set enabled-unit mask |
| `0x4103` | Query enabled-unit mask |
| `0x4440` | Replace Quick Food list |
| `0x4441` | Add Quick Food |
| `0x4442` | Reorder / retain Quick Foods |
| `0x4443` | Query Quick Foods |
| `0x4444` | Set current app food context |
| `0x4445` | Selected Quick Food report |
| `0x4447` | Set language |
| `0x4448` | Query language |
| `0x444A` | LEFT / RIGHT / SET report |

Known but intentionally not exposed:

| Command | Status |
| --- | --- |
| `0x4446` | Offline-history query — exact parser known; controlled official-VeSync reconnect returned an empty response after the tested offline measurement |
| `0x444B` | History acknowledgement/delete — semantics known, but no stored record was produced by the tested unit/firmware |
| `0x444C` | Device-save lifecycle state — `00` while VeSync is backgrounded / save requested, `01` while foreground save is suppressed |
| `0xA087` | Factory reset — destructive, intentionally disabled |
| `0x8031` | BT_ETEKCITY_V3 firmware data response |
| `0x8032` | BT_ETEKCITY_V3 data-load result / acknowledgement |
| `0x8033` | BT_ETEKCITY_V3 final update result / acknowledgement |
| `0x8034` | BT_ETEKCITY_V3 initial update request |

## BT_ETEKCITY_V3 OTA

The CNS-R002S-S provider explicitly selects
`FirmwareUpdateType.BT_ETEKCITY_V3`. Static tracing proves the dispatch chain:

```text
FirmwareUpdateType.BT_ETEKCITY_V3
  -> FirmwareUpdateManager case 3
  -> lw0.d
  -> BtEtekcityV3FirmwareUpdateExecuteStep
  -> BtEtekcityV3OtaRequest
```

This is distinct from the KMP V4 command family `0x8035..0x8038`.

### Official firmware availability discovery

VeSync does not infer update availability from the local `0xA08A` version alone.
Static source tracing shows the CNS-R002S-S uses
`CheckFirmwareUpdateType.MAC_ID` and VeSync's firmware manager performs a cloud
upgrade check using the scale MAC address.

The decompiled app contains the request path:

```text
POST /cloud/v2/deviceManaged/getFirmwareUpdateInfoList
```

The request model is `UpgradeCheckRequest`, with the R002S-S MAC placed in its
`macIDList`. The returned `DeviceFirmware` data contains per-component firmware
metadata, including the currently/latest offered version, download metadata,
plugin/component identity, and upgrade level. `IFirmwareProvider.haveUpdate(mac)`
is driven from the cached result; an upgrade level other than `LEVEL_0` makes the
Nutrition Scale settings screen expose its red firmware-warning indicator.

A non-destructive official-app check on VeSync 5.9.60 (versionCode 782) captured
the actual `NutritionScaleSettingActivity` twice. The `Firmware Update` row was
visible in both snapshots but `sm_v_red_warning` was absent in both. No firmware
row was tapped, no OTA command was sent by the probe, and no firmware file was
requested. This proves that the official app currently reports
`haveUpdate(scaleMac) == false` for the tested device/account state.

Accordingly, there is currently no VeSync-offered firmware package to use for a
safe live OTA validation. The integration must not fabricate or substitute an
unverified image.

### Initial request `0x8034`

The logical command uses:

```text
flags           0x23
sequence        0
command version 1
sub-index       0
key type        K1
```

Its plaintext body is exactly 20 bytes:

```text
bytes 0-8    plugin name, UTF-8, zero padded to 9 bytes
byte 9       0
byte 10      2
byte 11      firmware patch version
byte 12      firmware minor version
byte 13      firmware major version
bytes 14-17  firmware file size, little-endian uint32
byte 18      0 when this is the last update component, otherwise 1
byte 19      0xFF
```

From the device's `0x8034` payload VeSync consumes:

```text
byte 9       update permission
bytes 10-11  maximum firmware-data chunk size, little-endian uint16
```

Update-permission values:

```text
0 can update
1 update not supported
2 cannot update now
3 system error
```

### Device-driven firmware data `0x8031`

After the initial request the transfer becomes device-driven. VeSync reads the
requested firmware offset from the first four bytes of each device `0x8031`
payload as little-endian uint32, then replies with the same sequence number.

The reply uses:

```text
flags           0x13
sequence        sequence from the device request
command version 1
sub-index       0
```

Reply plaintext body:

```text
byte 0       0 when chunk_length == device_max_chunk, otherwise 1
bytes 1-4    requested firmware offset, little-endian uint32
bytes 5-6    chunk length, little-endian uint16
bytes 7..    firmware bytes
```

LOW_SECURITY key selection is source-proven:

- `0x8031` is K0/plain only when the device request's key type is K0.
- Otherwise `0x8031` is K1.
- `0x8032` and `0x8033` acknowledgements are K1.

### Data-load result `0x8032`

Device payload:

```text
byte 0       load status
bytes 1-2    burn time in seconds when present for the last component
```

Load-status values:

```text
0 success
1 fail
2 timeout
```

VeSync immediately returns an empty `0x8032` response-style acknowledgement
with flags `0x13` and the device request's sequence.

### Final result `0x8033`

The first device payload byte is:

```text
0 success
1 update failed
2 firmware check failed
```

After about 20 ms VeSync returns an empty `0x8033` response-style
acknowledgement with flags `0x13` and the device request's sequence.

The pure packet/state helpers are implemented in `protocol/ota_v3.py`, but OTA
is deliberately not exposed as a Home Assistant action yet. The byte-level
transport is statically mapped; an actual firmware write has not yet been
live-validated on hardware.

## Units

Current-unit payloads:

| Unit | Payload |
| --- | --- |
| oz | `00 00` |
| lb:oz | `01 00` |
| g | `02 00` |
| mL water | `03 01` |
| mL milk | `03 02` |
| fl oz water | `04 01` |
| fl oz milk | `04 02` |

Enabled-unit mask bit order:

```text
0 oz
1 lb:oz
2 fl oz water
3 fl oz milk
4 g
5 mL water
6 mL milk
```

## Languages

```text
1 English (US)
2 English (UK)
3 German
4 French
5 Italian
6 Spanish
```

Changing language restarts the scale.

## Brightness

```text
Low     40
Medium  60
High    90
```

## Standby timeout

Supported values:

```text
30
45
60
120
180
300
```

## Physical controls

`0x444A` payload:

```text
set, left, right
```

A byte value `1` means that button was pressed.

Physical UNIT is reported through `0xA182`.
Physical short-press POWER/TARE is reported through `0xA186`.

## Quick Foods

One nutrition block is 33 bytes: 11 little-endian unsigned 24-bit values,
each stored in tenths, in this order:

1. calories
2. protein
3. total fat
4. saturated fat
5. trans fat
6. total carbohydrates
7. dietary fiber
8. sugars
9. cholesterol
10. sodium
11. iron

Quick Food names are truncated to 20 characters, matching the VeSync client.
