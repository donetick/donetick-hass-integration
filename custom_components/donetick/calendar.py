"""Calendar platform for Donetick."""
import logging
from datetime import date, datetime, timedelta, timezone
from typing import List, Optional
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

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
MAX_PROJECTED_OCCURRENCES = 365

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


def _task_description(task: DonetickTask, members: List[DonetickMember]) -> str:
    """Build a calendar description for a task."""
    assignee = _get_member_name(members, task.assigned_to)
    description = task.description or ""
    if assignee:
        description = f"Assigned to: {assignee}\n{description}".strip()
    return description


def _metadata_dict(task: DonetickTask) -> dict:
    """Return frequency metadata as a dict."""
    return task.frequency_metadata if isinstance(task.frequency_metadata, dict) else {}


def _metadata_time(task: DonetickTask) -> Optional[datetime]:
    """Return the metadata time value if present."""
    time_value = _metadata_dict(task).get("time")
    if not isinstance(time_value, str) or not time_value:
        return None
    try:
        return datetime.fromisoformat(time_value.replace("Z", "+00:00"))
    except ValueError:
        _LOGGER.debug("Unable to parse Donetick frequencyMetadata.time: %s", time_value)
        return None


def _metadata_timezone(task: DonetickTask) -> timezone | ZoneInfo:
    """Return the task timezone from metadata, falling back to UTC."""
    timezone_name = _metadata_dict(task).get("timezone")
    if isinstance(timezone_name, str) and timezone_name:
        try:
            return ZoneInfo(timezone_name)
        except ZoneInfoNotFoundError:
            _LOGGER.debug("Unknown Donetick timezone %s, falling back to UTC", timezone_name)
    return timezone.utc


def _metadata_days(task: DonetickTask) -> list[str]:
    """Return lower-cased weekday names from metadata."""
    days = _metadata_dict(task).get("days")
    if not isinstance(days, list):
        return []
    normalized_days: list[str] = []
    for day in days:
        if isinstance(day, str) and day:
            normalized_days.append(day.lower())
    return normalized_days


def _metadata_months(task: DonetickTask) -> list[str]:
    """Return lower-cased month names from metadata."""
    months = _metadata_dict(task).get("months")
    if not isinstance(months, list):
        return []
    normalized_months: list[str] = []
    for month in months:
        if isinstance(month, str) and month:
            normalized_months.append(month.lower())
    return normalized_months


def _metadata_unit(task: DonetickTask) -> Optional[str]:
    """Return the interval unit from metadata."""
    unit = _metadata_dict(task).get("unit")
    return unit if isinstance(unit, str) and unit else None


def _metadata_week_pattern(task: DonetickTask) -> str:
    """Return the recurrence week pattern."""
    pattern = _metadata_dict(task).get("weekPattern")
    if not isinstance(pattern, str) or not pattern:
        return "every_week"
    return pattern


def _metadata_occurrences(task: DonetickTask) -> list[str]:
    """Return normalized occurrence values from metadata."""
    metadata = _metadata_dict(task)
    occurrences = metadata.get("occurrences")
    if isinstance(occurrences, list) and occurrences:
        normalized: list[str] = []
        for occurrence in occurrences:
            if isinstance(occurrence, int):
                normalized.append("last" if occurrence == -1 else str(occurrence))
        return normalized

    week_numbers = metadata.get("weekNumbers")
    if isinstance(week_numbers, list):
        return [str(value) for value in week_numbers if isinstance(value, int)]

    return []


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


def _normalize_occurrence_start(task: DonetickTask, due_value: datetime) -> datetime | date:
    """Normalize a due datetime to the display start used by the calendar."""
    if _is_date_only_due(due_value):
        return due_value.date()
    return due_value


def _scheduled_task_event(
    task: DonetickTask,
    members: List[DonetickMember],
    due_value: datetime,
    uid_suffix: str = "",
) -> CalendarEvent:
    """Build a scheduled task calendar event from a due datetime."""
    start = _normalize_occurrence_start(task, due_value)
    uid = f"donetick_{task.id}" if not uid_suffix else f"donetick_{task.id}_{uid_suffix}"
    return CalendarEvent(
        summary=task.name,
        start=start,
        end=_event_end(start, DEFAULT_SCHEDULED_DURATION),
        description=_task_description(task, members),
        uid=uid,
    )


def _month_last_day(year: int, month: int) -> int:
    """Return the last valid day number for a month."""
    if month == 12:
        next_month = datetime(year + 1, 1, 1, tzinfo=timezone.utc)
    else:
        next_month = datetime(year, month + 1, 1, tzinfo=timezone.utc)
    return (next_month - timedelta(days=1)).day


def _add_months(value: datetime, months: int) -> datetime:
    """Add months to a datetime, clamping the day when needed."""
    month_index = value.month - 1 + months
    year = value.year + month_index // 12
    month = month_index % 12 + 1
    day = min(value.day, _month_last_day(year, month))
    return value.replace(year=year, month=month, day=day)


def _add_years(value: datetime, years: int) -> datetime:
    """Add years to a datetime, clamping leap-day when needed."""
    try:
        return value.replace(year=value.year + years)
    except ValueError:
        return value.replace(year=value.year + years, day=28)


def _apply_due_time(task: DonetickTask, base_date: datetime) -> datetime:
    """Apply the metadata time-of-day to a base datetime."""
    metadata_time = _metadata_time(task)
    if metadata_time is None:
        return base_date

    metadata_time = metadata_time.astimezone(timezone.utc)
    return datetime(
        base_date.year,
        base_date.month,
        base_date.day,
        metadata_time.hour,
        metadata_time.minute,
        metadata_time.second,
        0,
        tzinfo=timezone.utc,
    )


def _get_nth_occurrence_in_month(value: datetime) -> int:
    """Return the 1-based weekday occurrence within the month."""
    weekday = value.weekday()
    occurrence = 0
    current = value.replace(day=1)
    while current.date() <= value.date():
        if current.weekday() == weekday:
            occurrence += 1
        current += timedelta(days=1)
    return occurrence


def _is_last_occurrence_in_month(value: datetime) -> bool:
    """Return true if this is the last weekday occurrence in the month."""
    return (value + timedelta(days=7)).month != value.month


def _get_nth_occurrence_in_quarter(value: datetime) -> int:
    """Return the 1-based weekday occurrence within the quarter."""
    quarter_start_month = ((value.month - 1) // 3) * 3 + 1
    current = value.replace(month=quarter_start_month, day=1)
    weekday = value.weekday()
    occurrence = 0
    while current.date() <= value.date():
        if current.weekday() == weekday:
            occurrence += 1
        current += timedelta(days=1)
    return occurrence


def _is_last_occurrence_in_quarter(value: datetime) -> bool:
    """Return true if this is the last weekday occurrence in the quarter."""
    current_quarter = (value.month - 1) // 3
    next_week = value + timedelta(days=7)
    return next_week.year != value.year or ((next_week.month - 1) // 3) != current_quarter


def _find_next_due_for_occurrence_pattern(
    base_date: datetime,
    days: list[str],
    occurrences: list[str],
    is_monthly: bool,
) -> Optional[datetime]:
    """Find the next due date for week-of-month or week-of-quarter schedules."""
    day_set = set(days)
    occurrence_set = set(occurrences)
    current = base_date + timedelta(days=1)

    for _ in range(730):
        weekday_name = current.strftime("%A").lower()
        if weekday_name in day_set:
            if is_monthly:
                nth = str(_get_nth_occurrence_in_month(current))
                if nth in occurrence_set or ("last" in occurrence_set and _is_last_occurrence_in_month(current)):
                    return current
            else:
                nth = str(_get_nth_occurrence_in_quarter(current))
                if nth in occurrence_set or ("last" in occurrence_set and _is_last_occurrence_in_quarter(current)):
                    return current
        current += timedelta(days=1)

    return None


def _schedule_next_due(task: DonetickTask, current_due: datetime) -> Optional[datetime]:
    """Mirror Donetick's recurrence scheduling for projecting future events."""
    frequency_type = task.frequency_type
    if frequency_type in {"once", "no_repeat", "trigger"}:
        return None

    base_date = current_due.astimezone(timezone.utc)

    if frequency_type in {"day_of_the_month", "days_of_the_week", "interval"}:
        base_date = _apply_due_time(task, base_date)

    if frequency_type == "daily":
        return base_date + timedelta(days=1)
    if frequency_type == "weekly":
        return base_date + timedelta(days=7)
    if frequency_type == "monthly":
        return _add_months(base_date, 1)
    if frequency_type == "yearly":
        return _add_years(base_date, 1)
    if frequency_type == "adaptive":
        return None
    if frequency_type == "interval":
        unit = _metadata_unit(task)
        freq = max(task.frequency, 1)
        if unit == "hours":
            return base_date + timedelta(hours=freq)
        if unit == "days":
            return base_date + timedelta(days=freq)
        if unit == "weeks":
            return base_date + timedelta(weeks=freq)
        if unit == "months":
            return _add_months(base_date, freq)
        if unit == "years":
            return _add_years(base_date, freq)
        return None
    if frequency_type == "days_of_the_week":
        days = _metadata_days(task)
        if not days:
            return None

        week_pattern = _metadata_week_pattern(task)
        if week_pattern in {"", "every_week"}:
            tzinfo = _metadata_timezone(task)
            localized_base = base_date.astimezone(tzinfo)
            for offset in range(1, 8):
                candidate = localized_base + timedelta(days=offset)
                if candidate.strftime("%A").lower() in days:
                    return candidate.astimezone(timezone.utc)
            return None

        occurrences = _metadata_occurrences(task)
        if not occurrences:
            return None

        if week_pattern == "week_of_month":
            return _find_next_due_for_occurrence_pattern(base_date, days, occurrences, True)
        if week_pattern == "week_of_quarter":
            return _find_next_due_for_occurrence_pattern(base_date, days, occurrences, False)
        return None
    if frequency_type == "day_of_the_month":
        months = _metadata_months(task)
        target_day = task.frequency
        if not months or target_day <= 0 or target_day > 31:
            return None

        search_base = current_due.astimezone(timezone.utc)
        if task.is_rolling:
            search_base = search_base + timedelta(seconds=1)

        base_with_time = _apply_due_time(task, search_base)
        for offset in range(1, 13):
            candidate = _add_months(base_with_time, offset)
            if candidate.strftime("%B").lower() not in months:
                continue

            due_day = min(target_day, _month_last_day(candidate.year, candidate.month))
            return candidate.replace(day=due_day, second=0, microsecond=0)

        return None

    return None


def _generate_occurrences(
    task: DonetickTask,
    members: List[DonetickMember],
    range_start: datetime,
    range_end: datetime,
) -> List[CalendarEvent]:
    """Generate scheduled events for a task within a date range."""
    if task.status in (CHORE_STATUS_IN_PROGRESS, CHORE_STATUS_PAUSED):
        event = _task_to_event(task, members)
        if event is None:
            return []
        return [event] if _event_in_range(event, range_start, range_end) else []

    if task.next_due_date is None:
        return []

    events: List[CalendarEvent] = []
    current_due = task.next_due_date
    current_event = _scheduled_task_event(task, members, current_due)
    if _event_in_range(current_event, range_start, range_end):
        events.append(current_event)

    if task.frequency_type not in RECURRING_FREQUENCY_TYPES:
        return events

    range_end_key = _comparison_datetime(range_end)
    next_due = current_due
    for _ in range(MAX_PROJECTED_OCCURRENCES):
        next_due = _schedule_next_due(task, next_due)
        if next_due is None:
            break

        next_event = _scheduled_task_event(task, members, next_due, next_due.isoformat())
        if _comparison_datetime(next_event.start) > range_end_key:
            break
        if _event_in_range(next_event, range_start, range_end):
            events.append(next_event)

    return events


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
            events.extend(_generate_occurrences(task, self._circle_members, range_start, range_end))

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
