"""Minimal Home Assistant stubs for isolated integration unit tests."""

import sys
import types
from pathlib import Path
from typing import Any, cast

ROOT = Path(__file__).parents[1]
sys.path.insert(0, str(ROOT))


class HomeAssistant:
    """Home Assistant test stub."""


class ServiceCall:
    """Service call test stub."""

    def __init__(self, data: dict[str, Any]) -> None:
        self.data = data


class ConfigEntry:
    """Config entry test stub."""


class DataUpdateCoordinator:
    """Coordinator test stub."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        self.refresh_count = 0

    async def async_config_entry_first_refresh(self) -> None:
        return None

    async def async_request_refresh(self) -> None:
        self.refresh_count += 1


class HomeAssistantError(Exception):
    """Error surfaced to Home Assistant service callers."""


class Platform:
    """Platform constants used by the integration."""

    TODO = "todo"
    SENSOR = "sensor"
    SWITCH = "switch"
    NUMBER = "number"
    TEXT = "text"
    CALENDAR = "calendar"


class TodoItem:
    """Todo item test stub."""


class TodoItemStatus:
    """Todo status test stub."""


def _string(value: Any) -> str:
    if not isinstance(value, str):
        raise TypeError("value must be a string")
    return value


def _ensure_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else [value]


homeassistant = cast(Any, types.ModuleType("homeassistant"))
core = cast(Any, types.ModuleType("homeassistant.core"))
config_entries = cast(Any, types.ModuleType("homeassistant.config_entries"))
ha_const = cast(Any, types.ModuleType("homeassistant.const"))
exceptions = cast(Any, types.ModuleType("homeassistant.exceptions"))
helpers = cast(Any, types.ModuleType("homeassistant.helpers"))
config_validation = cast(
    Any, types.ModuleType("homeassistant.helpers.config_validation")
)
aiohttp_client = cast(Any, types.ModuleType("homeassistant.helpers.aiohttp_client"))
update_coordinator = cast(
    Any, types.ModuleType("homeassistant.helpers.update_coordinator")
)
components = cast(Any, types.ModuleType("homeassistant.components"))
todo = cast(Any, types.ModuleType("homeassistant.components.todo"))

core.HomeAssistant = HomeAssistant
core.ServiceCall = ServiceCall
config_entries.ConfigEntry = ConfigEntry
ha_const.Platform = Platform
exceptions.HomeAssistantError = HomeAssistantError
config_validation.string = _string
config_validation.ensure_list = _ensure_list
aiohttp_client.async_get_clientsession = lambda hass: None
update_coordinator.DataUpdateCoordinator = DataUpdateCoordinator
todo.TodoItem = TodoItem
todo.TodoItemStatus = TodoItemStatus

homeassistant.core = core
homeassistant.config_entries = config_entries
homeassistant.const = ha_const
homeassistant.exceptions = exceptions
homeassistant.helpers = helpers
homeassistant.components = components
helpers.config_validation = config_validation
helpers.aiohttp_client = aiohttp_client
helpers.update_coordinator = update_coordinator
components.todo = todo

for name, module in {
    "homeassistant": homeassistant,
    "homeassistant.core": core,
    "homeassistant.config_entries": config_entries,
    "homeassistant.const": ha_const,
    "homeassistant.exceptions": exceptions,
    "homeassistant.helpers": helpers,
    "homeassistant.helpers.config_validation": config_validation,
    "homeassistant.helpers.aiohttp_client": aiohttp_client,
    "homeassistant.helpers.update_coordinator": update_coordinator,
    "homeassistant.components": components,
    "homeassistant.components.todo": todo,
}.items():
    sys.modules[name] = module
