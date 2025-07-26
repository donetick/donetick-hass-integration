"""Todo for Donetick integration."""
import logging
from datetime import datetime, timedelta
from typing import Any

from homeassistant.components.todo import (
    TodoItem,
    TodoItemStatus,
    TodoListEntity,
    TodoListEntityFeature, 
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DOMAIN, CONF_URL, CONF_TOKEN, CONF_SHOW_DUE_IN
from .api import DonetickApiClient
from .model import DonetickTask
from .coordinator import DonetickDataUpdateCoordinator
from .entity import DonetickEntity

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Donetick todo platform."""
    coordinator = hass.data[DOMAIN][config_entry.entry_id]
    async_add_entities([DonetickTodoListEntity(coordinator, config_entry)])

class DonetickTodoListEntity(DonetickEntity, TodoListEntity):
    """Donetick Todo List entity."""
    
    _attr_supported_features = (
        TodoListEntityFeature.UPDATE_TODO_ITEM
    )

    def __init__(self, coordinator: DonetickDataUpdateCoordinator, config_entry: ConfigEntry) -> None:
        """Initialize the Todo List."""
        super().__init__(coordinator)
        self._config_entry = config_entry
        self._attr_unique_id = f"{config_entry.entry_id}"

    @property
    def todo_items(self) -> list[TodoItem] | None: 
        """Return a list of todo items."""
        if self.coordinator.data is None or self.coordinator.data.get("tasks") is None:
            return None
        return [  TodoItem(
            summary=task.name,
            uid="%s--%s" % (task.id, task.next_due_date),
            status=self.get_status(task.next_due_date, task.is_active),
            due=task.next_due_date,
            description=f"{self._config_entry.data[CONF_URL]}/chore/{task.id}"
        ) for task in self.coordinator.data["tasks"] if task.is_active ]

    def get_status(self, due_date: datetime, is_active: bool) -> TodoItemStatus:
        """Return the status of the task."""
        if not is_active:
            return TodoItemStatus.COMPLETED
        return TodoItemStatus.NEEDS_ACTION 

    async def async_update_todo_item(self, item: TodoItem) -> None:
        """Update a todo item."""
        if not self.coordinator.data:
            return None
        if item.status == TodoItemStatus.COMPLETED:
            try:
                session = async_get_clientsession(self.hass)
                client = DonetickApiClient(
                    self._config_entry.data[CONF_URL],
                    self._config_entry.data[CONF_TOKEN],
                    session,
                )
                res = await client.async_complete_task(item.uid.split("--")[0])
                if res.frequency_type!= "once":
                    item.status = TodoItemStatus.NEEDS_ACTION
                    item.due = res.next_due_date
                    self.async_update_todo_item(item)


            except Exception as e:
                _LOGGER.error("Error completing task from Donetick: %s", e)
        else:
            pass
 
        await self.coordinator.async_refresh()
