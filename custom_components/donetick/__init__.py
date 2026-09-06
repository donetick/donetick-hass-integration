"""The Donetick integration."""
import logging
from datetime import timedelta

import voluptuous as vol
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .api import DonetickApiClient
from .chore_payload import (
    ASSIGNMENT_STRATEGIES,
    FREQUENCY_TYPES,
    build_create_chore_payload,
)
from .const import (
    CONF_REFRESH_INTERVAL,
    CONF_SHOW_DUE_IN,
    CONF_TOKEN,
    CONF_URL,
    DEFAULT_REFRESH_INTERVAL,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)
PLATFORMS = [Platform.TODO, Platform.SENSOR, Platform.SWITCH, Platform.NUMBER, Platform.TEXT, Platform.CALENDAR]


SERVICE_COMPLETE_TASK = "complete_task"
SERVICE_COMPLETE_CHORE = "complete_chore"
SERVICE_CREATE_TASK = "create_task"
SERVICE_CREATE_CHORE = "create_chore"
SERVICE_UPDATE_TASK = "update_task"
SERVICE_DELETE_TASK = "delete_task"
SERVICE_SKIP_TASK = "skip_task"

COMPLETE_TASK_SCHEMA = vol.Schema({
    vol.Required("task_id"): vol.Coerce(int),
    vol.Optional("completed_by"): vol.Coerce(int),
    vol.Optional("config_entry_id"): cv.string,
})

COMPLETE_CHORE_SCHEMA = vol.Schema({
    vol.Required("chore_id"): vol.All(vol.Coerce(int), vol.Range(min=1)),
    vol.Required("completed_by"): vol.All(vol.Coerce(int), vol.Range(min=1)),
    vol.Optional("assigned_to"): vol.All(vol.Coerce(int), vol.Range(min=1)),
    vol.Optional("config_entry_id"): cv.string,
})

CREATE_TASK_SCHEMA = vol.Schema({
    vol.Required("name"): cv.string,
    vol.Optional("description"): cv.string,
    vol.Optional("due_date"): cv.string,
    vol.Optional("created_by"): vol.Coerce(int),
    vol.Optional("config_entry_id"): cv.string,
})

CREATE_CHORE_SCHEMA = vol.Schema({
    vol.Required("name"): vol.All(cv.string, vol.Length(min=1)),
    vol.Optional("description"): cv.string,
    vol.Optional("next_due_date"): cv.string,
    vol.Optional("frequency_type", default="once"): vol.In(FREQUENCY_TYPES),
    vol.Optional("frequency", default=1): vol.All(
        vol.Coerce(int), vol.Range(min=1)
    ),
    vol.Optional("frequency_metadata"): dict,
    vol.Optional("assignee_ids"): vol.All(
        cv.ensure_list,
        [vol.All(vol.Coerce(int), vol.Range(min=1))],
    ),
    vol.Optional("assigned_to"): vol.All(vol.Coerce(int), vol.Range(min=1)),
    vol.Optional("assign_strategy"): vol.In(ASSIGNMENT_STRATEGIES),
    vol.Optional("priority", default=0): vol.Coerce(int),
    vol.Optional("is_rolling"): bool,
    vol.Optional("config_entry_id"): cv.string,
})

UPDATE_TASK_SCHEMA = vol.Schema({
    vol.Required("task_id"): vol.Coerce(int),
    vol.Optional("name"): cv.string,
    vol.Optional("description"): cv.string,
    vol.Optional("due_date"): cv.string,
    vol.Optional("config_entry_id"): cv.string,
})

DELETE_TASK_SCHEMA = vol.Schema({
    vol.Required("task_id"): vol.Coerce(int),
    vol.Optional("config_entry_id"): cv.string,
})

SKIP_TASK_SCHEMA = vol.Schema({
    vol.Required("task_id"): vol.Coerce(int),
    vol.Optional("completed_by"): vol.Coerce(int),
    vol.Optional("config_entry_id"): cv.string,
})

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Donetick from a config entry."""
    hass.data.setdefault(DOMAIN, {})

    session = async_get_clientsession(hass)
    client = DonetickApiClient(
        entry.data[CONF_URL],
        entry.data[CONF_TOKEN],
        session,
    )

    refresh_interval_seconds = entry.data.get(CONF_REFRESH_INTERVAL, DEFAULT_REFRESH_INTERVAL)
    coordinator = DataUpdateCoordinator(
        hass,
        _LOGGER,
        name="donetick_chores",
        update_method=client.async_get_tasks,
        update_interval=timedelta(seconds=refresh_interval_seconds),
    )
    await coordinator.async_config_entry_first_refresh()

    # Fetch circle members for resolving user IDs to names
    circle_members = []
    try:
        circle_members = await client.async_get_circle_members()
    except Exception as e:
        _LOGGER.warning("Failed to fetch circle members: %s", e)

    hass.data[DOMAIN][entry.entry_id] = {
        CONF_URL: entry.data[CONF_URL],
        CONF_TOKEN: entry.data[CONF_TOKEN],
        CONF_SHOW_DUE_IN: entry.data.get(CONF_SHOW_DUE_IN, 7),
        "coordinator": coordinator,
        "client": client,
        "circle_members": circle_members,
    }
    
    # Register services before setting up platforms
    async def complete_task_handler(call: ServiceCall) -> None:
        await async_complete_task_service(hass, call)

    async def complete_chore_handler(call: ServiceCall) -> None:
        await async_complete_chore_service(hass, call)

    async def create_task_handler(call: ServiceCall) -> None:
        await async_create_task_service(hass, call)

    async def create_chore_handler(call: ServiceCall) -> None:
        await async_create_chore_service(hass, call)
    
    async def update_task_handler(call: ServiceCall) -> None:
        await async_update_task_service(hass, call)
    
    async def delete_task_handler(call: ServiceCall) -> None:
        await async_delete_task_service(hass, call)

    async def skip_task_handler(call: ServiceCall) -> None:
        await async_skip_task_service(hass, call)

    hass.services.async_register(
        DOMAIN,
        SERVICE_COMPLETE_TASK,
        complete_task_handler,
        schema=COMPLETE_TASK_SCHEMA,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_COMPLETE_CHORE,
        complete_chore_handler,
        schema=COMPLETE_CHORE_SCHEMA,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_CREATE_TASK,
        create_task_handler,
        schema=CREATE_TASK_SCHEMA,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_CREATE_CHORE,
        create_chore_handler,
        schema=CREATE_CHORE_SCHEMA,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_UPDATE_TASK,
        update_task_handler,
        schema=UPDATE_TASK_SCHEMA,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_DELETE_TASK,
        delete_task_handler,
        schema=DELETE_TASK_SCHEMA,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_SKIP_TASK,
        skip_task_handler,
        schema=SKIP_TASK_SCHEMA,
    )
    _LOGGER.debug("Registered services: %s.%s, %s.%s, %s.%s, %s.%s, %s.%s",
                  DOMAIN, SERVICE_COMPLETE_TASK, DOMAIN, SERVICE_CREATE_TASK,
                  DOMAIN, SERVICE_UPDATE_TASK, DOMAIN, SERVICE_DELETE_TASK,
                  DOMAIN, SERVICE_SKIP_TASK)
    
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    entry.add_update_listener(async_reload_entry)
    
    return True

async def async_complete_task_service(hass: HomeAssistant, call: ServiceCall) -> None:
    """Handle the complete_task service call."""
    task_id = call.data["task_id"]
    completed_by = call.data.get("completed_by")
    config_entry_id = call.data.get("config_entry_id")
    
    # Find the config entry to use
    entry = None
    if config_entry_id:
        # Check if it's a config entry ID
        entry = hass.config_entries.async_get_entry(config_entry_id)
        
        # If not found, check if it's an entity ID and extract config entry from it
        if not entry and config_entry_id.startswith("todo."):
            entity_registry = hass.helpers.entity_registry.async_get()
            entity_entry = entity_registry.async_get(config_entry_id)
            if entity_entry:
                entry = hass.config_entries.async_get_entry(entity_entry.config_entry_id)
        
        if not entry:
            _LOGGER.error("Config entry not found for: %s", config_entry_id)
            return
    else:
        # Use the first Donetick integration if no specific entry provided
        entries = [entry for entry in hass.config_entries.async_entries(DOMAIN)]
        if not entries:
            _LOGGER.error("No Donetick integration found")
            return
        entry = entries[0]
    
    # Get API client and coordinator
    config = hass.data[DOMAIN][entry.entry_id]
    client = config["client"]
    coordinator = config["coordinator"]

    try:
        result = await client.async_complete_task(task_id, completed_by)
        _LOGGER.info("Task %d completed successfully by user %s", task_id, completed_by or "default")
        await coordinator.async_request_refresh()

    except Exception as e:
        _LOGGER.error("Failed to complete task %d: %s", task_id, e)


async def async_complete_chore_service(hass: HomeAssistant, call: ServiceCall) -> None:
    """Complete a chore while recording the actual circle member who did it."""
    config_entry_id = call.data.get("config_entry_id")
    entry = await _get_config_entry(hass, config_entry_id)
    if not entry:
        raise HomeAssistantError("No matching Donetick config entry found")

    try:
        config = hass.data[DOMAIN][entry.entry_id]
    except KeyError as err:
        raise HomeAssistantError(
            f"Donetick config entry {entry.entry_id} is not loaded"
        ) from err

    try:
        await config["client"].async_complete_chore(
            call.data["chore_id"],
            call.data["completed_by"],
            assigned_to=call.data.get("assigned_to"),
        )
    except Exception as err:
        raise HomeAssistantError(f"Failed to complete Donetick chore: {err}") from err

    try:
        await config["coordinator"].async_request_refresh()
    except Exception as err:
        raise HomeAssistantError(
            "Donetick chore was completed, but Home Assistant refresh failed: "
            f"{err}"
        ) from err


async def async_create_task_service(hass: HomeAssistant, call: ServiceCall) -> None:
    """Handle the create_task service call."""
    name = call.data["name"]
    description = call.data.get("description")
    due_date = call.data.get("due_date")
    created_by = call.data.get("created_by")
    config_entry_id = call.data.get("config_entry_id")
    
    # Find the config entry to use
    entry = await _get_config_entry(hass, config_entry_id)
    if not entry:
        return
    
    # Get API client and coordinator
    config = hass.data[DOMAIN][entry.entry_id]
    client = config["client"]
    coordinator = config["coordinator"]

    try:
        result = await client.async_create_task(name, description, due_date, created_by)
        _LOGGER.info("Task '%s' created successfully with ID %d", name, result.id)
        await coordinator.async_request_refresh()

    except Exception as e:
        _LOGGER.error("Failed to create task '%s': %s", name, e)


async def async_create_chore_service(hass: HomeAssistant, call: ServiceCall) -> None:
    """Create a chore through Donetick's full API."""
    config_entry_id = call.data.get("config_entry_id")
    entry = await _get_config_entry(hass, config_entry_id)
    if not entry:
        raise HomeAssistantError("No matching Donetick config entry found")

    try:
        config = hass.data[DOMAIN][entry.entry_id]
    except KeyError as err:
        raise HomeAssistantError(
            f"Donetick config entry {entry.entry_id} is not loaded"
        ) from err
    client = config["client"]
    coordinator = config["coordinator"]

    try:
        payload = build_create_chore_payload(call.data)
        chore_id = await client.async_create_chore(payload)
    except Exception as err:
        raise HomeAssistantError(f"Failed to create Donetick chore: {err}") from err

    try:
        await coordinator.async_request_refresh()
    except Exception as err:
        raise HomeAssistantError(
            f"Donetick chore was created with ID {chore_id}, "
            f"but Home Assistant refresh failed: {err}"
        ) from err

    _LOGGER.info(
        "Chore '%s' created successfully with ID %d", payload["name"], chore_id
    )


async def async_update_task_service(hass: HomeAssistant, call: ServiceCall) -> None:
    """Handle the update_task service call."""
    task_id = call.data["task_id"]
    name = call.data.get("name")
    description = call.data.get("description")
    due_date = call.data.get("due_date")
    config_entry_id = call.data.get("config_entry_id")
    
    # Find the config entry to use
    entry = await _get_config_entry(hass, config_entry_id)
    if not entry:
        return
    
    # Get API client and coordinator
    config = hass.data[DOMAIN][entry.entry_id]
    client = config["client"]
    coordinator = config["coordinator"]

    try:
        result = await client.async_update_task(task_id, name, description, due_date)
        _LOGGER.info("Task %d updated successfully", task_id)
        await coordinator.async_request_refresh()

    except Exception as e:
        _LOGGER.error("Failed to update task %d: %s", task_id, e)

async def async_delete_task_service(hass: HomeAssistant, call: ServiceCall) -> None:
    """Handle the delete_task service call."""
    task_id = call.data["task_id"]
    config_entry_id = call.data.get("config_entry_id")
    
    # Find the config entry to use
    entry = await _get_config_entry(hass, config_entry_id)
    if not entry:
        return
    
    # Get API client and coordinator
    config = hass.data[DOMAIN][entry.entry_id]
    client = config["client"]
    coordinator = config["coordinator"]

    try:
        success = await client.async_delete_task(task_id)
        if success:
            _LOGGER.info("Task %d deleted successfully", task_id)
            await coordinator.async_request_refresh()
        else:
            _LOGGER.error("Failed to delete task %d", task_id)

    except Exception as e:
        _LOGGER.error("Failed to delete task %d: %s", task_id, e)

async def async_skip_task_service(hass: HomeAssistant, call: ServiceCall) -> None:
    """Handle the skip_task service call."""
    task_id = call.data["task_id"]
    completed_by = call.data.get("completed_by")
    config_entry_id = call.data.get("config_entry_id")

    entry = await _get_config_entry(hass, config_entry_id)
    if not entry:
        return

    config = hass.data[DOMAIN][entry.entry_id]
    client = config["client"]
    coordinator = config["coordinator"]

    try:
        result = await client.async_skip_task(task_id, completed_by)
        _LOGGER.info("Task %d skipped successfully", task_id)
        await coordinator.async_request_refresh()

    except Exception as e:
        _LOGGER.error("Failed to skip task %d: %s", task_id, e)

async def _get_config_entry(hass: HomeAssistant, config_entry_id: str = None) -> ConfigEntry:
    """Get the config entry to use for the service call."""
    entry = None
    if config_entry_id:
        # Check if it's a config entry ID
        entry = hass.config_entries.async_get_entry(config_entry_id)
        
        # If not found, check if it's an entity ID and extract config entry from it
        if not entry and config_entry_id.startswith("todo."):
            entity_registry = hass.helpers.entity_registry.async_get()
            entity_entry = entity_registry.async_get(config_entry_id)
            if entity_entry:
                entry = hass.config_entries.async_get_entry(entity_entry.config_entry_id)
        
        if not entry:
            _LOGGER.error("Config entry not found for: %s", config_entry_id)
            return None
    else:
        # Use the first Donetick integration if no specific entry provided
        entries = [entry for entry in hass.config_entries.async_entries(DOMAIN)]
        if not entries:
            _LOGGER.error("No Donetick integration found")
            return None
        entry = entries[0]
    
    return entry

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)
        
        # Remove services if this is the last config entry
        if not hass.data[DOMAIN]:
            service_names = (
                SERVICE_COMPLETE_TASK,
                SERVICE_COMPLETE_CHORE,
                SERVICE_CREATE_TASK,
                SERVICE_CREATE_CHORE,
                SERVICE_UPDATE_TASK,
                SERVICE_DELETE_TASK,
                SERVICE_SKIP_TASK,
            )
            for service_name in service_names:
                if hass.services.has_service(DOMAIN, service_name):
                    hass.services.async_remove(DOMAIN, service_name)
            _LOGGER.debug("Removed all Donetick services")
    
    return unload_ok

async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload config entry."""
    await hass.config_entries.async_reload(entry.entry_id)