"""HTTP view that proxies Immich API calls to avoid CORS."""
import logging
from typing import Any

import aiohttp
from aiohttp import web

from homeassistant.components.http import HomeAssistantView
from homeassistant.core import HomeAssistant

from .const import (
    CONF_API_KEY,
    CONF_HOST,
    CONF_SEARCH_BATCH_SIZE,
    CONF_DEFAULT_SIZE,
    CONF_REFILL_THRESHOLD,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)

# Valid Immich thumbnail sizes.
# "thumbnail" → ~50 kB  (fast, lower quality)
# "preview"   → ~300 kB (good quality, still 10-20× smaller than original)
VALID_SIZES = {"thumbnail", "preview"}

# Shared ClientSession key in hass.data
SESSION_KEY = "aiohttp_session"

# Set of cache_keys currently being refilled — prevents duplicate tasks.
REFILLING_KEY = "refilling"


def _entry_value(entry, key: str, default):
    """Read from options first (set via Configure), then initial data, then default."""
    return entry.options.get(key, entry.data.get(key, default))


def _get_session(hass: HomeAssistant) -> aiohttp.ClientSession:
    """Return (or create) the shared aiohttp session for this integration."""
    hass_data = hass.data[DOMAIN]
    session = hass_data.get(SESSION_KEY)
    if session is None or session.closed:
        session = aiohttp.ClientSession()
        hass_data[SESSION_KEY] = session
    return session


async def _refill_cache(
    hass: HomeAssistant,
    cache_key: str,
    album_ids: list[str],
) -> None:
    """Background task: fetch a new batch of asset IDs and append to cache."""
    hass_data = hass.data[DOMAIN]
    refilling: set = hass_data.setdefault(REFILLING_KEY, set())

    if cache_key in refilling:
        return  # already in progress
    refilling.add(cache_key)

    try:
        entry = _get_config_entry(hass)
        if entry is None:
            return

        host       = _entry_value(entry, CONF_HOST, "").rstrip("/")
        api_key    = _entry_value(entry, CONF_API_KEY, "")
        headers    = {"X-Api-Key": api_key, "Content-Type": "application/json"}
        batch_size = _entry_value(entry, CONF_SEARCH_BATCH_SIZE, 50)

        search_body: dict[str, Any] = {"type": "IMAGE", "size": batch_size}
        if album_ids:
            search_body["albumIds"] = album_ids

        _LOGGER.debug("Background refill: fetching %d IDs for %s", batch_size, cache_key)

        session = _get_session(hass)
        async with session.post(
            f"{host}/api/search/random",
            json=search_body,
            headers=headers,
            timeout=aiohttp.ClientTimeout(total=15),
        ) as resp:
            if resp.status != 200:
                _LOGGER.error("Background refill failed: HTTP %d", resp.status)
                return
            results = await resp.json()
            if results:
                hass_data.setdefault(cache_key, []).extend(
                    {"id": item["id"], "date": item.get("fileCreatedAt", "")}
                    for item in results
                )
                _LOGGER.debug(
                    "Background refill done: +%d IDs for %s (total: %d)",
                    len(results),
                    cache_key,
                    len(hass_data[cache_key]),
                )

    except aiohttp.ClientError as exc:
        _LOGGER.error("Background refill error: %s", exc)
    finally:
        refilling.discard(cache_key)


class ImmichRandomImageView(HomeAssistantView):
    """Handle requests for a random Immich image, proxied through HA."""

    url  = "/api/immich_slideshow/random_image"
    name = "api:immich_slideshow:random_image"
    requires_auth = True

    def __init__(self, hass: HomeAssistant) -> None:
        self.hass = hass

    async def get(self, request: web.Request) -> web.Response:
        """Return one random image from Immich (proxied, no CORS)."""
        entry = _get_config_entry(self.hass)
        if entry is None:
            return web.Response(status=503, text="Integration not configured.")

        host    = _entry_value(entry, CONF_HOST, "").rstrip("/")
        api_key = _entry_value(entry, CONF_API_KEY, "")
        headers = {"X-Api-Key": api_key, "Content-Type": "application/json"}

        # --- Query params ---------------------------------------------------
        # ?albums=id1,id2   optional album filter
        # ?size=thumbnail   thumbnail | preview  (overrides integration default)
        albums_param = request.rel_url.query.get("albums", "")
        album_ids    = [a for a in albums_param.split(",") if a]

        # Size: query param > integration option > fallback default
        default_size = _entry_value(entry, CONF_DEFAULT_SIZE, "thumbnail")
        size = request.rel_url.query.get("size", default_size)
        if size not in VALID_SIZES:
            size = default_size

        refill_threshold = _entry_value(entry, CONF_REFILL_THRESHOLD, 3)

        cache_key = f"cache_{','.join(sorted(album_ids)) if album_ids else 'all'}"
        hass_data = self.hass.data[DOMAIN]
        hass_data.setdefault(cache_key, [])

        session = _get_session(self.hass)

        try:
            # 1. Blocking refill only when cache is completely empty -------------
            if not hass_data[cache_key]:
                _LOGGER.debug("Cache empty, blocking refill for %s", cache_key)
                await _refill_cache(self.hass, cache_key, album_ids)
                if not hass_data[cache_key]:
                    return web.Response(status=404, text="No images found.")

            # 2. Proactive background refill when running low -------------------
            elif len(hass_data[cache_key]) <= refill_threshold:
                self.hass.async_create_task(
                    _refill_cache(self.hass, cache_key, album_ids)
                )

            # 3. Consume next asset ID — retry up to 5 on non-200 --------------
            image_data   = None
            content_type = "image/jpeg"

            for _ in range(min(5, len(hass_data[cache_key]))):
                if not hass_data[cache_key]:
                    break

                asset = hass_data[cache_key].pop(0)
                asset_id   = asset["id"]
                asset_date = asset["date"]

                async with session.get(
                    f"{host}/api/assets/{asset_id}/thumbnail",
                    params={"size": size},
                    headers=headers,
                    timeout=aiohttp.ClientTimeout(total=15),
                ) as img_resp:
                    if img_resp.status == 200:
                        content_type = img_resp.headers.get("Content-Type", "image/jpeg")
                        image_data   = await img_resp.read()
                        break
                    _LOGGER.warning("Skipping asset %s (HTTP %d)", asset_id, img_resp.status)

            if image_data is None:
                return web.Response(status=404, text="No accessible image found.")

        except aiohttp.ClientError as exc:
            _LOGGER.error("Error connecting to Immich: %s", exc)
            return web.Response(status=503, text="Cannot reach Immich server.")

        return web.Response(
            body=image_data,
            content_type=content_type,
            headers={
                "Cache-Control": "no-store",
                "X-Immich-Date": asset_date,
            },
        )


def _get_config_entry(hass: HomeAssistant):
    """Return the first config entry for the integration."""
    entries = hass.config_entries.async_entries(DOMAIN)
    return entries[0] if entries else None
    