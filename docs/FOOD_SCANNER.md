# AI Food Scanner dashboard

VeSync Local BT includes an optional dashboard card that can analyze either the
current image from a Home Assistant camera or a photo captured/selected on the
browser device, ask a Home Assistant AI Task provider to identify one food,
return a structured nutrition profile normalized to **100 g**, and let the user
review or edit every value before anything is sent to the scale.

## Safety model

AI recognition is not treated as authoritative nutrition data.

The flow is deliberately two-stage:

1. **Scan and review** — the camera image is analyzed and the proposed food name,
   confidence, evidence basis, warning, and all 11 nutrition values are shown.
2. **Explicit send** — only after review does the user choose either **Send to
   scale** or **Save as Quick Food**.

The dashboard never automatically sends an AI result to the physical scale.

The scanner has an explicit language contract:

- the recognized **food name is always English**, independent of the Home
  Assistant/dashboard language, so the scale receives one stable canonical food
  name;
- user-facing **warning/description text follows the Home Assistant UI
  language**;
- machine values such as `basis` remain fixed protocol/schema values and are not
  translated.

The evidence badge distinguishes:

- `nutrition_label` — values came from a readable label in the image.
- `known_food` — the food was recognized and typical nutrition data was used.
- `visual_estimate` — the result required visual estimation and should be checked
  especially carefully.
- `unknown` — reliable identification was not possible; sending is disabled.

All values are normalized to a 100 g reference because that is the nutrition
format used by the scale.

## Privacy

VeSync Local BT does **not** store the camera image or AI result in integration
storage, Home Assistant entities, or Recorder. The `scan_food` action is
response-only and the dashboard keeps the current draft only in browser memory.

The selected image is passed through Home Assistant's AI Task framework. If the
chosen AI Task provider is cloud-based, the provider can receive the image
according to that provider's own privacy terms. Provider credentials stay with
the provider integration; VeSync Local BT does not store or handle them.

The card remembers only the selected scale, camera source, AI Task entity, and
optional hint in browser `localStorage`. It does not persist recognized food or
nutrition values.

## Requirements

- Home Assistant 2026.9 or newer.
- VeSync Local BT loaded with a supported scale.
- Either a Home Assistant `camera.*` entity or browser/mobile photo capture.
- An AI Task entity that supports both **Generate data** and **attachments**.
  You can select one in the card, or leave the field blank to use Home
  Assistant's preferred AI Task for Generate data.

Home Assistant resolves `media-source://camera/<entity_id>` attachments into a
camera snapshot before invoking the AI provider. Browser/mobile captures are
sent as an in-memory image attachment and are not persisted by VeSync Local BT.

### Browser and mobile camera behavior

The card offers two local-device capture paths:

- **Live browser camera** uses `navigator.mediaDevices.getUserMedia()`. Browsers
  expose this only in a secure context, so normal HTTPS Home Assistant URLs can
  use the live preview/capture buttons. A plain-LAN URL such as
  `http://192.168.x.x:8123` cannot use live `getUserMedia()` by browser design.
- **Take / select photo** uses the native `input type="file"` image-capture path.
  It remains available on plain HTTP and is intended to work in normal mobile
  browsers and Home Assistant Companion WebViews even when live camera capture
  is unavailable.

The scanner deliberately avoids rebuilding its DOM while a native select menu,
camera permission prompt, or Android/file chooser is active. Unrelated Home
Assistant state churn therefore cannot close a selector or destroy the pending
photo input while the user is interacting with it.

### OpenAI provider note

As of 2026-09-11, Home Assistant core issue #180168 is still open for a case
where the OpenAI AI Task integration accepts an image attachment but the model
may not receive it. If OpenAI returns results that clearly ignore the camera
image, test another image-capable AI Task provider until that upstream issue is
resolved.

## Add the dashboard card

The card JavaScript is served and registered automatically by the integration;
there is no separate HACS frontend repository to install.

Add a manual card to a dashboard:

```yaml
type: custom:vesync-local-bt-food-scanner
```

Optional defaults can be pinned in YAML:

```yaml
type: custom:vesync-local-bt-food-scanner
device_id: YOUR_HOME_ASSISTANT_DEVICE_ID
camera_entity: camera.kitchen
ai_task_entity: ai_task.your_provider
```

Leaving a value out keeps it selectable in the card.

A complete example dashboard is in
[`examples/food-scanner-dashboard.yaml`](../examples/food-scanner-dashboard.yaml).

## Dashboard workflow

1. Wake the scale if you plan to send the result immediately.
2. Choose the target scale.
3. Choose either a Home Assistant camera or **Browser / device camera**.
4. Choose an image-capable AI Task, or use the preferred AI Task.
5. Optionally add a short hint such as `banana` or `nutrition label`.
6. For the browser/device source, either use live capture on HTTPS or choose
   **Take / select photo** on any supported mobile browser/WebView.
7. Select **Scan food**.
8. Review the English food name, localized warning, evidence basis, confidence,
   and every nutrition value.
9. Correct any value that is wrong.
10. Choose:
   - **Send to scale** — sends the reviewed profile through the proven `0x4444`
     food-context path. It does not add a Quick Food.
   - **Save as Quick Food** — writes the reviewed profile as a 100 g Quick Food
     on the scale.

## Backend action

The scanner is also available as a response-only Home Assistant action:

```yaml
action: ha_vesync_bt.scan_food
data:
  camera_entity: camera.kitchen
  ai_task_entity: ai_task.your_provider  # optional
  hint: banana                            # optional
response_variable: food
```

The response contains:

```yaml
identified: true
name: Banana
confidence: 96
basis: known_food
warning: ""
reference_weight_g: 100
camera_entity: camera.kitchen
ai_task_entity: ai_task.your_provider
scanned_at: "..."
calories_kcal: 89
protein_g: 1.1
# ...remaining scale nutrition fields...
```

No scale write occurs during `scan_food`.
