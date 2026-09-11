"""Register the VeSync Local BT dashboard card."""

from __future__ import annotations

from pathlib import Path

from homeassistant.components.frontend import add_extra_js_url
from homeassistant.components.http import StaticPathConfig
from homeassistant.core import HomeAssistant

from .const import DOMAIN

_FRONTEND_URL = "/vesync_local_bt"
_DATA_KEY = f"{DOMAIN}_frontend_registered"


async def async_setup_frontend(hass: HomeAssistant) -> None:
    """Serve and load the built-in food scanner card when frontend is available."""
    if "frontend" not in hass.config.components or hass.data.get(_DATA_KEY):
        return

    frontend_dir = Path(__file__).parent / "frontend"
    await hass.http.async_register_static_paths(
        [
            StaticPathConfig(
                url_path=_FRONTEND_URL,
                path=str(frontend_dir),
                cache_headers=False,
            )
        ]
    )
    # Load through one ordered module so the translation table is guaranteed to
    # exist before the custom card module evaluates.
    add_extra_js_url(
        hass,
        f"{_FRONTEND_URL}/food-scanner-loader.js?v=0.2.0b2-r1",
    )
    hass.data[_DATA_KEY] = True
