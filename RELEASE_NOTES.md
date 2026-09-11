# VeSync Local BT 0.2.0b1 — Beta 1

This is the first public beta of **VeSync Local BT** for the **COSORI CNS-R002S-S Smart Nutrition Scale**.

> **Beta release:** this version is intended for testing before the first stable release. In HACS, enable prerelease updates for this repository if you want beta updates to appear automatically.

## Highlights

- **100% local BLE operation** for the supported scale.
- No VeSync account, cloud password, OAuth token, API key, access token, or refresh token is required or stored by the integration.
- Native VeSync VSV3 session setup with encrypted transport and automatic reconnect when the scale wakes.
- Live measurement plus stable, tare, object-present, overload, low-voltage, battery, and charging state.
- Controls for unit, enabled-unit mask, device language, brightness, standby timeout, tare, clock sync, and refresh.
- Physical LEFT / RIGHT / SET / UNIT / TARE events exposed to Home Assistant.
- Quick Food query, add, remove, reorder, nutrition payloads, and food context.
- **Live selected-food tracking now follows LEFT/RIGHT immediately without requiring SET**, matching the food the scale actually uses for nutrient calculation. The real `<none>` state at both ends of the Quick Food list is also tracked.
- SET-confirmed `0x4445` food reports remain supported as a confirmation/reconciliation path.
- Home Assistant UI translations included for **English, German, and Greek**.
- User-visible integration name is now **VeSync Local BT**. The technical domain remains `ha_vesync_bt`, so existing entity IDs, services, config entries, and automations remain compatible.

## HACS installation / upgrade

1. Add `https://github.com/Chreece/HA-Vesync-BT` to HACS as a **Custom repository** of type **Integration** if it is not already added.
2. For beta updates, enable the repository's **prerelease** switch in HACS.
3. Install or update to **v0.2.0b1**.
4. Restart Home Assistant.
5. Add **VeSync Local BT** from **Settings → Devices & services** if this is a new installation.

**Minimum Home Assistant version:** `2026.9.0`

The repository is validated with the official **HACS action** and **Hassfest** with no ignored HACS checks before the release is published.

## Supported hardware

Currently supported:

- COSORI Smart Nutrition Scale **CNS-R002S-S**

## Known limitations

- **Offline history:** disabled. The history protocol and official save lifecycle are mapped, but the tested scale/firmware did not produce stored records even when exercised through the official VeSync flow.
- **OTA firmware update:** disabled. The BT_ETEKCITY_V3 transfer protocol is mapped, but no verified official firmware image has yet been obtained for safe live validation.
- **Factory reset:** disabled because it is destructive.
- **Hold / region controls:** not exposed because the CNS-R002S-S implementation explicitly disables those capabilities.

## Feedback

This beta is reverse-engineering based and evidence-first. If you find a reproducible device or Home Assistant issue, please open a GitHub issue with the Home Assistant version, integration version, and relevant diagnostics/log details (with private information removed).
