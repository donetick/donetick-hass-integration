"""Todo for Donetick integration."""
from __future__ import annotations

import hashlib
import logging
from datetime import datetime, timedelta, timezone
from typing import Any

from homeassistant.components.todo import (
    TodoItem,
    TodoItemStatus,
    TodoListEntity,
    TodoListEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.util import dt as dt_util

from .const import (
    DOMAIN,
    CONF_URL,
    CONF_TOKEN,
    CONF_SHOW_DUE_IN,
    CONF_SHOW_ONLY_TODAY,
    CONF_CREATE_UNIFIED_LIST,
    CONF_CREATE_ASSIGNEE_LISTS,
    CONF_REFRESH_INTERVAL,
    DEFAULT_REFRESH_INTERVAL,
)
from .api import DonetickApiClient
from .model import DonetickTask, DonetickMember

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Donetick todo platform."""
    session = async_get_clientsession(hass)
    client = DonetickApiClient(
        hass.data[DOMAIN][config_entry.entry_id][CONF_URL],
        hass.data[DOMAIN][config_entry.entry_id][CONF_TOKEN],
        session,
    )

    refresh_interval_seconds = config_entry.data.get(
        CONF_REFRESH_INTERVAL,
        DEFAULT_REFRESH_INTERVAL,
    )
    coordinator = DataUpdateCoordinator(
        hass,
        _LOGGER,
        name="donetick_todo",
        update_method=client.async_get_tasks,
        update_interval=timedelta(seconds=refresh_interval_seconds),
    )

    await coordinator.async_config_entry_first_refresh()

    entities = []

    # Create unified list if enabled (check options first, then data)
    create_unified = config_entry.options.get(
        CONF_CREATE_UNIFIED_LIST,
        config_entry.data.get(CONF_CREATE_UNIFIED_LIST, True),
    )
    if create_unified:
        entity = DonetickAllTasksList(coordinator, config_entry)
        entity._circle_members = []  # Will be set after we get members
        entities.append(entity)

    # Get circle members for all entities (useful for custom cards)
    circle_members = []
    try:
        circle_members = await client.async_get_circle_members()
        _LOGGER.debug("Found %d circle members", len(circle_members))

        # Set circle members on unified entity if it exists
        if entities and hasattr(entities[0], "_circle_members"):
            entities[0]._circle_members = circle_members

    except Exception as e:
        _LOGGER.error("Failed to get circle members: %s", e)

    # Create per-assignee lists if enabled (check options first, then data)
    create_assignee_lists = config_entry.options.get(
        CONF_CREATE_ASSIGNEE_LISTS,
        config_entry.data.get(CONF_CREATE_ASSIGNEE_LISTS, False),
    )
    if create_assignee_lists:
        _LOGGER.debug("Assignee lists enabled in config")
        for member in circle_members:
            if member.is_active:
                _LOGGER.debug(
                    "Creating entity for member: %s (ID: %d)",
                    member.display_name,
                    member.user_id,
                )
                entity = DonetickAssigneeTasksList(
                    coordinator,
                    config_entry,
                    member,
                )
                entity._circle_members = circle_members
                entities.append(entity)
    else:
        _LOGGER.debug("Assignee lists not enabled in config")

    _LOGGER.debug("Creating %d total entities", len(entities))
    async_add_entities(entities)

# Remove old assignee detection function since we now use circle members


class DonetickTodoListBase(CoordinatorEntity, TodoListEntity):
    """Base class for Donetick Todo List entities."""

    _attr_supported_features = (
        TodoListEntityFeature.CREATE_TODO_ITEM
        | TodoListEntityFeature.UPDATE_TODO_ITEM
        | TodoListEntityFeature.DELETE_TODO_ITEM
        | TodoListEntityFeature.SET_DESCRIPTION_ON_ITEM
        | TodoListEntityFeature.SET_DUE_DATE_ON_ITEM
        | TodoListEntityFeature.SET_DUE_DATETIME_ON_ITEM
    )

    def __init__(
        self,
        coordinator: DataUpdateCoordinator,
        config_entry: ConfigEntry,
    ) -> None:
        """Initialize the Todo List."""
        super().__init__(coordinator)
        self._config_entry = config_entry
        self._display_tasks: list[DonetickTask] = []
        self._tasks_checksum: str | None = None
        self._attr_todo_items: list[TodoItem] | None = None
        raw_show_due_in = config_entry.options.get(
            CONF_SHOW_DUE_IN,
            config_entry.data.get(CONF_SHOW_DUE_IN, 7),
        )
        self._show_due_in_days = self._coerce_show_due_in(raw_show_due_in)
        raw_show_only_today = config_entry.options.get(
            CONF_SHOW_ONLY_TODAY,
            config_entry.data.get(CONF_SHOW_ONLY_TODAY, False),
        )
        if isinstance(raw_show_only_today, bool):
            self._show_only_today = raw_show_only_today
        elif isinstance(raw_show_only_today, str):
            normalized_value = raw_show_only_today.lower()
            self._show_only_today = normalized_value in ("true", "1", "yes")
        else:
            self._show_only_today = bool(raw_show_only_today)

    def _filter_tasks(self, tasks):
        """Filter tasks based on entity type. Override in subclasses."""
        return tasks

    def _get_display_tasks(self) -> list[DonetickTask]:
        """Return tasks that should be exposed to Home Assistant."""
        if not self.coordinator or not self.coordinator.data:
            return []

        filtered_tasks = self._filter_tasks(self.coordinator.data)
        filtered_tasks = self._filter_by_due_window(filtered_tasks)
        return [task for task in filtered_tasks if task.is_active]

    def _build_todo_items(self, tasks: list[DonetickTask]) -> list[TodoItem]:
        """Convert Donetick tasks into Home Assistant todo items."""
        return [
            TodoItem(
                summary=task.name,
                uid="%s--%s" % (task.id, task.next_due_date),
                status=self.get_status(task.next_due_date, task.is_active),
                due=task.next_due_date,
                description=task.description or "",
            )
            for task in tasks
        ]

    def _calculate_checksum(self, tasks: list[DonetickTask]) -> str | None:
        """Generate a signature for the current task list."""
        if not tasks:
            return None

        sorted_tasks = sorted(tasks, key=lambda task: task.id)
        signature_parts: list[str] = []
        for task in sorted_tasks:
            due_part = (
                task.next_due_date.isoformat()
                if task.next_due_date
                else ""
            )
            updated_part = getattr(task, "updated_at", "") or ""
            signature_parts.append(
                ":".join(
                    (
                        str(task.id),
                        due_part,
                        str(int(task.is_active)),
                        updated_part,
                    )
                )
            )

        signature_source = "|".join(signature_parts)
        return hashlib.sha256(signature_source.encode()).hexdigest()[:12]

    @staticmethod
    def _coerce_show_due_in(value: Any) -> int | None:
        """Validate the show_due_in configuration value."""
        if value is None:
            return None
        try:
            coerced = max(0, int(value))
        except (TypeError, ValueError):
            _LOGGER.warning(
                "Invalid show_due_in value '%s'. "
                "Falling back to 7 days.",
                value,
            )
            return 7
        return coerced

    @staticmethod
    def _normalize_due_date(due_date: datetime) -> datetime:
        """Return a timezone-aware due date in UTC."""
        if due_date.tzinfo is None:
            return due_date.replace(tzinfo=timezone.utc)
        return due_date.astimezone(timezone.utc)

    def _filter_by_due_window(self, tasks):
        """Filter tasks so only those within the configured window remain."""
        if self._show_due_in_days is None:
            return self._filter_today_only(tasks)

        now_utc = datetime.now(timezone.utc)
        cutoff = now_utc + timedelta(days=self._show_due_in_days)
        filtered = []
        for task in tasks:
            if task.next_due_date is None:
                filtered.append(task)
                continue

            normalized_due = self._normalize_due_date(task.next_due_date)
            if normalized_due <= cutoff:
                filtered.append(task)

        return self._filter_today_only(filtered)

    def _filter_today_only(self, tasks):
        """Filter tasks to those due today, overdue, or without due dates."""
        if not self._show_only_today:
            return tasks

        now_local = dt_util.now()
        start_of_today = dt_util.start_of_local_day(now_local)
        end_of_today = start_of_today + timedelta(days=1)
        filtered = []
        for task in tasks:
            if task.next_due_date is None:
                _LOGGER.debug(
                    "Including task %s with no due date for today-only filter",
                    task.id,
                )
                filtered.append(task)
                continue

            normalized_due = self._normalize_due_date(task.next_due_date)
            local_due = dt_util.as_local(normalized_due)
            if local_due <= end_of_today:
                _LOGGER.debug(
                    "Including task %s due %s (local %s) <= end of today %s",
                    task.id,
                    normalized_due,
                    local_due,
                    end_of_today,
                )
                filtered.append(task)
            else:
                _LOGGER.debug(
                    "Excluding task %s due %s (local %s) > end of today %s",
                    task.id,
                    normalized_due,
                    local_due,
                    end_of_today,
                )

        return filtered

    @property
    def todo_items(self) -> list[TodoItem] | None:
        """Return a list of todo items."""
        return self._attr_todo_items

    def get_status(
        self, due_date: datetime | None, is_active: bool
    ) -> TodoItemStatus:
        """Return the status of the task."""
        if not is_active:
            return TodoItemStatus.COMPLETED
        return TodoItemStatus.NEEDS_ACTION
    
    @property
    def extra_state_attributes(self):
        """Return additional state attributes for custom cards."""
        attributes = {
            "config_entry_id": self._config_entry.entry_id,
            "donetick_url": self._config_entry.data[CONF_URL],
        }
        attributes["show_due_in_days"] = self._show_due_in_days
        attributes["show_only_today"] = self._show_only_today
        
        # Add circle members data for custom card user selection
        if hasattr(self, '_circle_members'):
            attributes["circle_members"] = [
                {
                    "user_id": member.user_id,
                    "display_name": member.display_name,
                    "username": member.username,
                }
                for member in self._circle_members
            ]

        attributes["tasks_checksum"] = self._tasks_checksum
        
        return attributes

    @callback
    def _handle_coordinator_update(self) -> None:
        """React to coordinator updates with filtered task cache."""
        if not self.coordinator.data:
            self._display_tasks = []
            self._attr_todo_items = []
            self._tasks_checksum = None
        else:
            self._display_tasks = self._get_display_tasks()
            self._attr_todo_items = self._build_todo_items(self._display_tasks)
            self._tasks_checksum = self._calculate_checksum(
                self._display_tasks
            )

        super()._handle_coordinator_update()

    async def async_create_todo_item(self, item: TodoItem) -> None:
        """Create a todo item."""
        session = async_get_clientsession(self.hass)
        client = DonetickApiClient(
            self._config_entry.data[CONF_URL],
            self._config_entry.data[CONF_TOKEN],
            session,
        )
        
        try:
            # Determine the created_by user for assignee lists
            created_by: int | None = None
            if hasattr(self, "_member"):
                created_by = self._member.user_id

            # Convert due date to RFC3339 format if provided
            due_date: str | None = None
            if item.due:
                due_date = item.due.isoformat()

            create_kwargs: dict[str, Any] = {
                "name": item.summary,
            }
            if item.description is not None:
                create_kwargs["description"] = item.description
            if due_date is not None:
                create_kwargs["due_date"] = due_date
            if created_by is not None:
                create_kwargs["created_by"] = created_by

            result = await client.async_create_task(**create_kwargs)
            _LOGGER.info(
                "Created task '%s' with ID %d",
                item.summary,
                result.id,
            )
            
        except Exception as e:
            _LOGGER.error("Failed to create task '%s': %s", item.summary, e)
            raise
        
        await self.coordinator.async_refresh()

    async def async_update_todo_item(
        self, item: TodoItem, context: Any | None = None
    ) -> None:
        """Update a todo item."""
        _LOGGER.debug("Update todo item: %s %s", item.uid, item.status)
        if not self.coordinator.data:
            return None
        
        session = async_get_clientsession(self.hass)
        client = DonetickApiClient(
            self._config_entry.data[CONF_URL],
            self._config_entry.data[CONF_TOKEN],
            session,
        )
        
        task_id = int(item.uid.split("--")[0])
        
        try:
            if item.status == TodoItemStatus.COMPLETED:
                # Complete the task
                _LOGGER.debug("Completing task %s", item.uid)
                # Determine who should complete this task using smart logic
                completed_by = await self._get_completion_user_id(
                    client, item, context
                )
                
                if completed_by is not None:
                    updated_task = await client.async_complete_task(
                        task_id,
                        completed_by,
                    )
                else:
                    updated_task = await client.async_complete_task(task_id)
                self._apply_task_update(updated_task)
                _LOGGER.debug(
                    "Task %d completion synced with coordinator cache",
                    task_id
                )
            else:
                # Update task properties (summary, description, due date)
                _LOGGER.debug("Updating task %d properties", task_id)
                
                # Convert due date to RFC3339 format if provided
                due_date: str | None = None
                if item.due:
                    due_date = item.due.isoformat()

                update_kwargs: dict[str, Any] = {
                    "task_id": task_id,
                    "name": item.summary,
                    "description": item.description,
                }
                if due_date is not None:
                    update_kwargs["due_date"] = due_date

                updated_task = await client.async_update_task(**update_kwargs)
                self._apply_task_update(updated_task)
                _LOGGER.info("Updated task %d", task_id)
                
        except Exception as e:
            _LOGGER.error("Error updating task %d: %s", task_id, e)
            raise
        
        await self.coordinator.async_request_refresh()

    async def async_delete_todo_items(self, uids: list[str]) -> None:
        """Delete todo items."""
        session = async_get_clientsession(self.hass)
        client = DonetickApiClient(
            self._config_entry.data[CONF_URL],
            self._config_entry.data[CONF_TOKEN],
            session,
        )
        
        for uid in uids:
            try:
                task_id = int(uid.split("--")[0])
                success = await client.async_delete_task(task_id)
                if success:
                    _LOGGER.info("Deleted task %d", task_id)
                    self._remove_task_from_cache(task_id)
                else:
                    _LOGGER.error("Failed to delete task %d", task_id)
                    
            except Exception as e:
                _LOGGER.error("Error deleting task %s: %s", uid, e)
                raise
        
        await self.coordinator.async_request_refresh()
    
    async def _get_completion_user_id(
        self, client, item, context=None
    ) -> int | None:
        """Determine who should complete this task using smart logic."""
        
        # Option 1: Context-based completion
        # If this is an assignee-specific list, use that assignee
        if hasattr(self, '_member'):
            _LOGGER.debug(
                "Using assignee from specific list: %s (ID: %d)",
                self._member.display_name,
                self._member.user_id
            )
            return self._member.user_id
        
        # If completing from "All Tasks", find the task's original assignee
        task_id = int(item.uid.split("--")[0])
        if self.coordinator.data:
            for task in self.coordinator.data:
                if task.id == task_id and task.assigned_to:
                    _LOGGER.debug(
                        "Using task's original assignee: %d",
                        task.assigned_to
                    )
                    return task.assigned_to
        
        # No default user - rely on context-based or task assignee
        
        _LOGGER.debug("No completion user determined, using default")
        return None

    def _apply_task_update(self, updated_task: DonetickTask) -> None:
        """Merge updated task into coordinator cache and notify listeners."""
        current_tasks = list(self.coordinator.data or [])
        replaced = False
        for index, task in enumerate(current_tasks):
            if task.id == updated_task.id:
                current_tasks[index] = updated_task
                replaced = True
                break
        if not replaced:
            current_tasks.append(updated_task)

        self.coordinator.async_set_updated_data(current_tasks)

    def _remove_task_from_cache(self, task_id: int) -> None:
        """Remove a task from the coordinator cache and notify listeners."""
        current_tasks = [
            task for task in (self.coordinator.data or [])
            if task.id != task_id
        ]

        self.coordinator.async_set_updated_data(current_tasks)


class DonetickAllTasksList(DonetickTodoListBase):
    """Donetick All Tasks List entity."""

    def __init__(
        self, coordinator: DataUpdateCoordinator, config_entry: ConfigEntry
    ) -> None:
        """Initialize the All Tasks List."""
        super().__init__(coordinator, config_entry)
        self._attr_unique_id = f"dt_{config_entry.entry_id}_all_tasks"
        self._attr_name = "All Tasks"

    def _filter_tasks(self, tasks):
        """Return all active tasks."""
        return [task for task in tasks if task.is_active]


class DonetickAssigneeTasksList(DonetickTodoListBase):
    """Donetick Assignee-specific Tasks List entity."""

    def __init__(
        self,
        coordinator: DataUpdateCoordinator,
        config_entry: ConfigEntry,
        member: DonetickMember
    ) -> None:
        """Initialize the Assignee Tasks List."""
        super().__init__(coordinator, config_entry)
        self._member = member
        self._attr_unique_id = (
            f"dt_{config_entry.entry_id}_{member.user_id}_tasks"
        )
        self._attr_name = f"{member.display_name}'s Tasks"

    def _filter_tasks(self, tasks):
        """Return tasks assigned to this member."""
        return [
            task for task in tasks
            if task.is_active and task.assigned_to == self._member.user_id
        ]

# Keep the old class for backward compatibility


class DonetickTodoListEntity(DonetickAllTasksList):
    """Donetick Todo List entity."""
    
    """Legacy Donetick Todo List entity for backward compatibility."""
    
    def __init__(
        self, coordinator: DataUpdateCoordinator, config_entry: ConfigEntry
    ) -> None:
        """Initialize the Todo List."""
        super().__init__(coordinator, config_entry)
        self._attr_unique_id = f"dt_{config_entry.entry_id}"

