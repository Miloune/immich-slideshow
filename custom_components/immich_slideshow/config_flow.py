"""Config Flow for Immich Slideshow integration."""
import aiohttp
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult
from homeassistant.exceptions import HomeAssistantError

from .const import CONF_API_KEY, CONF_HOST, CONF_SEARCH_BATCH_SIZE, DOMAIN

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): str,
        vol.Required(CONF_API_KEY): str,
        vol.Required(CONF_SEARCH_BATCH_SIZE, default=50): vol.All(
            vol.Coerce(int), vol.Range(min=1, max=1000)
        ),
    }
)


async def validate_input(hass: HomeAssistant, data: dict) -> dict:
    """Validate the user input allows us to connect to the Immich server."""
    host = data[CONF_HOST].rstrip("/")
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


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle the config flow for Immich Slideshow."""

    VERSION = 1

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


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidAuth(HomeAssistantError):
    """Error to indicate there is invalid auth."""
