"""Config Flow for Immich Slideshow integration."""
import aiohttp
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import HomeAssistant, callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.selector import (
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)

from .const import (
    CONF_API_KEY,
    CONF_HOST,
    CONF_SEARCH_BATCH_SIZE,
    CONF_DEFAULT_SIZE,
    CONF_REFILL_THRESHOLD,
    DOMAIN,
)

# ─── Schemas ──────────────────────────────────────────────────────────────────

_API_KEY_SELECTOR = TextSelector(
    TextSelectorConfig(type=TextSelectorType.PASSWORD)
)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): str,
        vol.Required(CONF_API_KEY): _API_KEY_SELECTOR,
        vol.Required(CONF_SEARCH_BATCH_SIZE, default=50): vol.All(
            vol.Coerce(int), vol.Range(min=1, max=1000)
        ),
        vol.Required(CONF_DEFAULT_SIZE, default="thumbnail"): vol.In(["thumbnail", "preview"]),
        vol.Required(CONF_REFILL_THRESHOLD, default=3): vol.All(
            vol.Coerce(int), vol.Range(min=1, max=20)
        ),
    }
)


def _options_schema(current: dict) -> vol.Schema:
    """Build the options schema pre-filled with current values."""
    return vol.Schema(
        {
            vol.Required(CONF_HOST, default=current.get(CONF_HOST, "")): str,
            vol.Required(CONF_API_KEY, default=current.get(CONF_API_KEY, "")): _API_KEY_SELECTOR,
            vol.Required(
                CONF_SEARCH_BATCH_SIZE,
                default=current.get(CONF_SEARCH_BATCH_SIZE, 50),
            ): vol.All(vol.Coerce(int), vol.Range(min=1, max=1000)),
            vol.Required(
                CONF_DEFAULT_SIZE,
                default=current.get(CONF_DEFAULT_SIZE, "thumbnail"),
            ): vol.In(["thumbnail", "preview"]),
            vol.Required(
                CONF_REFILL_THRESHOLD,
                default=current.get(CONF_REFILL_THRESHOLD, 3),
            ): vol.All(vol.Coerce(int), vol.Range(min=1, max=20)),
        }
    )


# ─── Validation ───────────────────────────────────────────────────────────────

async def validate_input(hass: HomeAssistant, data: dict) -> dict:
    """Validate the user input allows us to connect to the Immich server."""
    host    = data[CONF_HOST].rstrip("/")
    api_key = data[CONF_API_KEY]

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"{host}/api/server/ping",
                headers={"X-Api-Key": api_key},
                timeout=aiohttp.ClientTimeout(total=10),
            ) as resp:
                if resp.status == 401:
                    raise InvalidAuth
                if resp.status != 200:
                    raise CannotConnect
    except aiohttp.ClientError as exc:
        raise CannotConnect from exc

    return {"title": f"Immich Slideshow ({host})"}


# ─── Config Flow (initial setup) ──────────────────────────────────────────────

class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle the config flow for Immich Slideshow."""

    VERSION = 1

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: config_entries.ConfigEntry) -> "OptionsFlow":
        """Return the options flow handler."""
        return OptionsFlow(config_entry)

    async def async_step_user(
        self, user_input: dict | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        errors: dict = {}

        if user_input is not None:
            try:
                info = await validate_input(self.hass, user_input)
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except Exception:  # noqa: BLE001
                errors["base"] = "unknown"
            else:
                return self.async_create_entry(title=info["title"], data=user_input)

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_DATA_SCHEMA,
            errors=errors,
        )


# ─── Options Flow (edit after setup) ─────────────────────────────────────────

class OptionsFlow(config_entries.OptionsFlow):
    """Handle options for Immich Slideshow (accessible via the Configure button)."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        self._config_entry = config_entry

    async def async_step_init(
        self, user_input: dict | None = None
    ) -> FlowResult:
        """Show the options form."""
        errors: dict = {}

        # Merge data + options so the form always reflects the active values.
        current = {**self._config_entry.data, **self._config_entry.options}

        if user_input is not None:
            try:
                await validate_input(self.hass, user_input)
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except Exception:  # noqa: BLE001
                errors["base"] = "unknown"
            else:
                # Invalidate all caches so the new settings take effect immediately.
                hass_data = self.hass.data.get(DOMAIN, {})
                for key in list(hass_data.keys()):
                    if key.startswith("cache_"):
                        hass_data.pop(key)

                return self.async_create_entry(title="", data=user_input)

        return self.async_show_form(
            step_id="init",
            data_schema=_options_schema(current),
            errors=errors,
        )


# ─── Errors ───────────────────────────────────────────────────────────────────

class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidAuth(HomeAssistantError):
    """Error to indicate there is invalid auth."""
