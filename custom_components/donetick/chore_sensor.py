"""Donetick chore sensor entities."""
import logging
from typing import Any

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)

from .const import DOMAIN
from .model import DonetickMember, DonetickTask

_LOGGER = logging.getLogger(__name__)


async def async_setup_chore_sensors(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Donetick chore sensor entities."""
    config = hass.data[DOMAIN][config_entry.entry_id]
    coordinator = config["coordinator"]

    entities = {
        task.id: DonetickChoreSensor(coordinator, config_entry, task.id)
        for task in coordinator.data or [] if task.is_active
    }

    _LOGGER.debug("Creating %d chore sensor entities", len(entities))
    if entities:
        async_add_entities(list(entities.values()))

    # Listen for coordinator updates to add/remove sensors as chores change
    _track_new_chores(hass, coordinator, config_entry, async_add_entities, entities)


def _track_new_chores(
    hass: HomeAssistant,
    coordinator: DataUpdateCoordinator,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
    entities: dict[int, "DonetickChoreSensor"],
) -> None:
    """Track coordinator updates and add or remove sensors as chores change."""

    @callback
    def _on_coordinator_update() -> None:
        # None is a failed refresh. An empty list means every chore is gone.
        if coordinator.data is None:
            return

        current_ids = {task.id for task in coordinator.data if task.is_active}
        new_entities = {
            task_id: DonetickChoreSensor(coordinator, config_entry, task_id)
            for task_id in current_ids - entities.keys()
        }
        if new_entities:
            entities.update(new_entities)
            async_add_entities(list(new_entities.values()))

        for task_id in entities.keys() - current_ids:
            entity = entities.pop(task_id)
            _remove_entity(hass, entity)

    coordinator.async_add_listener(_on_coordinator_update)


def _remove_entity(hass: HomeAssistant, entity: "DonetickChoreSensor") -> None:
    """Remove a deleted chore's registry entry and its live state."""
    registry = er.async_get(hass)
    entity_id = registry.async_get_entity_id("sensor", DOMAIN, entity.unique_id)
    if entity_id:
        _LOGGER.debug("Removing sensor for deleted chore %s", entity.unique_id)
        registry.async_remove(entity_id)
    # Removing the registry entry alone leaves the current state unavailable
    # until Home Assistant restarts.
    if entity.hass is not None:
        hass.async_create_task(entity.async_remove(force_remove=True))


class DonetickChoreSensor(CoordinatorEntity, SensorEntity):
    """Sensor entity for a single Donetick chore."""

    def __init__(
        self,
        coordinator: DataUpdateCoordinator,
        config_entry: ConfigEntry,
        task_id: int,
    ) -> None:
        """Initialize the chore sensor."""
        super().__init__(coordinator)
        self._task_id = task_id
        self._config_entry = config_entry
        self._attr_unique_id = f"dt_chore_{config_entry.entry_id}_{task_id}"

    @property
    def _task(self) -> DonetickTask | None:
        """Find this sensor's task in the coordinator data."""
        if not self.coordinator.data:
            return None
        for task in self.coordinator.data:
            if task.id == self._task_id:
                return task
        return None

    @property
    def available(self) -> bool:
        """Return True if the task still exists."""
        return self._task is not None and super().available

    @property
    def name(self) -> str:
        """Return the chore name."""
        task = self._task
        return task.name if task else f"Chore {self._task_id}"

    @property
    def native_value(self) -> str | None:
        """Return the chore name as the sensor state."""
        task = self._task
        return task.name if task else None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Expose chore metadata as attributes."""
        task = self._task
        if not task:
            return {}

        attrs = {
            "task_id": task.id,
            "assigned_to": self._resolve_user_name(task.assigned_to),
            "assigned_to_user_id": task.assigned_to,
            "next_due_date": task.next_due_date.isoformat() if task.next_due_date else None,
            "frequency_type": task.frequency_type,
            "frequency": task.frequency,
            "interval_type": task.interval_type,
            "points": task.points,
            "priority": task.priority,
            "labels": task.labels,
            "is_active": task.is_active,
            "description": task.description,
        }
        return attrs

    def _resolve_user_name(self, user_id: int | None) -> str | None:
        """Resolve a user ID to a display name using circle members."""
        if user_id is None:
            return None
        config = self.hass.data[DOMAIN].get(self._config_entry.entry_id, {})
        members: list[DonetickMember] = config.get("circle_members", [])
        for member in members:
            if member.user_id == user_id:
                return member.display_name or member.username
        return str(user_id)

    @property
    def device_info(self) -> dict[str, Any]:
        """Return device information."""
        return {
            "identifiers": {(DOMAIN, f"chores_{self._config_entry.entry_id}")},
            "name": "Donetick Chores",
            "manufacturer": "Donetick",
            "model": "Chores",
        }
