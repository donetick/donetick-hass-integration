"""Config flow for Donetick integration."""
from typing import Any
import voluptuous as vol
import aiohttp

from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DOMAIN, CONF_URL, CONF_TOKEN, CONF_SHOW_DUE_IN, CONF_CREATE_UNIFIED_LIST, CONF_CREATE_ASSIGNEE_LISTS
from .api import DonetickApiClient

class DonetickConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Donetick."""

    VERSION = 1
    
    def __init__(self):
        """Initialize the config flow."""
        self._server_data = {}

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        errors = {}

        if user_input is not None:
            try:
                session = async_get_clientsession(self.hass)
                client = DonetickApiClient(
                    user_input[CONF_URL],
                    user_input[CONF_TOKEN],
                    session,
                )
                # Test the API connection
                await client.async_get_tasks()

                # Store server data and proceed to options step  
                self._server_data = user_input
                return await self.async_step_options()
            except aiohttp.ClientError:
                errors["base"] = "cannot_connect"
            except Exception:  # pylint: disable=broad-except
                errors["base"] = "unknown"

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({
                vol.Required(CONF_URL): str,
                vol.Required(CONF_TOKEN): str,
            }),
            errors=errors,
        )

    async def async_step_options(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the options step."""
        if user_input is not None:
            # Combine server data with options
            final_data = {
                **self._server_data,
                CONF_SHOW_DUE_IN: user_input.get(CONF_SHOW_DUE_IN, 7),
                CONF_CREATE_UNIFIED_LIST: user_input.get(CONF_CREATE_UNIFIED_LIST, True),
                CONF_CREATE_ASSIGNEE_LISTS: user_input.get(CONF_CREATE_ASSIGNEE_LISTS, False),
            }
            
            return self.async_create_entry(
                title="Donetick",
                data=final_data
            )

        return self.async_show_form(
            step_id="options",
            data_schema=vol.Schema({
                vol.Optional(CONF_SHOW_DUE_IN, default=7): vol.Coerce(int),
                vol.Optional(CONF_CREATE_UNIFIED_LIST, default=True): bool,
                vol.Optional(CONF_CREATE_ASSIGNEE_LISTS, default=False): bool,
            }),
        )