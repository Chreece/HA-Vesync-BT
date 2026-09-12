from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CARD = (ROOT / "custom_components/ha_vesync_bt/frontend/food-scanner-card-v2.js").read_text(
    encoding="utf-8"
)
I18N = (ROOT / "custom_components/ha_vesync_bt/frontend/food-scanner-i18n.js").read_text(
    encoding="utf-8"
)
LOADER = (ROOT / "custom_components/ha_vesync_bt/frontend/food-scanner-loader.js").read_text(
    encoding="utf-8"
)
SETUP = (ROOT / "custom_components/ha_vesync_bt/frontend_setup.py").read_text(
    encoding="utf-8"
)


def test_hass_updates_do_not_rebuild_controls_on_every_state_change():
    assert "hassSignature()" in CARD
    assert "if(sig===this._hassSignature)" in CARD
    assert "this._repaintPending" in CARD
    assert "this.uiLocked()||this.stream" in CARD


def test_mobile_selects_arm_a_dom_repaint_hold_before_native_ui_opens():
    assert 'querySelectorAll("button,select,input")' in CARD
    assert 'addEventListener("pointerdown",arm' in CARD
    assert 'addEventListener("touchstart",arm' in CARD
    assert 'el.tagName==="SELECT"?60000:8000' in CARD


def test_photo_picker_survives_android_and_webview_native_chooser():
    assert 'class="filepick" type="file" accept="image/*" capture="environment"' in CARD
    assert ".filepick{position:fixed!important" in CARD
    assert "display:none" not in CARD
    assert "this._pickerOpen=true" in CARD
    assert "this.holdUi(120000)" in CARD
    assert 'addEventListener("cancel"' in CARD
    assert 'document.addEventListener("visibilitychange"' in CARD
    assert 'window.addEventListener("focus"' in CARD
    assert "p.click()" in CARD


def test_live_camera_stays_https_only_but_native_photo_capture_remains_available():
    assert "window.isSecureContext&&navigator.mediaDevices?.getUserMedia" in CARD
    assert '!window.isSecureContext||!navigator.mediaDevices?.getUserMedia' in CARD
    assert 'capture="environment"' in CARD


def test_companion_android_limit_is_not_misrepresented():
    assert "Home Assistant Companion for Android" in I18N
    assert "existing photos/files only" in I18N
    assert "nur vorhandene Fotos/Dateien" in I18N
    assert "μόνο υπάρχουσες φωτογραφίες/αρχεία" in I18N
    assert "still works on mobile and lets the phone camera handle capture" not in I18N
    assert "εξακολουθεί να χρησιμοποιεί την κάμερα του κινητού" not in I18N


def test_frontend_cache_revision_moves_together():
    assert 'const revision = "0.2.0b2-r5"' in LOADER
    assert '_FRONTEND_REVISION = "0.2.0b2-r5"' in SETUP
