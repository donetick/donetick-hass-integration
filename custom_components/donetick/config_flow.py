"""Config flow for Donetick integration."""
from typing import Any
import logging
import voluptuous as vol
import aiohttp
from datetime import timedelta

from homeassistant import config_entries
from homeassistant.core import HomeAssistant, callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers import config_validation as cv

from homeassistant.helpers.selector import (
    DurationSelector,
    DurationSelectorConfig,
)

from .const import DOMAIN, CONF_URL, CONF_TOKEN, CONF_SHOW_DUE_IN, CONF_CREATE_UNIFIED_LIST, CONF_CREATE_ASSIGNEE_LISTS, CONF_REFRESH_INTERVAL, DEFAULT_REFRESH_INTERVAL
from .api import DonetickApiClient

_LOGGER = logging.getLogger(__name__)

def _seconds_to_time_config(total_seconds: int):
    hours, remainder = divmod(total_seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    return {
        "hours": hours,
        "minutes": minutes,
        "seconds": seconds,
    }

def _config_to_seconds(config: dict[str, int]):
    return timedelta(
        hours=config["hours"],
        minutes=config["minutes"],
        seconds=config["seconds"],
    ).total_seconds()

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
            refresh_interval = DEFAULT_REFRESH_INTERVAL
            if (refresh_interval_input := user_input.get(CONF_REFRESH_INTERVAL)) is not None:
                refresh_interval = _config_to_seconds(refresh_interval_input)
            final_data = {
                **self._server_data,
                CONF_SHOW_DUE_IN: user_input.get(CONF_SHOW_DUE_IN, 7),
                CONF_CREATE_UNIFIED_LIST: user_input.get(CONF_CREATE_UNIFIED_LIST, True),
                CONF_CREATE_ASSIGNEE_LISTS: user_input.get(CONF_CREATE_ASSIGNEE_LISTS, False),
                CONF_REFRESH_INTERVAL: refresh_interval
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
                vol.Optional(CONF_REFRESH_INTERVAL, default=_seconds_to_time_config(DEFAULT_REFRESH_INTERVAL)): DurationSelector(
                    DurationSelectorConfig(enable_day=False, allow_negative=False)
                ),
            }),
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        """Get the options flow for this handler."""
        return DonetickOptionsFlowHandler(config_entry)

class DonetickOptionsFlowHandler(config_entries.OptionsFlow):
    """Handle Donetick options."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialize options flow."""
        self.entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Manage the options."""
        if user_input is not None:
            refresh_interval = DEFAULT_REFRESH_INTERVAL
            if (refresh_interval_input := user_input.get(CONF_REFRESH_INTERVAL)) is not None:
                refresh_interval = _config_to_seconds(refresh_interval_input)
            data = {
                CONF_URL: self.entry.data.get(CONF_URL),
                CONF_TOKEN: self.entry.data.get(CONF_TOKEN),
                CONF_SHOW_DUE_IN: user_input.get(CONF_SHOW_DUE_IN, 7),
                CONF_CREATE_UNIFIED_LIST: user_input.get(CONF_CREATE_UNIFIED_LIST, True),
                CONF_CREATE_ASSIGNEE_LISTS: user_input.get(CONF_CREATE_ASSIGNEE_LISTS, False),
                CONF_REFRESH_INTERVAL: refresh_interval
            }

            # Workaround to being able to use the same parameters in both config and options flow. 
            # https://community.home-assistant.io/t/configflowhandler-and-optionsflowhandler-managing-the-same-parameter/365582
            self.hass.config_entries.async_update_entry(
                self.entry, data=data, options=self.entry.options
            )
            self.hass.async_create_task(
                self.hass.config_entries.async_reload(self.entry.entry_id)
            )
            self.async_abort(reason="configuration updated")
            return self.async_create_entry(title="", data={})

        # No additional data needed for display

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema({
                vol.Optional(
                    CONF_SHOW_DUE_IN,
                    default=self.entry.data.get(CONF_SHOW_DUE_IN, 7)
                ): vol.Coerce(int),
                vol.Optional(
                    CONF_CREATE_UNIFIED_LIST,
                    default=self.entry.data.get(CONF_CREATE_UNIFIED_LIST, True)
                ): bool,
                vol.Optional(
                    CONF_CREATE_ASSIGNEE_LISTS,
                    default=self.entry.data.get(CONF_CREATE_ASSIGNEE_LISTS, False)
                ): bool,
                vol.Optional(
                    CONF_REFRESH_INTERVAL, 
                    default=_seconds_to_time_config(self.entry.data.get(CONF_REFRESH_INTERVAL, DEFAULT_REFRESH_INTERVAL))
                ): DurationSelector(DurationSelectorConfig(enable_day=False, allow_negative=False))
            }),
        )