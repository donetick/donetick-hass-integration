"""Calendar platform for Donetick."""
import logging
from datetime import datetime, date, timedelta
from typing import List, Optional

from homeassistant.components.calendar import CalendarEntity, CalendarEvent
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)

from .const import DOMAIN
from .model import DonetickTask, DonetickMember

_LOGGER = logging.getLogger(__name__)

# Frequency types that represent recurring chores
RECURRING_FREQUENCY_TYPES = {
    "daily",
    "weekly",
    "monthly",
    "yearly",
    "interval",
    "days_of_the_week",
    "day_of_the_month",
    "adaptive",
}


def _get_member_name(members: List[DonetickMember], user_id: Optional[int]) -> Optional[str]:
    """Resolve a user ID to a display name."""
    if user_id is None:
        return None
    for member in members:
        if member.user_id == user_id:
            return member.display_name
    return None


def _task_to_event(task: DonetickTask, members: List[DonetickMember]) -> Optional[CalendarEvent]:
    """Convert a DonetickTask to a CalendarEvent on its next_due_date."""
    if task.next_due_date is None:
        return None

    due = task.next_due_date.date() if isinstance(task.next_due_date, datetime) else task.next_due_date

    assignee = _get_member_name(members, task.assigned_to)
    description = task.description or ""
    if assignee:
        description = f"Assigned to: {assignee}\n{description}".strip()

    return CalendarEvent(
        summary=task.name,
        start=due,
        end=due + timedelta(days=1),
        description=description,
        uid=f"donetick_{task.id}",
    )


def _generate_occurrences(
    task: DonetickTask,
    members: List[DonetickMember],
    range_start: date,
    range_end: date,
) -> List[CalendarEvent]:
    """Generate calendar events for a task within a date range.

    For non-recurring tasks, returns the single event if it falls in range.
    For recurring tasks, projects future occurrences based on frequency_type and frequency.
    """
    if task.next_due_date is None:
        return []

    anchor = task.next_due_date.date() if isinstance(task.next_due_date, datetime) else task.next_due_date

    assignee = _get_member_name(members, task.assigned_to)
    description = task.description or ""
    if assignee:
        description = f"Assigned to: {assignee}\n{description}".strip()

    # Non-recurring: single event
    if task.frequency_type not in RECURRING_FREQUENCY_TYPES:
        if range_start <= anchor < range_end:
            return [CalendarEvent(
                summary=task.name,
                start=anchor,
                end=anchor + timedelta(days=1),
                description=description,
                uid=f"donetick_{task.id}",
            )]
        return []

    # Recurring: compute the interval as a timedelta
    delta = _frequency_to_delta(task.frequency_type, task.frequency)
    if delta is None:
        # Unsupported frequency — just show the next due date
        if range_start <= anchor < range_end:
            return [CalendarEvent(
                summary=task.name,
                start=anchor,
                end=anchor + timedelta(days=1),
                description=description,
                uid=f"donetick_{task.id}",
            )]
        return []

    events: List[CalendarEvent] = []
    current = anchor

    # Walk backwards to find occurrences before anchor but still in range
    if current > range_start and delta.days > 0:
        while current - delta >= range_start:
            current = current - delta

    # Walk forward through the range
    while current < range_end:
        if current >= range_start:
            events.append(CalendarEvent(
                summary=task.name,
                start=current,
                end=current + timedelta(days=1),
                description=description,
                uid=f"donetick_{task.id}_{current.isoformat()}",
            ))
        current = current + delta
        # Safety: cap at 365 events
        if len(events) >= 365:
            break

    return events


def _frequency_to_delta(frequency_type: str, frequency: int) -> Optional[timedelta]:
    """Convert a Donetick frequency type + multiplier to a timedelta."""
    freq = max(frequency, 1)
    if frequency_type == "daily" or frequency_type == "interval":
        return timedelta(days=freq)
    if frequency_type == "weekly" or frequency_type == "days_of_the_week":
        return timedelta(weeks=freq)
    if frequency_type == "monthly" or frequency_type == "day_of_the_month":
        return timedelta(days=30 * freq)
    if frequency_type == "yearly":
        return timedelta(days=365 * freq)
    # adaptive and others — can't reliably predict
    return None


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Donetick calendar from a config entry."""
    data = hass.data[DOMAIN][entry.entry_id]
    coordinator = data["coordinator"]
    circle_members = data.get("circle_members", [])

    async_add_entities([DonetickCalendar(coordinator, circle_members, entry)])


class DonetickCalendar(CoordinatorEntity, CalendarEntity):
    """A calendar entity representing Donetick chores."""

    _attr_has_entity_name = True
    _attr_name = "Chores"

    def __init__(
        self,
        coordinator: DataUpdateCoordinator,
        circle_members: List[DonetickMember],
        entry: ConfigEntry,
    ) -> None:
        """Initialize the calendar."""
        super().__init__(coordinator)
        self._circle_members = circle_members
        self._attr_unique_id = f"{entry.entry_id}_calendar"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, f"{entry.entry_id}_chores")},
            "name": "Donetick Chores",
            "manufacturer": "Donetick",
        }

    @property
    def event(self) -> Optional[CalendarEvent]:
        """Return the next upcoming event (used for the entity state)."""
        tasks: List[DonetickTask] = self.coordinator.data or []
        today = date.today()
        closest_event: Optional[CalendarEvent] = None
        closest_date: Optional[date] = None

        for task in tasks:
            if not task.is_active or task.next_due_date is None:
                continue
            due = task.next_due_date.date() if isinstance(task.next_due_date, datetime) else task.next_due_date
            if closest_date is None or due < closest_date:
                closest_date = due
                closest_event = _task_to_event(task, self._circle_members)

        return closest_event

    async def async_get_events(
        self,
        hass: HomeAssistant,
        start_date: datetime,
        end_date: datetime,
    ) -> List[CalendarEvent]:
        """Return events within a date range (called by the calendar card)."""
        tasks: List[DonetickTask] = self.coordinator.data or []
        range_start = start_date.date() if isinstance(start_date, datetime) else start_date
        range_end = end_date.date() if isinstance(end_date, datetime) else end_date

        events: List[CalendarEvent] = []
        for task in tasks:
            if not task.is_active:
                continue
            events.extend(
                _generate_occurrences(task, self._circle_members, range_start, range_end)
            )

        events.sort(key=lambda e: e.start)
        return events
