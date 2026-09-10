# Feature matrix

| Capability | Evidence status | HA-VeSync-BT 0.1.0 |
| --- | --- | --- |
| VSV3 connection | Proven live | Implemented |
| AES session | Proven live | Implemented |
| Live measurement | Proven live | Implemented |
| Stable flag | Proven live | Implemented |
| Tare | Proven native + physical | Implemented |
| Battery | Proven live | Implemented |
| Charging | Proven state model | Implemented |
| Low voltage | Proven state model | Implemented |
| Overload | Proven state model | Implemented |
| Object present | Proven state model | Implemented |
| 7 current units | Proven write/readback | Implemented |
| Enabled-unit mask | Proven bit-by-bit | Implemented |
| 6 languages | Proven write/reconnect/readback | Implemented |
| Brightness 40/60/90 | Proven write/readback | Implemented |
| 30/45/60/120/180/300 s timeout | Proven write/readback | Implemented |
| LEFT/RIGHT/SET events | Proven live | Implemented |
| UNIT event | Proven live | Implemented |
| TARE event | Proven live | Implemented |
| Timestamp sync | Proven command | Implemented |
| Firmware query | Proven live | Implemented |
| Quick Food query | Proven live | Implemented |
| Quick Food add | Proven live | Implemented |
| Quick Food reorder/delete semantics | Proven live | Implemented |
| Quick Food nutrition | Proven exact roundtrip | Implemented |
| Food context `0x4444` | Proven | Implemented action |
| Selected food `0x4445` | Proven live | Implemented sensor/state |
| Offline 200-record history | Advertised by manual; official VeSync first reconnect after a controlled offline selected-food measurement returned an empty `0x4446` response on the tested CNS-R002S-S | **Disabled** |
| History delete/ack | `0x444B` semantics known, but no real stored record was produced by the tested unit/firmware | **Disabled** |
| OTA `BT_ETEKCITY_V3` wire protocol | Static provider/state-machine/codec mapping proven; actual firmware write has not been live-validated | Internal pure codec only; **not exposed** |
| Factory reset | Command known, destructive | **Disabled** |
| Hold | CNS-R002S-S disables capability | Not exposed |
| Region query | CNS-R002S-S disables capability | Not exposed |
