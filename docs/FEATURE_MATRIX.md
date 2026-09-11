# Feature matrix

| Capability | Evidence status | VeSync Local BT 0.2.0b2 / main |
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
| SET-confirmed food report `0x4445` | Proven live for five physical Quick Foods, including UTF-8 `Hühnchenbrust`; captured vectors parse correctly. Raw capture shows `0x4445` arriving at the same timestamp as the SET `0x444A` event, not on LEFT/RIGHT navigation | Parser retained as a SET-confirmation/reconciliation path |
| Live highlighted Quick Food cursor | v39 proved nutrient-mode weighing works after LEFT/RIGHT with no SET and no `0x4445`. v40 proved the exact ordered cursor: `<none> -> Ei -> Banane -> Hühnchenbrust -> Blaubeere -> Avocado -> <none>` for RIGHT and the exact reverse for LEFT. v41r1 live Home Assistant validation then recorded four distinct MySQL Recorder transitions with no SET: `unknown -> Ei -> Banane -> Ei -> unknown`, each with a new state ID. No VeSync Local BT errors or tracebacks occurred during the validation window | **Implemented and live-proven end to end**; LEFT/RIGHT immediately publishes the highlighted Quick Food, including the `<none>` boundaries |
| AI camera food scanner | Home Assistant 2026.9 AI Task supports structured output and camera/media attachments. The implementation requests one food with all 11 scale nutrients normalized to 100 g, returns the result only to the dashboard browser, requires explicit review, and uses the already-proven food-context / Quick Food actions for the final user-confirmed write | **Implemented on `main`; live runtime validation pending** |
| Offline 200-record history | Advertised by manual; protocol/provider parser and sync path are known. Static callgraph proves R002 inherits the R001 implementation and the official lifecycle is `onPause -> save enabled (0x444C 00)`, `onResume/connected-active -> save suppressed (0x444C 01)`. A controlled official-VeSync offline selected-food measurement using that exact lifecycle still returned an empty `0x4446` page on first reconnect | **Disabled** — no record-producing behavior has been observed on the tested unit/firmware |
| History delete/ack | `0x444B` semantics known, but no real stored record was produced by the tested unit/firmware | **Disabled** |
| OTA `BT_ETEKCITY_V3` wire protocol | Static provider/state-machine/codec mapping proven; actual firmware write has not been live-validated | Internal codec + updater + explicit VSV3 response-frame support; **not exposed** |
| Official firmware availability | Static VeSync source proves CNS-R002S-S uses `MAC_ID` cloud update checks. On VeSync 5.9.60, two safe settings-screen UI snapshots showed the Firmware Update row but no `sm_v_red_warning`; that view is driven directly by `haveUpdate(scaleMac)` | **No official update currently offered for the tested device** |
| Factory reset | Static end-to-end VeSync path proven: CNS-R002S-S inherits the R001 reset provider; connected-only UI confirmation calls `0xA087` with payload `01`, awaits the normal BLE request completion, dismisses on success, and reports failure if the scale is not connected. Scale-specific UI warns the reset is irreversible, clears stored user/history/configuration data, and the device restarts afterward | **Disabled** — destructive operation; no live reset performed |
| Hold | CNS-R002S-S disables capability | Not exposed |
| Region query | CNS-R002S-S disables capability | Not exposed |
