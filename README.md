# HA-VeSync-BT

Local Home Assistant integration for VeSync BLE devices.

> **Status:** experimental / reverse-engineering based.  
> **Currently supported:** COSORI Smart Nutrition Scale **CNS-R002S-S**.

The integration is intentionally separate from Home Assistant's built-in `vesync`
integration. Its Home Assistant domain is `ha_vesync_bt`, so both integrations can
coexist.

## Goals

- 100% local BLE operation.
- No VeSync account, cloud credential, access token, refresh token, password, or
  API key is stored or required.
- Device-specific code is separated from the generic VeSync VSV3 transport so
  additional VeSync BLE devices can be added later.
- Only behavior proven from captures, device testing, or VeSync client behavior
  is implemented.

## CNS-R002S-S support

### Implemented

- Bluetooth discovery by `COSORI Nutrition Scale`.
- Native VeSync VSV3 session setup (`0x4201` / `0x4202`).
- AES-CBC/PKCS7 encrypted VSV3 transport.
- MTU-aware VSV3 write splitting.
- Automatic reconnect when the scale wakes and advertises again.
- Live measurement reports.
- Stable / unstable state.
- Tare state and native tare command.
- Object-present state.
- Overload and low-voltage state.
- Battery and charging state.
- Current unit:
  - g
  - oz
  - lb:oz
  - mL water
  - mL milk
  - fl oz water
  - fl oz milk
- Enabled-unit mask.
- Device language:
  - English (US)
  - English (UK)
  - German
  - French
  - Italian
  - Spanish
- Brightness:
  - Low = 40
  - Medium = 60
  - High = 90
- Standby/backlight timeout:
  - 30 s
  - 45 s
  - 60 s
  - 120 s
  - 180 s
  - 300 s
- Physical LEFT / RIGHT / SET / UNIT / TARE events.
- Timestamp sync.
- Firmware query.
- Quick Food query/add/remove/reorder.
- Current food-context command (`0x4444`).
- Quick Food selection report (`0x4445`) and nutrition payload.
- Full 11-field nutrition payload encoding/decoding.

### Deliberately not exposed yet

These are kept out of the public HA surface until their behavior is fully proven:

- Offline-history persistence / 200-record memory.
- History acknowledgement/deletion (`0x444B`).
- OTA firmware update.
- Factory reset.
- Rare destructive/error edge cases.
- Hold and device-region controls: the CNS-R002S-S implementation explicitly
  disables these capabilities, so they are not missing entities.

## Installation

### HACS custom repository

1. Add this repository to HACS as a **Custom repository** of type **Integration**.
2. Install **HA-VeSync-BT**.
3. Restart Home Assistant.
4. Wake the CNS-R002S-S.
5. Go to **Settings → Devices & services → Add integration → HA-VeSync-BT**.
6. Select the discovered `COSORI Nutrition Scale`.

### Manual

Copy:

```text
custom_components/ha_vesync_bt
```

into:

```text
<your Home Assistant config>/custom_components/ha_vesync_bt
```

and restart Home Assistant.

## Entities

The first implementation exposes:

- Measurement sensor
- Battery sensor
- Quick Food count sensor
- Selected food sensor
- Enabled units sensor
- Firmware sensor
- Connected binary sensor
- Stable binary sensor
- Tare binary sensor
- Object present binary sensor
- Low battery binary sensor
- Overload binary sensor
- Charging binary sensor
- Unit select
- Language select
- Brightness select
- Standby timeout select
- Tare button
- Sync clock button
- Refresh button
- Physical-controls event entity

The physical-controls event entity emits the standard Home Assistant
`press_end` event with a `button` field containing one of:

```text
left
right
set
unit
tare
```

## Actions

The integration provides device-level actions for the structured functions that
do not fit standard Home Assistant entity models:

- `ha_vesync_bt.add_quick_food`
- `ha_vesync_bt.remove_quick_food`
- `ha_vesync_bt.reorder_quick_foods`
- `ha_vesync_bt.set_enabled_units`
- `ha_vesync_bt.set_food_context`

Quick Food nutrition fields are encoded in the same fixed order used by the
scale:

1. Calories (kcal)
2. Protein (g)
3. Total fat (g)
4. Saturated fat (g)
5. Trans fat (g)
6. Total carbohydrates (g)
7. Dietary fiber (g)
8. Sugars (g)
9. Cholesterol (mg)
10. Sodium (mg)
11. Iron (mg)

## Architecture

```text
Home Assistant
   │
   ├── config flow / Bluetooth discovery
   │
   ├── coordinator + HA entities/actions
   │
   └── devices/
        └── CNS-R002S-S device implementation
                │
                └── protocol/
                     └── generic VeSync VSV3 BLE transport
```

The VSV3 session key and IV are ephemeral and remain only in memory while the
scale is connected. They are never written into the Home Assistant config
entry, logs, diagnostics, or storage.

## Development

Protocol-only tests do not require Home Assistant:

```bash
python -m pytest -q tests
```

Static syntax check:

```bash
python -m compileall -q custom_components tests
```

The repository includes HACS and Hassfest validation workflows.

## Reverse-engineering notes

See:

- [`docs/PROTOCOL.md`](docs/PROTOCOL.md)
- [`docs/FEATURE_MATRIX.md`](docs/FEATURE_MATRIX.md)

This project is unofficial and is not affiliated with VeSync or COSORI.
