const VESYNC_SCAN_TEXT = window.VESYNC_SCAN_TEXT || {};
const NUTRIENTS = [
"calories_kcal",
"protein_g",
"total_fat_g",
"saturated_fat_g",
"trans_fat_g",
"total_carbs_g",
"dietary_fiber_g",
"sugars_g",
"cholesterol_mg",
"sodium_mg",
"iron_mg",
];
const esc = (value) =>
String(value ?? "")
.replaceAll("&", "&amp;")
.replaceAll("<", "&lt;")
.replaceAll(">", "&gt;")
.replaceAll('"', "&quot;")
.replaceAll("'", "&#039;");
class VeSyncLocalBtFoodScanner extends HTMLElement {
setConfig(config) {
this._config = config || {};
this._deviceId = this._config.device_id || localStorage.getItem("vesync_scan_device") || "";
this._cameraEntity = this._config.camera_entity || localStorage.getItem("vesync_scan_camera") || "";
this._aiTaskEntity = this._config.ai_task_entity || localStorage.getItem("vesync_scan_ai") || "";
this._hint = localStorage.getItem("vesync_scan_hint") || "";
this._registriesLoaded = false;
this._busy = false;
this._message = "";
this._error = "";
this._draft = null;
this._scanResult = null;
}
static getStubConfig() {
return {};
}
getCardSize() {
return 10;
}
set hass(hass) {
this._hass = hass;
if (!this._registriesLoaded) {
this._loadRegistries();
return;
}
this._render();
}
get hass() {
return this._hass;
}
_lang() {
const language = (this._hass?.language || "en").toLowerCase().split("-")[0];
return VESYNC_SCAN_TEXT[language] || VESYNC_SCAN_TEXT.en;
}
async _loadRegistries() {
if (!this._hass || this._loadingRegistries) return;
this._loadingRegistries = true;
try {
const devices = await this._hass.callWS({ type: "config/device_registry/list" });
this._devices = devices.filter((device) =>
(device.identifiers || []).some(
(identifier) => Array.isArray(identifier) && identifier[0] === "ha_vesync_bt"
)
);
if (!this._deviceId && this._devices.length === 1) {
this._deviceId = this._devices[0].id;
}
const cameras = this._cameraOptions();
if (!this._cameraEntity && cameras.length === 1) {
this._cameraEntity = cameras[0][0];
}
this._registriesLoaded = true;
} catch (err) {
this._error = String(err?.message || err);
} finally {
this._loadingRegistries = false;
this._render();
}
}
_cameraOptions() {
if (!this._hass) return [];
return Object.entries(this._hass.states)
.filter(([entityId]) => entityId.startsWith("camera."))
.map(([entityId, state]) => [
entityId,
state.attributes.friendly_name || entityId,
])
.sort((a, b) => a[1].localeCompare(b[1]));
}
_aiOptions() {
if (!this._hass) return [];
return Object.entries(this._hass.states)
.filter(([entityId]) => entityId.startsWith("ai_task."))
.map(([entityId, state]) => [
entityId,
state.attributes.friendly_name || entityId,
])
.sort((a, b) => a[1].localeCompare(b[1]));
}
_basisText(value) {
const t = this._lang();
return {
nutrition_label: t.label,
known_food: t.known,
visual_estimate: t.estimate,
unknown: t.unknown,
}[value] || value || t.unknown;
}
_selectOptions(options, selected) {
return options
.map(
([value, label]) =>
`<option value="${esc(value)}" ${value === selected ? "selected" : ""}>${esc(label)}</option>`
)
.join("");
}
_render() {
if (!this._hass || !this._config) return;
const t = this._lang();
const cameras = this._cameraOptions();
const aiTasks = this._aiOptions();
const devices = this._devices || [];
const attrs = this._scanResult || {};
const cameraState = this._hass.states[this._cameraEntity];
const cameraPicture = cameraState?.attributes?.entity_picture || "";
const resultExists = Boolean(this._scanResult);
const identified = attrs.identified !== false;
const confidence = Number(attrs.confidence ?? 0);
const warning = attrs.warning || "";
const deviceOptions = devices.map((d) => [d.id, d.name_by_user || d.name || d.id]);
this.innerHTML = `
<ha-card>
<style>
.wrap { padding: 16px; }
.header { display:flex; gap:12px; align-items:center; margin-bottom:14px; }
.header ha-icon { --mdc-icon-size: 32px; }
h2 { margin:0; font-size:1.35rem; }
.sub { color:var(--secondary-text-color); margin-top:3px; }
.grid { display:grid; grid-template-columns:repeat(2,minmax(0,1fr)); gap:12px; }
.field label { display:block; font-size:.82rem; color:var(--secondary-text-color); margin-bottom:5px; }
select,input { box-sizing:border-box; width:100%; min-height:42px; padding:8px 10px; border:1px solid var(--divider-color); border-radius:10px; background:var(--card-background-color); color:var(--primary-text-color); }
.preview { margin:14px 0; aspect-ratio:16/9; border-radius:14px; overflow:hidden; background:var(--secondary-background-color); display:flex; align-items:center; justify-content:center; }
.preview img { width:100%; height:100%; object-fit:cover; }
.actions { display:flex; flex-wrap:wrap; gap:10px; margin-top:14px; }
button { border:0; border-radius:12px; min-height:42px; padding:0 16px; font-weight:600; cursor:pointer; background:var(--primary-color); color:var(--text-primary-color); }
button.secondary { background:var(--secondary-background-color); color:var(--primary-text-color); }
button:disabled { opacity:.45; cursor:not-allowed; }
.result { margin-top:18px; padding-top:16px; border-top:1px solid var(--divider-color); }
.meta { display:flex; flex-wrap:wrap; gap:8px; margin:8px 0 12px; }
.pill { background:var(--secondary-background-color); padding:5px 9px; border-radius:999px; font-size:.82rem; }
.warning { margin:10px 0; padding:10px 12px; border-radius:10px; background:var(--warning-color, #f6c34422); }
.nutrition { display:grid; grid-template-columns:repeat(2,minmax(0,1fr)); gap:10px; }
.nutrition .field input { text-align:right; }
.reference { color:var(--secondary-text-color); font-size:.82rem; margin:8px 0 12px; }
.message { margin-top:10px; font-size:.9rem; }
.message.error { color:var(--error-color); }
@media (max-width:600px) { .grid,.nutrition { grid-template-columns:1fr; } }
</style>
<div class="wrap">
<div class="header">
<ha-icon icon="mdi:camera-iris"></ha-icon>
<div>
<h2>${esc(t.title)}</h2>
<div class="sub">${esc(t.subtitle)}</div>
</div>
</div>
<div class="grid">
<div class="field">
<label>${esc(t.scale)}</label>
<select id="scale" ${devices.length ? "" : "disabled"}>
${this._selectOptions(deviceOptions, this._deviceId)}
</select>
</div>
<div class="field">
<label>${esc(t.camera)}</label>
<select id="camera" ${cameras.length ? "" : "disabled"}>
${this._selectOptions(cameras, this._cameraEntity)}
</select>
</div>
<div class="field">
<label>${esc(t.aiTask)}</label>
<select id="ai">
<option value="" ${this._aiTaskEntity ? "" : "selected"}>${esc(t.preferredAi)}</option>
${this._selectOptions(aiTasks, this._aiTaskEntity)}
</select>
</div>
<div class="field">
<label>${esc(t.hint)}</label>
<input id="hint" type="text" maxlength="500" value="${esc(this._hint)}" placeholder="${esc(t.hintPlaceholder)}">
</div>
</div>
<div class="preview">
${
cameraPicture
? `<img src="${esc(cameraPicture)}" alt="${esc(t.camera)}">`
: `<ha-icon icon="mdi:camera-off" style="--mdc-icon-size:48px"></ha-icon>`
}
</div>
<div class="actions">
<button id="scan" ${this._busy || !this._deviceId || !this._cameraEntity ? "disabled" : ""}>
${esc(this._busy ? t.scanning : t.scan)}
</button>
</div>
${
resultExists
? `
<div class="result">
<h3>${esc(t.result)}</h3>
<div class="meta">
<span class="pill">${esc(t.confidence)}: ${esc(confidence.toFixed(0))}%</span>
<span class="pill">${esc(t.basis)}: ${esc(this._basisText(attrs.basis))}</span>
${!identified ? `<span class="pill">${esc(t.unknown)}</span>` : ""}
</div>
${warning ? `<div class="warning"><strong>${esc(t.warning)}:</strong> ${esc(warning)}</div>` : ""}
<div class="field">
<label>${esc(t.result)}</label>
<input id="food-name" type="text" maxlength="20" value="${esc(this._draft?.name || "")}">
</div>
<div class="reference">${esc(t.reference)}</div>
<div class="nutrition">
${NUTRIENTS.map(
(field) => `
<div class="field">
<label>${esc(t[field])}</label>
<input class="nutrient" data-field="${field}" type="number" min="0" step="0.1" value="${esc(this._draft?.[field] ?? 0)}">
</div>`
).join("")}
</div>
<div class="actions">
<button id="send" ${this._busy || !identified ? "disabled" : ""}>${esc(t.send)}</button>
<button id="save" class="secondary" ${this._busy || !identified ? "disabled" : ""}>${esc(t.save)}</button>
</div>
</div>`
: `<div class="result sub">${esc(t.noResult)}</div>`
}
${
this._message
? `<div class="message">${esc(this._message)}</div>`
: ""
}
${
this._error
? `<div class="message error">${esc(this._error)}</div>`
: ""
}
${!devices.length ? `<div class="message error">${esc(t.noDevices)}</div>` : ""}
${!cameras.length ? `<div class="message error">${esc(t.noCameras)}</div>` : ""}
</div>
</ha-card>
`;
this._bind();
}
_bind() {
const scale = this.querySelector("#scale");
const camera = this.querySelector("#camera");
const ai = this.querySelector("#ai");
const hint = this.querySelector("#hint");
scale?.addEventListener("change", (ev) => {
this._deviceId = ev.target.value;
localStorage.setItem("vesync_scan_device", this._deviceId);
this._render();
});
camera?.addEventListener("change", (ev) => {
this._cameraEntity = ev.target.value;
localStorage.setItem("vesync_scan_camera", this._cameraEntity);
this._render();
});
ai?.addEventListener("change", (ev) => {
this._aiTaskEntity = ev.target.value;
localStorage.setItem("vesync_scan_ai", this._aiTaskEntity);
});
hint?.addEventListener("input", (ev) => {
this._hint = ev.target.value;
localStorage.setItem("vesync_scan_hint", this._hint);
});
this.querySelector("#scan")?.addEventListener("click", () => this._scan());
this.querySelector("#send")?.addEventListener("click", () => this._send(false));
this.querySelector("#save")?.addEventListener("click", () => this._send(true));
this.querySelector("#food-name")?.addEventListener("input", (ev) => {
if (this._draft) this._draft.name = ev.target.value.slice(0, 20);
});
this.querySelectorAll(".nutrient").forEach((input) => {
input.addEventListener("input", (ev) => {
if (!this._draft) return;
const field = ev.target.dataset.field;
this._draft[field] = Math.max(0, Number(ev.target.value || 0));
});
});
}
async _scan() {
const t = this._lang();
this._busy = true;
this._error = "";
this._message = "";
this._render();
try {
const data = { camera_entity: this._cameraEntity };
if (this._aiTaskEntity) data.ai_task_entity = this._aiTaskEntity;
if (this._hint.trim()) data.hint = this._hint.trim();
const result = await this._hass.callWS({
type: "call_service",
domain: "ha_vesync_bt",
service: "scan_food",
service_data: data,
return_response: true,
});
const response = result?.response || {};
if (!response.name) throw new Error("AI scan returned no food result");
this._scanResult = response;
this._draft = { name: String(response.name || "").slice(0, 20) };
for (const field of NUTRIENTS) {
this._draft[field] = Math.max(0, Number(response[field] ?? 0));
}
this._busy = false;
this._render();
} catch (err) {
this._busy = false;
this._error = `${t.scanFailed}: ${err?.message || err}`;
this._render();
}
}
_reviewedServiceData() {
const data = {
device_id: this._deviceId,
name: String(this._draft?.name || "").trim().slice(0, 20),
};
for (const field of NUTRIENTS) {
data[field] = Math.max(0, Number(this._draft?.[field] || 0));
}
return data;
}
async _send(saveQuickFood) {
const t = this._lang();
if (!this._draft?.name) return;
const question = saveQuickFood ? t.saveConfirm : t.sendConfirm;
if (!window.confirm(question)) return;
this._busy = true;
this._error = "";
this._message = "";
this._render();
try {
const data = this._reviewedServiceData();
if (saveQuickFood) {
data.daily_food_weight_g = 100;
await this._hass.callService("ha_vesync_bt", "add_quick_food", data);
this._message = t.saved;
} else {
await this._hass.callService("ha_vesync_bt", "set_food_context", data);
this._message = t.sent;
}
} catch (err) {
this._error = `${saveQuickFood ? t.saveFailed : t.sendFailed}: ${err?.message || err}`;
} finally {
this._busy = false;
this._render();
}
}
}
if (!customElements.get("vesync-local-bt-food-scanner")) {
customElements.define("vesync-local-bt-food-scanner", VeSyncLocalBtFoodScanner);
}
window.customCards = window.customCards || [];
if (!window.customCards.some((card) => card.type === "vesync-local-bt-food-scanner")) {
window.customCards.push({
type: "vesync-local-bt-food-scanner",
name: "VeSync Local BT Food Scanner",
description: "AI camera food recognition and nutrition review for VeSync Local BT.",
preview: false,
});
}
