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

VALID_SIZES   = {"thumbnail", "preview"}
SESSION_KEY   = "aiohttp_session"
REFILLING_KEY = "refilling"


def _entry_value(entry, key: str, default):
    """Read from options first, then data, then default."""
    return entry.options.get(key, entry.data.get(key, default))


def _get_session(hass: HomeAssistant) -> aiohttp.ClientSession:
    """Return (or create) the shared aiohttp session."""
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
        return
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
                    len(results), cache_key, len(hass_data[cache_key]),
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

    async def _fetch_asset(
        self,
        session: aiohttp.ClientSession,
        host: str,
        headers: dict,
        asset_id: str,
        size: str,
        asset_date: str,
    ) -> web.Response | None:
        """Fetch one asset thumbnail. Returns None if the asset is inaccessible."""
        async with session.get(
            f"{host}/api/assets/{asset_id}/thumbnail",
            params={"size": size},
            headers=headers,
            timeout=aiohttp.ClientTimeout(total=15),
        ) as img_resp:
            if img_resp.status != 200:
                _LOGGER.warning("Skipping asset %s (HTTP %d)", asset_id, img_resp.status)
                return None
            content_type = img_resp.headers.get("Content-Type", "image/jpeg")
            image_data   = await img_resp.read()

        return web.Response(
            body=image_data,
            content_type=content_type,
            headers={
                "Cache-Control": "no-store",
                "X-Immich-Date":     asset_date,
                "X-Immich-Asset-Id": asset_id,
            },
        )

    async def get(self, request: web.Request) -> web.Response:
        """Return one random image from Immich (proxied, no CORS)."""
        entry = _get_config_entry(self.hass)
        if entry is None:
            return web.Response(status=503, text="Integration not configured.")

        host    = _entry_value(entry, CONF_HOST, "").rstrip("/")
        api_key = _entry_value(entry, CONF_API_KEY, "")
        headers = {"X-Api-Key": api_key, "Content-Type": "application/json"}

        default_size = _entry_value(entry, CONF_DEFAULT_SIZE, "thumbnail")
        size = request.rel_url.query.get("size", default_size)
        if size not in VALID_SIZES:
            size = default_size

        # Session initialisée ici, avant tout usage
        session = _get_session(self.hass)

        try:
            # --- Fetch direct par asset_id (modale preview) -------------------
            explicit_asset_id = request.rel_url.query.get("asset_id", "")
            if explicit_asset_id:
                response = await self._fetch_asset(
                    session, host, headers, explicit_asset_id, size, asset_date=""
                )
                return response or web.Response(status=404, text="Asset not found.")

            # --- Fetch aléatoire depuis le cache ------------------------------
            albums_param     = request.rel_url.query.get("albums", "")
            album_ids        = [a for a in albums_param.split(",") if a]
            refill_threshold = _entry_value(entry, CONF_REFILL_THRESHOLD, 3)
            cache_key        = f"cache_{','.join(sorted(album_ids)) if album_ids else 'all'}"

            hass_data = self.hass.data[DOMAIN]
            hass_data.setdefault(cache_key, [])

            # 1. Refill bloquant si cache vide
            if not hass_data[cache_key]:
                _LOGGER.debug("Cache empty, blocking refill for %s", cache_key)
                await _refill_cache(self.hass, cache_key, album_ids)
                if not hass_data[cache_key]:
                    return web.Response(status=404, text="No images found.")

            # 2. Refill proactif en arrière-plan
            elif len(hass_data[cache_key]) <= refill_threshold:
                self.hass.async_create_task(
                    _refill_cache(self.hass, cache_key, album_ids)
                )

            # 3. Consommer le prochain asset — retry jusqu'à 5 si inaccessible
            max_attempts = min(5, len(hass_data[cache_key]))
            for _ in range(max_attempts):
                if not hass_data[cache_key]:
                    break
                asset      = hass_data[cache_key].pop(0)
                response   = await self._fetch_asset(
                    session, host, headers, asset["id"], size, asset["date"]
                )
                if response is not None:
                    return response
                # _fetch_asset a loggé le warning, on essaie le suivant

            return web.Response(status=404, text="No accessible image found.")

        except aiohttp.ClientError as exc:
            _LOGGER.error("Error connecting to Immich: %s", exc)
            return web.Response(status=503, text="Cannot reach Immich server.")


def _get_config_entry(hass: HomeAssistant):
    """Return the first config entry for the integration."""
    entries = hass.config_entries.async_entries(DOMAIN)
    return entries[0] if entries else None
    