"""Todo for Donetick integration."""
import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

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
from homeassistant.util import slugify

from .const import (
    DOMAIN,
    CONF_URL,
    CONF_TOKEN,
    CONF_SHOW_DUE_IN,
    CONF_CREATE_UNIFIED_LIST,
    CONF_CREATE_ASSIGNEE_LISTS,
    CONF_CREATE_LABEL_LISTS,
    CONF_REFRESH_INTERVAL,
    DEFAULT_REFRESH_INTERVAL,
)
from .api import DonetickApiClient
from .model import DonetickTask, DonetickMember

_LOGGER = logging.getLogger(__name__)


def _normalize_label_name(name: Optional[str]) -> Optional[str]:
    """Return a normalized version of a label name for matching."""
    if not name:
        return None
    normalized = name.strip().lower()
    return normalized or None


def _label_key(label_id: Optional[int], normalized_name: Optional[str]) -> Optional[str]:
    if label_id is not None:
        return f"id_{label_id}"
    if normalized_name:
        return f"name_{normalized_name}"
    return None


def _collect_label_descriptors(tasks: List[DonetickTask]) -> List[Dict[str, Any]]:
    """Collect unique labels present in the task list."""
    label_map: Dict[str, Dict[str, Any]] = {}
    for task in tasks:
        if not task or not task.is_active:
            continue
        if task.labels_v2:
            for label in task.labels_v2:
                normalized_name = _normalize_label_name(label.name)
                key = _label_key(label.id, normalized_name)
                if not key:
                    continue
                if key not in label_map:
                    display_name = label.name or f"Label {label.id}"
                    label_map[key] = {
                        "label_id": label.id,
                        "label_name": display_name,
                        "normalized_name": normalized_name,
                        "color": label.color,
                    }
        elif task.label_names:
            for name in task.label_names:
                normalized_name = _normalize_label_name(name)
                key = _label_key(None, normalized_name)
                if not key:
                    continue
                if key not in label_map:
                    label_map[key] = {
                        "label_id": None,
                        "label_name": name,
                        "normalized_name": normalized_name,
                        "color": None,
                    }
    return sorted(label_map.values(), key=lambda item: item["label_name"].lower())


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

    refresh_interval_seconds = config_entry.data.get(CONF_REFRESH_INTERVAL, DEFAULT_REFRESH_INTERVAL)
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
    
    # Create per-label lists if enabled
    create_label_lists = config_entry.options.get(
        CONF_CREATE_LABEL_LISTS,
        config_entry.data.get(CONF_CREATE_LABEL_LISTS, False),
    )
    if create_label_lists:
        label_descriptors = _collect_label_descriptors(coordinator.data or [])
        _LOGGER.debug("Label lists enabled in config. Found %d labels", len(label_descriptors))
        for descriptor in label_descriptors:
            entity = DonetickLabelTasksList(
                coordinator,
                config_entry,
                descriptor["label_id"],
                descriptor["label_name"],
                descriptor["normalized_name"],
                descriptor["color"],
            )
            entity._circle_members = circle_members
            entities.append(entity)
    else:
        _LOGGER.debug("Label lists not enabled in config")
    
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

    @property
    def todo_items(self) -> list[TodoItem] | None: 
        """Return a list of todo items."""
        if self.coordinator.data is None:
            return None
        
        filtered_tasks = self._filter_tasks(self.coordinator.data)
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
            
            # Convert due date to RFC3339 format if provided
            due_date = None
            if item.due:
                due_date = item.due.isoformat()
            
            result = await client.async_create_task(
                name=item.summary,
                description=item.description,
                due_date=due_date,
                created_by=created_by
            )
            _LOGGER.info("Created task '%s' with ID %d", item.summary, result.id)
            
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
                
                res = await client.async_complete_task(task_id, completed_by)
                if res.frequency_type != "once":
                    _LOGGER.debug("Task %s is recurring, updating next due date", res.name)
                    item.status = TodoItemStatus.NEEDS_ACTION
                    item.due = res.next_due_date
                    self.async_update_todo_item(item)
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
                    due_date=due_date
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
        
        # Option 1: Context-based completion
        # If this is an assignee-specific list, use that assignee
        if hasattr(self, '_member'):
            _LOGGER.debug("Using assignee from specific list: %s (ID: %d)", self._member.display_name, self._member.user_id)
            return self._member.user_id
        
        # If completing from "All Tasks", find the task's original assignee
        task_id = int(item.uid.split("--")[0])
        if self.coordinator.data:
            for task in self.coordinator.data:
                if task.id == task_id and task.assigned_to:
                    _LOGGER.debug("Using task's original assignee: %d", task.assigned_to)
                    return task.assigned_to
        
        # No default user - rely on context-based or task assignee
        
        _LOGGER.debug("No completion user determined, using default")
        return None

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


class DonetickLabelTasksList(DonetickTodoListBase):
    """Donetick label-specific tasks list entity."""

    def __init__(
        self,
        coordinator: DataUpdateCoordinator,
        config_entry: ConfigEntry,
        label_id: Optional[int],
        label_name: str,
        normalized_name: Optional[str],
        color: Optional[str] = None,
    ) -> None:
        super().__init__(coordinator, config_entry)
        self._label_id = label_id
        self._label_name = label_name or "Label"
        self._normalized_name = normalized_name
        self._label_color = color
        slug_source = slugify(self._label_name) if self._label_name else None
        if not slug_source and self._normalized_name:
            slug_source = self._normalized_name.replace(" ", "_")
        if not slug_source:
            slug_source = f"label_{label_id or 'unknown'}"
        if label_id is not None:
            slug_source = f"{slug_source}_{label_id}"
        self._attr_unique_id = f"dt_{config_entry.entry_id}_label_{slug_source}"
        self._attr_name = f"{self._label_name} Tasks"

    def _filter_tasks(self, tasks):
        """Return tasks matching this label."""
        matched_tasks: List[DonetickTask] = []
        for task in tasks:
            if not task.is_active:
                continue
            if self._task_matches_label(task):
                matched_tasks.append(task)
        return matched_tasks

    def _task_matches_label(self, task: DonetickTask) -> bool:
        if self._label_id is not None and task.labels_v2:
            for label in task.labels_v2:
                if label.id == self._label_id:
                    return True
        if self._normalized_name:
            normalized_names = task.label_names_normalized or []
            if self._normalized_name in normalized_names:
                return True
        return False

    @property
    def extra_state_attributes(self):
        attrs = super().extra_state_attributes
        attrs = dict(attrs) if attrs else {}
        attrs.update(
            {
                "label_id": self._label_id,
                "label_name": self._label_name,
            }
        )
        if self._label_color:
            attrs["label_color"] = self._label_color
        return attrs


# Keep the old class for backward compatibility
class DonetickTodoListEntity(DonetickAllTasksList):
    """Donetick Todo List entity."""
    
    """Legacy Donetick Todo List entity for backward compatibility."""
    
    def __init__(self, coordinator: DataUpdateCoordinator, config_entry: ConfigEntry) -> None:
        """Initialize the Todo List."""
        super().__init__(coordinator, config_entry)
        self._attr_unique_id = f"dt_{config_entry.entry_id}"

