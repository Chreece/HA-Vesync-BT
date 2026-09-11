# Changelog

## 0.2.0b1

First public beta of **VeSync Local BT** for the COSORI CNS-R002S-S Smart Nutrition Scale.

### Added and proven

- Fully local BLE operation with no VeSync account or cloud credentials required by the integration.
- Native VeSync VSV3 session setup with AES-CBC/PKCS7 transport and automatic reconnect.
- Live measurement, stable state, tare state/command, object presence, overload, low-voltage, battery, and charging state.
- Current unit, enabled-unit mask, six device-language options, brightness, and standby timeout controls.
- Physical LEFT / RIGHT / SET / UNIT / TARE event reporting.
- Quick Food query, add, remove, reorder, nutrition payload handling, and food-context support.
- Live highlighted Quick Food tracking from physical LEFT/RIGHT navigation, including the real no-food boundary state, without requiring SET.
- SET-confirmed `0x4445` food reports retained as a confirmation/reconciliation path.
- Firmware query and clock synchronization.
- Home Assistant translations for English, German, and Greek.
- User-visible integration name changed to **VeSync Local BT** while keeping the `ha_vesync_bt` domain for compatibility.

### HACS / release readiness

- HACS custom-integration layout and `hacs.json` validated with the official HACS action without ignored checks.
- Hassfest validation enabled and passing.
- Minimum Home Assistant version: **2026.9.0**.
- GitHub prerelease publication is gated on the complete validation workflow succeeding.
- Published GitHub release notes are used directly by HACS.

### Known limitations

- Offline history remains disabled: the protocol is mapped, but the tested scale/firmware did not produce stored records even through the official VeSync lifecycle.
- OTA firmware updating remains disabled: the BT_ETEKCITY_V3 protocol is mapped, but no verified official firmware image has been obtained for safe live validation.
- Factory reset remains disabled because it is destructive.
- Hold and region controls are not exposed because the CNS-R002S-S explicitly disables those capabilities.

## 0.1.0

Initial development baseline (not published as a GitHub release).

- Add generic VeSync VSV3 BLE transport.
- Add CNS-R002S-S device implementation.
- Add Home Assistant Bluetooth config flow.
- Add live entities and reversible settings.
- Add Quick Food actions.
- Add English, German, and Greek Home Assistant translations.
