"""Build task-editor payloads using Donetick's recurrence model."""
from copy import deepcopy
from datetime import datetime, time, timezone
from zoneinfo import ZoneInfo

RECURRENCE_FIELDS = (
    "frequency_type", "frequency", "interval_unit", "weekdays", "week_pattern",
    "occurrences", "months", "day_of_month", "schedule_time",
    "schedule_from",
)
WEEKDAYS = ("monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday")
MONTHS = ("january", "february", "march", "april", "may", "june", "july", "august",
          "september", "october", "november", "december")
FREQUENCY_TYPES = ("once", "no_repeat", "daily", "weekly", "monthly", "yearly",
                   "adaptive", "interval", "days_of_the_week", "day_of_the_month", "always", "trigger")
CUSTOM_TYPES = ("interval", "days_of_the_week", "day_of_the_month")
NON_REPEATING_TYPES = ("once", "no_repeat", "always", "trigger")


def _choices(values, allowed, label):
    if not isinstance(values, list) or not values or any(value not in allowed for value in values):
        raise ValueError(f"Choose at least one valid {label}")
    return list(dict.fromkeys(values))


def build_recurrence_payload(task, changes, default_timezone="UTC", *, name=None,
                             description=None, due_date=None, force_unarchive=False):
    """Patch a freshly fetched task, preserving unrelated editor settings."""
    if not task.get("updatedAt"):
        raise ValueError("Task has no update timestamp; refresh before changing its recurrence")
    payload = deepcopy(task)
    previous_type = task.get("frequencyType", "once")
    kind = changes.get("frequency_type", previous_type)
    if kind not in FREQUENCY_TYPES:
        raise ValueError("Choose a supported repeat pattern")
    changed_type = kind != previous_type
    metadata = deepcopy(task.get("frequencyMetadata") or {})
    if changed_type:
        metadata = {key: value for key, value in metadata.items() if key in ("time", "timezone")}
        payload["frequency"] = 1
    payload["frequencyType"] = kind
    if name is not None:
        if not name.strip():
            raise ValueError("Task name cannot be empty")
        payload["name"] = name
    if description is not None:
        payload["description"] = description
    if due_date is not None:
        parsed = datetime.fromisoformat(due_date.replace("Z", "+00:00"))
        if len(due_date) == 10:
            # Match Donetick's date-only editor deadline: local end of day.
            parsed = parsed.replace(hour=23, minute=59, second=59,
                                    tzinfo=ZoneInfo(default_timezone))
        elif parsed.tzinfo is None:
            raise ValueError("Due Date must include a timezone, or use YYYY-MM-DD")
        payload["nextDueDate"] = parsed.isoformat()
    if force_unarchive:
        payload["isActive"] = True

    # Reject fields that would silently have no scheduling effect.
    valid_fields = {"frequency_type"}
    if kind not in NON_REPEATING_TYPES:
        valid_fields.add("schedule_from")
    if kind in CUSTOM_TYPES:
        valid_fields.add("schedule_time")
    if kind == "interval":
        valid_fields.update(("frequency", "interval_unit"))
    elif kind == "days_of_the_week":
        valid_fields.update(("weekdays", "week_pattern", "occurrences"))
    elif kind == "day_of_the_month":
        valid_fields.update(("months", "day_of_month"))
    invalid = set(changes) - valid_fields
    if invalid:
        raise ValueError(f"These fields do not apply to {kind}: {', '.join(sorted(invalid))}")
    if kind not in NON_REPEATING_TYPES and not payload.get("nextDueDate"):
        raise ValueError("Set Due Date for the first occurrence when making this a repeating task")

    if "schedule_from" in changes:
        if changes["schedule_from"] not in ("due_date", "completion"):
            raise ValueError("Reschedule from must be due_date or completion")
        payload["isRolling"] = changes["schedule_from"] == "completion"
    elif changed_type and kind in NON_REPEATING_TYPES:
        payload["isRolling"] = False

    if kind == "interval":
        count = changes.get("frequency", payload.get("frequency", 1))
        if type(count) is not int or not 1 <= count <= 1000:
            raise ValueError("Repeat every must be a whole number between 1 and 1000")
        unit = changes.get("interval_unit", metadata.get("unit", "days"))
        if unit not in ("hours", "days", "weeks", "months", "years"):
            raise ValueError("Choose an interval unit: hours, days, weeks, months, or years")
        payload["frequency"] = count
        metadata["unit"] = unit
    elif kind == "days_of_the_week":
        metadata["days"] = _choices(changes.get("weekdays", metadata.get("days")), WEEKDAYS, "weekday")
        pattern = changes.get("week_pattern", metadata.get("weekPattern") or "every_week")
        if pattern not in ("every_week", "week_of_month", "week_of_quarter"):
            raise ValueError("Choose a supported weekday pattern")
        metadata["weekPattern"] = pattern
        if pattern != "every_week":
            occurrences = changes.get("occurrences", metadata.get("occurrences") or metadata.get("weekNumbers"))
            # Existing schedules can contain the legacy fifth weekday. Retain
            # their format and meaning unless occurrences are explicitly edited.
            month_occurrences = (1, 2, 3, 4, -1) if "occurrences" in changes else (1, 2, 3, 4, 5, -1)
            allowed = month_occurrences if pattern == "week_of_month" else (*range(1, 14), -1)
            if isinstance(occurrences, list) and any(type(value) is not int for value in occurrences):
                raise ValueError("Weekday occurrences must be numbers; use -1 for last")
            validated = _choices(occurrences, allowed, "weekday occurrence")
            if "occurrences" in changes:
                metadata["occurrences"] = validated
                metadata.pop("weekNumbers", None)
        else:
            if changes.get("occurrences"):
                raise ValueError("Choose the nth weekday pattern before selecting occurrences")
            metadata.pop("occurrences", None)
            metadata.pop("weekNumbers", None)
    elif kind == "day_of_the_month":
        metadata["months"] = _choices(changes.get("months", metadata.get("months")), MONTHS, "month")
        day = changes.get("day_of_month", payload.get("frequency", 1))
        if type(day) is not int or not 1 <= day <= 31:
            raise ValueError("Day of month must be between 1 and 31")
        payload["frequency"] = day

    if kind in CUSTOM_TYPES and ("schedule_time" in changes or not metadata.get("time")):
        # Use Donetick's UTC fallback; HA does not configure schedule timezones.
        due = datetime.fromisoformat(payload["nextDueDate"].replace("Z", "+00:00")).astimezone(timezone.utc)
        if "schedule_time" in changes:
            clock = time.fromisoformat(changes["schedule_time"])
            if clock.tzinfo is not None:
                raise ValueError("Custom repeat time must be a time without a UTC offset")
        else:
            clock = due.time()
        metadata["time"] = datetime.combine(due.date(), clock, tzinfo=timezone.utc).isoformat()
        metadata.pop("timezone", None)
    if kind == "trigger" and not task.get("thingChore"):
        raise ValueError("Configure a Thing trigger in Donetick before selecting the trigger schedule")
    if changed_type and previous_type == "trigger" and kind != "trigger":
        payload["thingTrigger"] = None
    elif thing := task.get("thingChore"):
        payload["thingTrigger"] = {"thingID": thing["thingId"], "triggerState": thing["triggerState"],
                                   "condition": thing.get("condition", "")}
    if kind in ("trigger", "always"):
        payload["notification"] = False
    payload["frequencyMetadata"] = metadata if kind in CUSTOM_TYPES else (None if changed_type else deepcopy(task.get("frequencyMetadata")))
    payload["labelsV2"] = [{"id": label["id"]} for label in task.get("labelsV2") or []]
    return payload
