"""Calendar platform for Donetick."""
import logging
from datetime import date, datetime, timedelta, timezone
from typing import List, Optional

from homeassistant.components.calendar import CalendarEntity, CalendarEvent
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)

from .api import DonetickApiClient
from .const import DOMAIN
from .model import DonetickChoreHistory, DonetickMember, DonetickTask

_LOGGER = logging.getLogger(__name__)

DEFAULT_SCHEDULED_DURATION = timedelta(hours=1)
DEFAULT_LOGGED_DURATION = timedelta(minutes=1)
HISTORY_LOOKBACK_DAYS = 90

CHORE_STATUS_IN_PROGRESS = 1
CHORE_STATUS_PAUSED = 2

HISTORY_STATUS_LABELS = {
    0: "Started",
    1: "Completed",
    2: "Skipped",
    3: "Pending approval",
    4: "Rejected",
    5: "Missed",
    6: "Rescheduled",
}

def _get_member_name(members: List[DonetickMember], user_id: Optional[int]) -> Optional[str]:
    """Resolve a user ID to a display name."""
    if user_id is None:
        return None
    for member in members:
        if member.user_id == user_id:
            return member.display_name
    return None


def _task_description(task: DonetickTask, members: List[DonetickMember]) -> str:
    """Build a calendar description for a task."""
    assignee = _get_member_name(members, task.assigned_to)
    description = task.description or ""
    if assignee:
        description = f"Assigned to: {assignee}\n{description}".strip()
    return description


def _is_date_only_due(value: datetime) -> bool:
    """Return true when a due datetime is acting like an all-day date marker."""
    return (value.hour, value.minute, value.second, value.microsecond) in {
        (0, 0, 0, 0),
        (23, 59, 0, 0),
        (23, 59, 59, 0),
        (23, 59, 59, 999999),
    }


def _best_task_start(task: DonetickTask) -> Optional[datetime | date]:
    """Return the best start time for an active/scheduled task."""
    if task.status in (CHORE_STATUS_IN_PROGRESS, CHORE_STATUS_PAUSED):
        return task.start_time or task.timer_updated_at or task.updated_at or task.next_due_date

    if task.next_due_date is None:
        return None

    if _is_date_only_due(task.next_due_date):
        return task.next_due_date.date()

    return task.next_due_date


def _event_end(start: datetime | date, duration: timedelta) -> datetime | date:
    """Return a calendar end value matching the start value type."""
    if not isinstance(start, datetime) and duration < timedelta(days=1):
        return start + timedelta(days=1)
    return start + duration


def _comparison_datetime(value: datetime | date) -> datetime:
    """Normalize date/datetime values for internal comparisons."""
    if not isinstance(value, datetime):
        return datetime.combine(value, datetime.min.time())
    if value.tzinfo is None:
        return value
    return value.astimezone(timezone.utc).replace(tzinfo=None)


def _event_sort_key(event: CalendarEvent) -> datetime:
    """Normalize event starts so date and datetime events sort together."""
    return _comparison_datetime(event.start)


def _event_in_range(event: CalendarEvent, range_start: datetime, range_end: datetime) -> bool:
    """Return true when a calendar event intersects the requested range."""
    start = _event_sort_key(event)
    end = _comparison_datetime(event.end)
    return start < _comparison_datetime(range_end) and end > _comparison_datetime(range_start)


def _task_to_event(task: DonetickTask, members: List[DonetickMember]) -> Optional[CalendarEvent]:
    """Convert a DonetickTask to a CalendarEvent using the best available time."""
    start = _best_task_start(task)
    if start is None:
        return None

    duration = (
        DEFAULT_LOGGED_DURATION
        if task.status in (CHORE_STATUS_IN_PROGRESS, CHORE_STATUS_PAUSED)
        else DEFAULT_SCHEDULED_DURATION
    )

    return CalendarEvent(
        summary=task.name,
        start=start,
        end=_event_end(start, duration),
        description=_task_description(task, members),
        uid=f"donetick_{task.id}",
    )


def _history_to_event(
    history: DonetickChoreHistory,
    tasks_by_id: dict[int, DonetickTask],
    members: List[DonetickMember],
) -> Optional[CalendarEvent]:
    """Convert a chore history row to a timed calendar event."""
    end = history.end_time or history.performed_at or history.updated_at or history.created_at
    if end is None:
        return None

    if history.start_time:
        start = history.start_time
    elif history.duration and history.duration > 0:
        start = end - timedelta(seconds=history.duration)
    else:
        start = end

    if history.end_time:
        event_end = history.end_time
    elif history.duration and history.duration > 0:
        event_end = end
    else:
        event_end = start + DEFAULT_LOGGED_DURATION

    if _comparison_datetime(event_end) <= _comparison_datetime(start):
        event_end = start + DEFAULT_LOGGED_DURATION

    task = tasks_by_id.get(history.chore_id)
    task_name = task.name if task else f"Donetick chore {history.chore_id}"
    status_label = HISTORY_STATUS_LABELS.get(history.status, "Logged")
    completed_by = _get_member_name(members, history.completed_by) or history.completed_by
    assigned_to = _get_member_name(members, history.assigned_to) or history.assigned_to

    description_parts = []
    if completed_by:
        description_parts.append(f"{status_label} by: {completed_by}")
    if assigned_to:
        description_parts.append(f"Assigned to: {assigned_to}")
    if history.due_date:
        description_parts.append(f"Due: {history.due_date.isoformat()}")
    if history.notes:
        description_parts.append(history.notes)

    return CalendarEvent(
        summary=f"{status_label}: {task_name}",
        start=start,
        end=event_end,
        description="\n".join(description_parts),
        uid=f"donetick_history_{history.id}",
    )


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Donetick calendar from a config entry."""
    data = hass.data[DOMAIN][entry.entry_id]
    coordinator = data["coordinator"]
    client = data["client"]
    circle_members = data.get("circle_members", [])

    async_add_entities(
        [
            DonetickCalendar(coordinator, client, circle_members, entry),
            DonetickActivityCalendar(coordinator, client, circle_members, entry),
        ]
    )


class DonetickCalendar(CoordinatorEntity, CalendarEntity):
    """A calendar entity representing Donetick chores."""

    _attr_has_entity_name = True
    _attr_name = "Chores"

    def __init__(
        self,
        coordinator: DataUpdateCoordinator,
        client: DonetickApiClient,
        circle_members: List[DonetickMember],
        entry: ConfigEntry,
    ) -> None:
        """Initialize the calendar."""
        super().__init__(coordinator)
        self._client = client
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
        closest_date: Optional[datetime] = None

        for task in tasks:
            if not task.is_active:
                continue
            event = _task_to_event(task, self._circle_members)
            if event is None:
                continue
            event_start = _event_sort_key(event)
            if event_start.date() < today:
                continue
            if closest_date is None or event_start < closest_date:
                closest_date = event_start
                closest_event = event

        return closest_event

    async def async_get_events(
        self,
        hass: HomeAssistant,
        start_date: datetime,
        end_date: datetime,
    ) -> List[CalendarEvent]:
        """Return events within a date range (called by the calendar card)."""
        tasks: List[DonetickTask] = self.coordinator.data or []
        range_start = (
            start_date
            if isinstance(start_date, datetime)
            else datetime.combine(start_date, datetime.min.time())
        )
        range_end = (
            end_date
            if isinstance(end_date, datetime)
            else datetime.combine(end_date, datetime.min.time())
        )
        events: List[CalendarEvent] = []
        for task in tasks:
            if not task.is_active:
                continue
            if task.status in (CHORE_STATUS_IN_PROGRESS, CHORE_STATUS_PAUSED) and task.start_time is None:
                detail = await self._client.async_get_task_detail(task.id)
                if detail is not None:
                    task.start_time = detail.start_time
                    task.timer_updated_at = detail.timer_updated_at
                    task.duration = detail.duration
            event = _task_to_event(task, self._circle_members)
            if event is not None and _event_in_range(event, range_start, range_end):
                events.append(event)

        events.sort(key=_event_sort_key)
        return events


class DonetickActivityCalendar(CoordinatorEntity, CalendarEntity):
    """A calendar entity representing Donetick chore activity history."""

    _attr_has_entity_name = True
    _attr_name = "Activity Log"

    def __init__(
        self,
        coordinator: DataUpdateCoordinator,
        client: DonetickApiClient,
        circle_members: List[DonetickMember],
        entry: ConfigEntry,
    ) -> None:
        """Initialize the activity log calendar."""
        super().__init__(coordinator)
        self._client = client
        self._circle_members = circle_members
        self._attr_unique_id = f"{entry.entry_id}_activity_calendar"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, f"{entry.entry_id}_chores")},
            "name": "Donetick Chores",
            "manufacturer": "Donetick",
        }

    @property
    def event(self) -> Optional[CalendarEvent]:
        """Return the next upcoming event."""
        return None

    async def async_get_events(
        self,
        hass: HomeAssistant,
        start_date: datetime,
        end_date: datetime,
    ) -> List[CalendarEvent]:
        """Return activity log events within a date range."""
        tasks: List[DonetickTask] = self.coordinator.data or []
        range_start = (
            start_date
            if isinstance(start_date, datetime)
            else datetime.combine(start_date, datetime.min.time())
        )
        range_end = (
            end_date
            if isinstance(end_date, datetime)
            else datetime.combine(end_date, datetime.min.time())
        )
        tasks_by_id = {task.id: task for task in tasks}

        now = datetime.now(timezone.utc)
        range_start_key = _comparison_datetime(range_start)
        range_end_key = _comparison_datetime(range_end)
        now_key = _comparison_datetime(now)
        if range_start_key > now_key or (range_end_key - range_start_key).days > HISTORY_LOOKBACK_DAYS:
            return []

        history_days = max((now_key - range_start_key).days + 1, 1)
        histories = await self._client.async_get_task_history(
            min(history_days, HISTORY_LOOKBACK_DAYS),
            include_members=True,
        )

        events: List[CalendarEvent] = []
        for history in histories:
            event = _history_to_event(history, tasks_by_id, self._circle_members)
            if event is not None and _event_in_range(event, range_start, range_end):
                events.append(event)

        events.sort(key=_event_sort_key)
        return events
