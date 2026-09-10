# CNS-R002S-S protocol notes

This document contains only behavior currently used by HA-VeSync-BT.

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
Normal K1 traffic uses the negotiated session IV.

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

Known but intentionally not exposed yet:

| Command | Status |
| --- | --- |
| `0x4446` | Offline-history query — parser known, persistence still under validation |
| `0x444B` | History acknowledgement/delete — not exposed until persistence is proven |
| `0x444C` | Device-save lifecycle state — known but not needed for core HA operation |
| `0xA087` | Factory reset — destructive, intentionally disabled |

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
