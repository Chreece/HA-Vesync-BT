# Changelog

## 0.2.0b2

Development beta for the AI food-scanner workflow. This version is not published yet; live Home Assistant validation comes before the Beta 2 release.

### Added on main

- Optional AI Food Scanner dashboard card for Home Assistant camera entities.
- Structured Home Assistant AI Task recognition with all 11 scale nutrition fields normalized to 100 g.
- Explicit review/edit step before any nutrition is sent to the physical scale.
- User-confirmed **Send to scale** through the proven `0x4444` food-context path.
- User-confirmed **Save as Quick Food** using the existing proven Quick Food write path.
- English, German, and Greek scanner-card UI.
- Response-only `ha_vesync_bt.scan_food` action with no scanner entity or Recorder persistence.
- Scanner documentation and complete dashboard example.

### Privacy / safety

- VeSync Local BT does not persist the camera image or AI recognition result.
- The dashboard keeps the current result only in browser memory; only camera/AI/device selections and an optional hint are remembered locally in the browser.
- Provider credentials remain owned by the Home Assistant AI Task provider.
- AI results are never automatically written to the scale.

### Validation status

- Static Python, JavaScript, YAML, scanner normalization tests, Hassfest, and HACS validation pass on `main`.
- Live camera → AI Task → review → scale validation is still required before publishing Beta 2.

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
