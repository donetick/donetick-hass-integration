"""Todo for Donetick integration."""
import logging

from datetime import datetime, timedelta, timezone
from typing import Any
import traceback

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

from .const import DOMAIN, CONF_URL, CONF_TOKEN, CONF_SHOW_DUE_IN, CONF_SHOW_NO_DUE_DATE, CONF_CREATE_UNIFIED_LIST, CONF_CREATE_PROJECT_LISTS, CONF_CREATE_ASSIGNEE_LISTS
from .api import DonetickApiClient
from .model import DonetickProject, DonetickTask, DonetickMember

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Donetick todo platform."""
    config = hass.data[DOMAIN][config_entry.entry_id]
    coordinator = config["coordinator"]
    client = config["client"]

    entities = []
    
    # Create unified list if enabled (check options first, then data)
    create_unified = config_entry.options.get(CONF_CREATE_UNIFIED_LIST, config_entry.data.get(CONF_CREATE_UNIFIED_LIST, True))
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
        if entities and hasattr(entities[0], '_circle_members'):
            entities[0]._circle_members = circle_members
            
    except Exception as e:
        _LOGGER.error("Failed to get circle members: %s", e)
    
    # Create per-assignee lists if enabled (check options first, then data)
    create_assignee_lists = config_entry.options.get(CONF_CREATE_ASSIGNEE_LISTS, config_entry.data.get(CONF_CREATE_ASSIGNEE_LISTS, False))
    if create_assignee_lists:
        _LOGGER.debug("Assignee lists enabled in config")
        for member in circle_members:
            if member.is_active:
                _LOGGER.debug("Creating entity for member: %s (ID: %d)", member.display_name, member.user_id)
                entity = DonetickAssigneeTasksList(coordinator, config_entry, member)
                entity._circle_members = circle_members
                entities.append(entity)
    else:
        _LOGGER.debug("Assignee lists not enabled in config")

    # Create per-project lists if enabled (check options first, then data)
    create_project_lists = config_entry.options.get(CONF_CREATE_PROJECT_LISTS, config_entry.data.get(CONF_CREATE_PROJECT_LISTS, False))
    if create_project_lists:
        _LOGGER.debug("Project lists enabled in config")
        try:
            projects = await client.async_get_projects()
            _LOGGER.debug("Found %d projects", len(projects))
            for project in projects:
                entity = DonetickProjectTasksList(coordinator, config_entry, project)
                entity._circle_members = circle_members
                entities.append(entity)
        except Exception as e:
            _LOGGER.error("Failed to get projects: %s", e)
    
    _LOGGER.debug("Creating %d total entities", len(entities))
    async_add_entities(entities)

# Remove old assignee detection function since we now use circle members

class DonetickTodoListBase(CoordinatorEntity, TodoListEntity):
    """Base class for Donetick Todo List entities."""
    
    _attr_supported_features = (
        TodoListEntityFeature.CREATE_TODO_ITEM | 
        TodoListEntityFeature.UPDATE_TODO_ITEM |
        TodoListEntityFeature.DELETE_TODO_ITEM |
        TodoListEntityFeature.SET_DESCRIPTION_ON_ITEM |
        TodoListEntityFeature.SET_DUE_DATE_ON_ITEM |
        TodoListEntityFeature.SET_DUE_DATETIME_ON_ITEM
    )

    def __init__(self, coordinator: DataUpdateCoordinator, config_entry: ConfigEntry) -> None:
        """Initialize the Todo List."""
        super().__init__(coordinator)
        self._config_entry = config_entry

    def _filter_tasks(self, tasks):
        """Filter tasks based on entity type. Override in subclasses."""
        return tasks

    def _apply_due_window(self, tasks):
        """Apply the configured upcoming task window to filtered tasks."""
        show_no_due_date = self._config_entry.data.get(CONF_SHOW_NO_DUE_DATE, True)
        show_due_in = self._config_entry.data.get(CONF_SHOW_DUE_IN, 7)
        if show_due_in in (None, 0):
            if show_no_due_date:
                return tasks
            else:
                return [ task for task in tasks if task.next_due_date is not None ]

        cutoff = datetime.now(timezone.utc) + timedelta(days=show_due_in)
        return [
            task for task in tasks
            if (show_no_due_date and (task.next_due_date is None or task.next_due_date <= cutoff)) or
                (not show_no_due_date and task.next_due_date is not None and task.next_due_date <= cutoff)
        ]

    @property
    def todo_items(self) -> list[TodoItem] | None: 
        """Return a list of todo items."""
        if self.coordinator.data is None:
            return None
        _LOGGER.debug("Generating todo items for entity %s (start with %d)", self._attr_name, len(self.coordinator.data))
        filtered_tasks = self._filter_tasks(self.coordinator.data)
        _LOGGER.debug("Generating todo items for entity %s (after filtering to: %d)", self._attr_name, len(filtered_tasks))
        filtered_tasks = self._apply_due_window(filtered_tasks)
        _LOGGER.debug("Generating todo items for entity %s (after applying due window: %d)", self._attr_name, len(filtered_tasks))
        return [
            TodoItem(
                summary=task.name,
                uid="%s--%s" % (task.id, task.next_due_date),
                status=self.get_status(task.next_due_date, task.is_active),
                due=task.next_due_date,
                description=task.description or ""
            ) for task in filtered_tasks if task.is_active
        ]

    def get_status(self, due_date: datetime, is_active: bool) -> TodoItemStatus:
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
            "donetick_project_id": hasattr(self, '_project') and self._project.id or None,
        }
        
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
        
        tasks = self._apply_due_window(self._filter_tasks(self.coordinator.data or []))
        attributes["tasks"] = [
            {"task_id": task.id, "name": task.name, "assigned_to": task.assigned_to,
             "assignee_ids": task.assignee_ids or [],
             "description": task.description,
             "next_due_date": task.next_due_date.isoformat() if task.next_due_date else None,
             "is_recurring": bool(task.frequency_type) and task.frequency_type not in ("once", "no_repeat"),
             "can_postpone": task.frequency_type not in ("once", "no_repeat", "trigger", "always")}
            for task in tasks if task.is_active
        ]
        if hasattr(self, "_member"):
            attributes["donetick_user_id"] = self._member.user_id
        return attributes

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
            created_by = None
            if hasattr(self, '_member'):
                created_by = self._member.user_id
            
            project_id = None
            if hasattr(self, '_project'):
                project_id = self._project.id
            _LOGGER.debug("Creating task '%s' in project %d by user %d", item.summary, project_id, created_by)

            # Convert due date to RFC3339 format if provided
            due_date = None
            if item.due:
                due_date = item.due.isoformat()
            
            result = await client.async_create_task(
                name=item.summary,
                description=item.description,
                due_date=due_date,
                created_by=created_by,
                project_id=project_id
            )
            _LOGGER.info("Created task '%s' in project %s with ID %d", item.summary, getattr(self, '_project_id', None), result.id)
            
        except Exception as e:
            _LOGGER.error("Failed to create task '%s': %s", item.summary, e)
            raise
        
        await self.coordinator.async_refresh()

    async def async_update_todo_item(self, item: TodoItem, context = None) -> None:
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
                completed_by = await self._get_completion_user_id(client, item, context)
                _LOGGER.debug("Completing task %s as user %s", item.uid, completed_by)
                
                res = await client.async_complete_task(task_id, completed_by)
                if res.frequency_type != "once":
                    _LOGGER.debug("Task %s is recurring, updating next due date", res.name)
                    item.status = TodoItemStatus.NEEDS_ACTION
                    item.due = res.next_due_date
            else:
                # Update task properties (summary, description, due date)
                _LOGGER.debug("Updating task %d properties", task_id)
                
                # Convert due date to RFC3339 format if provided
                due_date = None
                if item.due:
                    due_date = item.due.isoformat()
                
                await client.async_update_task(
                    task_id=task_id,
                    name=item.summary,
                    description=item.description,
                    due_date=due_date,
                )
                _LOGGER.info("Updated task %d", task_id)
                
        except Exception as e:
            _LOGGER.error("Error updating task %d: %s", task_id, e)
            raise
        
        await self.coordinator.async_refresh()

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
                else:
                    _LOGGER.error("Failed to delete task %d", task_id)
                    
            except Exception as e:
                _LOGGER.error("Error deleting task %s: %s", uid, e)
                raise
        
        await self.coordinator.async_refresh()
    
    async def _get_completion_user_id(self, client, item, context=None) -> int | None:
        """Determine who should complete this task using smart logic."""
        
        task_id = int(item.uid.split("--")[0])
        tasks = await client.async_get_tasks()
        task = next((task for task in tasks if task.id == task_id and task.is_active), None)
        if task is None or task.assigned_to is None:
            raise ValueError("Task must be active and assigned to a user before completion")
        return task.assigned_to


class DonetickAllTasksList(DonetickTodoListBase):
    """Donetick All Tasks List entity."""

    def __init__(self, coordinator: DataUpdateCoordinator, config_entry: ConfigEntry) -> None:
        """Initialize the All Tasks List."""
        super().__init__(coordinator, config_entry)
        self._attr_unique_id = f"dt_{config_entry.entry_id}_all_tasks"
        self._attr_name = "All Tasks"

    def _filter_tasks(self, tasks):
        """Return all active tasks."""
        return [task for task in tasks if task.is_active]

class DonetickProjectTasksList(DonetickTodoListBase):
    """Donetick Project-specific Tasks List entity."""

    def __init__(self, coordinator: DataUpdateCoordinator, config_entry: ConfigEntry, project: DonetickProject) -> None:
        """Initialize the Project Tasks List."""
        super().__init__(coordinator, config_entry)
        self._project = project
        self._project_id = project.id
        self._project_name = project.name
        self._attr_unique_id = f"dt_{config_entry.entry_id}_project_{project.id}_tasks"
        self._attr_name = f"{project.name} Tasks"

    def _filter_tasks(self, tasks):
        """Return tasks belonging to this project."""
        filtered_tasks = [task for task in tasks if task.is_active and task.project_id == self._project_id]
        _LOGGER.debug("Project %d has %d tasks", self._project_id, len(filtered_tasks))
        return filtered_tasks

class DonetickAssigneeTasksList(DonetickTodoListBase):
    """Donetick Assignee-specific Tasks List entity."""

    def __init__(self, coordinator: DataUpdateCoordinator, config_entry: ConfigEntry, member: DonetickMember) -> None:
        """Initialize the Assignee Tasks List."""
        super().__init__(coordinator, config_entry)
        self._member = member
        self._attr_unique_id = f"dt_{config_entry.entry_id}_{member.user_id}_tasks"
        self._attr_name = f"{member.display_name}'s Tasks"

    def _filter_tasks(self, tasks):
        """Return tasks assigned to this member."""
        return [task for task in tasks if task.is_active and task.assigned_to == self._member.user_id]

# Keep the old class for backward compatibility
class DonetickTodoListEntity(DonetickAllTasksList):
    """Donetick Todo List entity."""
    
    """Legacy Donetick Todo List entity for backward compatibility."""
    
    def __init__(self, coordinator: DataUpdateCoordinator, config_entry: ConfigEntry) -> None:
        """Initialize the Todo List."""
        super().__init__(coordinator, config_entry)
        self._attr_unique_id = f"dt_{config_entry.entry_id}"

