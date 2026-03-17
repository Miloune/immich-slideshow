"""The Immich Slideshow integration."""
import logging
import os

from aiohttp import web
from homeassistant.components.http import HomeAssistantView
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .api_view import ImmichRandomImageView
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

FRONTEND_JS_URL = "/api/immich_slideshow/frontend/immich-slideshow.js"
FRONTEND_CACHE_KEY = "frontend_js_content"


class ImmichFrontendView(HomeAssistantView):
    """Serve the Lovelace JS card file from memory."""

    url = FRONTEND_JS_URL
    name = "api:immich_slideshow:frontend"
    requires_auth = False  # Lovelace resources are loaded unauthenticated

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize the view."""
        self.hass = hass

    async def get(self, request: web.Request) -> web.Response:
        """Return the cached JS content."""
        content = self.hass.data[DOMAIN].get(FRONTEND_CACHE_KEY)
        if content is None:
            _LOGGER.error("Frontend JS content not found in cache")
            return web.Response(status=404)

        return web.Response(
            text=content,
            content_type="application/javascript",
            headers={"Cache-Control": "no-cache"},
        )


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Set up the Immich Slideshow component (runs at startup, before config entries)."""
    hass.data.setdefault(DOMAIN, {})

    # Load JS content into memory to avoid blocking I/O in the event loop
    js_path = os.path.join(os.path.dirname(__file__), "frontend", "immich-slideshow.js")

    def _load_js():
        try:
            with open(js_path, "r", encoding="utf-8") as f:
                return f.read()
        except OSError as exc:
            _LOGGER.error("Could not read frontend JS: %s", exc)
            return None

    js_content = await hass.async_add_executor_job(_load_js)
    if js_content:
        hass.data[DOMAIN][FRONTEND_CACHE_KEY] = js_content

    # Register HTTP views at startup so the card JS is always available
    hass.http.register_view(ImmichFrontendView(hass))
    hass.http.register_view(ImmichRandomImageView(hass))

    # Register the Lovelace resource so the card appears in the UI
    hass.async_create_task(_register_lovelace_resource(hass))

    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Immich Slideshow from a config entry (stores connection details)."""
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = entry.data
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    hass.data[DOMAIN].pop(entry.entry_id)
    return True


async def _register_lovelace_resource(hass: HomeAssistant) -> None:
    """Automatically register the Lovelace card JS resource."""
    try:
        lovelace = hass.data.get("lovelace")
        if lovelace is None:
            _LOGGER.warning("Lovelace not found, cannot auto-register resource.")
            return

        from homeassistant.components.lovelace import resources as lovelace_resources  # noqa: PLC0415

        resources = lovelace_resources.ResourceStorageCollection(hass, lovelace)
        await resources.async_load()
        existing = [r["url"] for r in resources.async_items()]

        if FRONTEND_JS_URL not in existing:
            await resources.async_create_item(
                {"res_type": "module", "url": FRONTEND_JS_URL}
            )
            _LOGGER.info("Immich Slideshow frontend resource registered.")
        else:
            _LOGGER.debug("Immich Slideshow frontend resource already registered.")

    except Exception as exc:  # noqa: BLE001
        _LOGGER.warning(
            "Could not auto-register Lovelace resource (add it manually if needed): %s",
            exc,
        )
