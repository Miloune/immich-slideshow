"""HTTP view that proxies Immich API calls to avoid CORS."""
import logging
from typing import Any

import aiohttp
from aiohttp import web

from homeassistant.components.http import HomeAssistantView
from homeassistant.core import HomeAssistant

from .const import CONF_API_KEY, CONF_HOST, CONF_SEARCH_BATCH_SIZE, DOMAIN

_LOGGER = logging.getLogger(__name__)


class ImmichRandomImageView(HomeAssistantView):
    """Handle requests for a random Immich image, proxied through HA server."""

    url = "/api/immich_slideshow/random_image"
    name = "api:immich_slideshow:random_image"
    requires_auth = True

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialise the view."""
        self.hass = hass

    async def get(self, request: web.Request) -> web.Response:
        """Handle GET request: find a random image ID, fetch it, and stream it back."""
        entry = _get_config_entry(self.hass)
        if entry is None:
            return web.Response(status=503, text="Integration not configured.")

        host = entry.data[CONF_HOST].rstrip("/")
        api_key = entry.data[CONF_API_KEY]

        # Get optional albums filter from query params: ?albums=id1,id2
        albums_param = request.rel_url.query.get("albums", "")
        album_ids = [a for a in albums_param.split(",") if a]
        
        # Create a cache key based on the album IDs to avoid mixing different collections
        cache_key = f"cache_{','.join(sorted(album_ids)) if album_ids else 'all'}"
        
        hass_data = self.hass.data[DOMAIN]
        if cache_key not in hass_data:
            hass_data[cache_key] = []

        headers = {"X-Api-Key": api_key, "Content-Type": "application/json"}

        try:
            async with aiohttp.ClientSession() as session:
                # 1. Get random asset IDs if cache is empty
                if not hass_data[cache_key]:
                    batch_size = entry.data.get(CONF_SEARCH_BATCH_SIZE, 50)
                    _LOGGER.debug("Fetching new batch of %s random IDs for %s", batch_size, cache_key)
                    search_body: dict[str, Any] = {"type": "IMAGE", "size": batch_size}
                    if album_ids:
                        search_body["albumIds"] = album_ids

                    async with session.post(
                        f"{host}/api/search/random",
                        json=search_body,
                        headers=headers,
                        timeout=aiohttp.ClientTimeout(total=15),
                    ) as search_resp:
                        if search_resp.status != 200:
                            _LOGGER.error("Immich search/random failed: %s", search_resp.status)
                            return web.Response(status=search_resp.status)
                        results = await search_resp.json()
                        if not results:
                            return web.Response(status=404, text="No images found.")
                        
                        # Fill the cache
                        hass_data[cache_key] = [item["id"] for item in results]

                # 2. Extract next asset_id from cache
                asset_id = hass_data[cache_key].pop(0)

                # 3. Fetch the full-size thumbnail
                async with session.get(
                    f"{host}/api/assets/{asset_id}/thumbnail",
                    params={"size": "fullsize"},
                    headers=headers,
                    timeout=aiohttp.ClientTimeout(total=30),
                ) as img_resp:
                    if img_resp.status != 200:
                        _LOGGER.error("Immich thumbnail fetch failed: %s", img_resp.status)
                        return web.Response(status=img_resp.status)
                    content_type = img_resp.headers.get("Content-Type", "image/jpeg")
                    image_data = await img_resp.read()

        except aiohttp.ClientError as exc:
            _LOGGER.error("Error connecting to Immich: %s", exc)
            return web.Response(status=503, text="Cannot reach Immich server.")

        return web.Response(body=image_data, content_type=content_type)


def _get_config_entry(hass: HomeAssistant):
    """Return the first config entry for the integration."""
    entries = hass.config_entries.async_entries(DOMAIN)
    return entries[0] if entries else None
