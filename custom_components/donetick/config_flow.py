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
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
)

from .const import DOMAIN, CONF_URL, CONF_TOKEN, CONF_SHOW_DUE_IN, CONF_SHOW_NO_DUE_DATE, CONF_CREATE_PROJECT_LISTS, CONF_CREATE_UNIFIED_LIST, CONF_CREATE_ASSIGNEE_LISTS, CONF_REFRESH_INTERVAL, DEFAULT_REFRESH_INTERVAL
from .api import DonetickApiClient
from .user_mapping import username_mappings
from .const import CONF_MAP_COMPLETION_USER, CONF_USER_MAPPING, CONF_UNMAPPED_USER

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
                CONF_SHOW_NO_DUE_DATE: user_input.get(CONF_SHOW_NO_DUE_DATE, True),
                CONF_CREATE_UNIFIED_LIST: user_input.get(CONF_CREATE_UNIFIED_LIST, True),
                CONF_CREATE_PROJECT_LISTS: user_input.get(CONF_CREATE_PROJECT_LISTS, False),
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
                vol.Optional(CONF_SHOW_NO_DUE_DATE, default=True): bool,
                vol.Optional(CONF_CREATE_UNIFIED_LIST, default=True): bool,
                vol.Optional(CONF_CREATE_PROJECT_LISTS, default=False): bool,
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
        self._mapping_data = {}
        self._mapping_defaults = None
        self._username_suggestions = {}
        self._members = []
        self._users = []

    async def async_step_settings(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Manage the options."""
        if user_input is not None:
            refresh_interval = DEFAULT_REFRESH_INTERVAL
            if (refresh_interval_input := user_input.get(CONF_REFRESH_INTERVAL)) is not None:
                refresh_interval = _config_to_seconds(refresh_interval_input)
            data = {
                **self.entry.data,
                CONF_URL: self.entry.data.get(CONF_URL),
                CONF_TOKEN: self.entry.data.get(CONF_TOKEN),
                CONF_SHOW_DUE_IN: user_input.get(CONF_SHOW_DUE_IN, 7),
                CONF_SHOW_NO_DUE_DATE: user_input.get(CONF_SHOW_NO_DUE_DATE, True),
                CONF_CREATE_UNIFIED_LIST: user_input.get(CONF_CREATE_UNIFIED_LIST, True),
                CONF_CREATE_PROJECT_LISTS: user_input.get(CONF_CREATE_PROJECT_LISTS, False),
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
            step_id="settings",
            data_schema=vol.Schema({
                vol.Optional(
                    CONF_SHOW_DUE_IN,
                    default=self.entry.data.get(CONF_SHOW_DUE_IN, 7)
                ): vol.Coerce(int),
                vol.Optional(
                    CONF_SHOW_NO_DUE_DATE,
                    default=self.entry.data.get(CONF_SHOW_NO_DUE_DATE, True)
                ): bool,
                vol.Optional(
                    CONF_CREATE_UNIFIED_LIST,
                    default=self.entry.data.get(CONF_CREATE_UNIFIED_LIST, True)
                ): bool,
                vol.Optional(
                    CONF_CREATE_PROJECT_LISTS,
                    default=self.entry.data.get(CONF_CREATE_PROJECT_LISTS, False)
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
    async def async_step_init(self, user_input=None):
        return self.async_show_menu(step_id="init", menu_options=["settings", "user_mapping"])

    def _confirmed_mapping_defaults(self, user_input):
        if user_input.get("apply_username_matches", False):
            return dict(self._mapping_defaults)
        return dict(self.entry.data.get(CONF_USER_MAPPING, {}))

    def _save_mapping(self):
        if getattr(self, "_mapping_defaults", None) is not None:
            self._mapping_data["user_mapping_initialized"] = True
        self.hass.config_entries.async_update_entry(
            self.entry, data={**self.entry.data, **self._mapping_data})
        self.hass.async_create_task(self.hass.config_entries.async_reload(self.entry.entry_id))
        return self.async_create_entry(title="", data={})

    async def async_step_user_mapping(self, user_input=None):
        """Configure completion and link both accounts on the same screen."""
        errors = {}
        # Allow disabling attribution while the server is unavailable.
        if user_input is not None and not any(key.startswith("HA user: ") for key in user_input):
            self._mapping_data = {
                CONF_MAP_COMPLETION_USER: user_input[CONF_MAP_COMPLETION_USER],
                CONF_UNMAPPED_USER: user_input[CONF_UNMAPPED_USER],
                CONF_USER_MAPPING: self._confirmed_mapping_defaults(user_input),
            }
            return self._save_mapping()
        try:
            self._users = [user for user in await self.hass.auth.async_get_users()
                           if user.is_active and not user.system_generated]
            client = DonetickApiClient(self.entry.data[CONF_URL], self.entry.data[CONF_TOKEN],
                                      async_get_clientsession(self.hass))
            self._members = [member for member in await client.async_get_circle_members() if member.is_active]
        except Exception:
            _LOGGER.exception("Unable to load users for Donetick mapping")
            errors["base"] = "cannot_connect"
        data = self.entry.data
        if not errors and getattr(self, "_mapping_defaults", None) is None:
            existing = data.get(CONF_USER_MAPPING, {})
            self._mapping_defaults = (dict(existing) if data.get("user_mapping_initialized", False)
                                      else username_mappings(self._users, self._members, existing))
            self._username_suggestions = {user_id:member_id for user_id, member_id in self._mapping_defaults.items()
                                          if user_id not in existing}
        # Native select fields stay visible together, rather than opening object-editor dialogs.
        user_fields = {}
        names = [user.name or user.id for user in self._users]
        for user in self._users:
            name = user.name or user.id
            label = f"HA user: {name}" if names.count(name) == 1 else f"HA user: {name} ({user.id})"
            user_fields[label] = user.id
        if user_input is not None and not errors:
            rows = {user_id:user_input[label] for label, user_id in user_fields.items() if label in user_input}
            valid_users = {user.id for user in self._users}
            valid_members = {str(member.user_id) for member in self._members}
            mappings = self._confirmed_mapping_defaults(user_input)
            if set(rows) - valid_users:
                errors["base"] = "invalid_user"
            for user_id, target in rows.items():
                current = data.get(CONF_USER_MAPPING, {}).get(user_id)
                if target == "unmapped":
                    mappings.pop(user_id, None)
                elif target not in valid_members and target != str(current):
                    errors["base"] = "invalid_user"
                elif (not user_input.get("apply_username_matches", False)
                      and user_id in self._username_suggestions
                      and target == str(self._username_suggestions[user_id])):
                    continue
                else:
                    mappings[user_id] = int(target)
            if not errors:
                self._mapping_data = {
                    CONF_MAP_COMPLETION_USER: user_input[CONF_MAP_COMPLETION_USER],
                    CONF_UNMAPPED_USER: user_input[CONF_UNMAPPED_USER],
                    CONF_USER_MAPPING: mappings,
                }
                return self._save_mapping()
        defaults = {**data, **(user_input or {})}
        members = {member.user_id: member.display_name or member.username for member in self._members}
        mappings = data.get(CONF_USER_MAPPING, {})
        summary = "; ".join(f"{user.name}: {members.get(mappings[user.id], 'Unavailable Donetick user')}"
                            for user in self._users if user.id in mappings) or "None"
        suggested = getattr(self, "_username_suggestions", {})
        suggestions = "; ".join(f"{user.name}: {members[suggested[user.id]]}"
                                 for user in self._users if user.id in suggested)
        if suggestions:
            suggestions = ("Suggested username matches: " + suggestions +
                "\n\nReview the prefilled matches and check Apply suggested username matches to confirm them. "
                "Leave unchecked to skip unchanged suggestions. Saving completes this one-time setup.")
        row_options = [{"value":"unmapped", "label":"Not mapped"}] + [
            {"value":str(member.user_id), "label":member.display_name or member.username}
            for member in self._members]
        fields = {}
        proposed = self._mapping_defaults or mappings
        for label, user_id in user_fields.items():
            current = proposed.get(user_id)
            options = list(row_options)
            if current is not None and current not in members:
                options.append({"value":str(current), "label":f"Unavailable Donetick user ({current})"})
            default = str(current) if current is not None else "unmapped"
            fields[vol.Required(label, default=defaults.get(label, default))] = SelectSelector(
                SelectSelectorConfig(options=options, mode=SelectSelectorMode.DROPDOWN))
        return self.async_show_form(step_id="user_mapping", errors=errors,
            description_placeholders={"mappings": summary, "suggestions": suggestions}, data_schema=vol.Schema({
                **({vol.Required("apply_username_matches", default=defaults.get("apply_username_matches", False)): bool}
                   if suggested else {}),
                vol.Required(CONF_MAP_COMPLETION_USER, default=defaults.get(CONF_MAP_COMPLETION_USER, False)): bool,
                vol.Required(CONF_UNMAPPED_USER, default=defaults.get(CONF_UNMAPPED_USER, "existing")): SelectSelector(
                    SelectSelectorConfig(options=[{"value":"existing", "label":"Credit the assignee (Anyone tasks: API token owner)"},
                                                  {"value":"require_mapping", "label":"Require a mapping or explicit performer"}],
                                         mode=SelectSelectorMode.DROPDOWN)),
                **fields,
            }))
