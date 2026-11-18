"""Patch task properties while retaining unrelated settings."""
from copy import deepcopy
from decimal import Decimal, InvalidOperation

PROPERTY_FIELDS = ("points", "priority")
DEFAULT_OVERDUE_NAGGING_MINUTES = 60
MAX_OVERDUE_NAGGING_MINUTES = 7 * 24 * 60
DEFAULT_OVERDUE_FOLLOW_UP_LIMIT = 3
MAX_OVERDUE_FOLLOW_UP_LIMIT = 100


def validate_points(value):
    """Accept an integer from YAML or the number selector without truncating it."""
    try:
        number = Decimal(str(value))
        if not number.is_finite() or number < 0 or number != number.to_integral_value():
            raise ValueError()
    except (InvalidOperation, ValueError):
        raise ValueError("Points must be a non-negative whole number") from None
    return int(number)


def validate_priority(value):
    """Accept Donetick's priority levels: 0 for none, 1 (urgent) to 4 (low)."""
    try:
        number = Decimal(str(value))
        if not number.is_finite() or number != number.to_integral_value() or not 0 <= number <= 4:
            raise ValueError()
    except (InvalidOperation, ValueError):
        raise ValueError("Priority must be a whole number from 0 (none) to 4 (low)") from None
    return int(number)


def validate_reminders(value):
    """Convert repeatable action rows to Donetick notification templates."""
    if not isinstance(value, list) or len(value) > 5:
        raise ValueError("Reminders must be a list of at most five options")
    templates = []
    for reminder in value:
        if not isinstance(reminder, dict):
            raise ValueError("Each reminder needs a when, amount, and unit")
        when = str(reminder.get("when", "")).strip().lower()
        amount = reminder.get("amount")
        unit = str(reminder.get("unit", "")).strip().lower()
        when = {"before due date": "before", "on due date": "due", "after due date": "after"}.get(when, when)
        unit = {"minutes": "m", "hours": "h", "days": "d"}.get(unit, unit)
        if when not in ("before", "due", "after"):
            raise ValueError("Reminder when must be before, due, or after")
        if when == "due":
            templates.append({"value": 0, "unit": "m"})
            continue
        if type(amount) is not int or amount < 1 or amount > 10000:
            raise ValueError("Before and after reminder amounts must be whole numbers from 1 to 10000")
        if unit not in ("m", "h", "d"):
            raise ValueError("Before and after reminders need a unit of minutes, hours, or days")
        templates.append({"value": -amount if when == "before" else amount, "unit": unit})
    return templates


def validate_overdue_nagging_interval(value):
    """Accept a whole number of minutes from YAML or the number selector."""
    try:
        number = Decimal(str(value))
        if not number.is_finite() or number != number.to_integral_value() or not 1 <= number <= MAX_OVERDUE_NAGGING_MINUTES:
            raise ValueError()
    except (InvalidOperation, ValueError):
        raise ValueError(
            f"Overdue follow-up interval must be a whole number from 1 to {MAX_OVERDUE_NAGGING_MINUTES} minutes"
        ) from None
    return int(number)


def validate_overdue_follow_up_limit(value):
    """Accept the maximum count per task occurrence."""
    try:
        count = validate_points(value)
    except ValueError:
        count = 0
    if not 1 <= count <= MAX_OVERDUE_FOLLOW_UP_LIMIT:
        raise ValueError(f"Maximum overdue follow-ups must be a whole number from 1 to {MAX_OVERDUE_FOLLOW_UP_LIMIT}")
    return count


def apply_task_properties(task, changes):
    """Return an editor payload without changing unrelated task settings."""
    payload = deepcopy(task)
    if "points" in changes:
        points = changes["points"]
        if type(points) is not int or points < 0:
            raise ValueError("Points must be a non-negative whole number")
        payload["points"] = points
    if "priority" in changes:
        priority = changes["priority"]
        if type(priority) is not int or not 0 <= priority <= 4:
            raise ValueError("Priority must be a whole number from 0 (none) to 4 (low)")
        payload["priority"] = priority
    if "reminders" in changes:
        templates = changes["reminders"]
        if not isinstance(templates, list) or len(templates) > 5:
            raise ValueError("Reminders must contain at most five offsets")
        if templates and (not payload.get("nextDueDate") or payload.get("frequencyType") in ("always", "trigger")):
            raise ValueError("Reminders require a scheduled due date; always-available and trigger-based tasks cannot have reminders")
        metadata = deepcopy(payload.get("notificationMetadata") or {})
        metadata["templates"] = deepcopy(templates)
        payload["notificationMetadata"] = metadata
        payload["notification"] = bool(templates)
    if any(field.startswith("overdue_") for field in changes):
        metadata = deepcopy(payload.get("notificationMetadata") or {})
        if changes.get("overdue_follow_ups", changes.get("overdue_nagging")) is False:
            metadata["overdueNagging"] = None
        else:
            if not payload.get("nextDueDate") or payload.get("frequencyType") in ("always", "trigger"):
                raise ValueError("Overdue follow-ups require a scheduled due date")
            current = metadata.get("overdueNagging") or {}
            minutes = changes.get(
                "overdue_follow_up_interval_minutes",
                changes.get("overdue_nagging_interval_minutes", current.get("intervalMinutes", DEFAULT_OVERDUE_NAGGING_MINUTES)),
            )
            limit = changes.get("overdue_follow_up_limit", current.get("maxFollowUps", DEFAULT_OVERDUE_FOLLOW_UP_LIMIT))
            continue_until_complete = changes.get("overdue_follow_up_until_complete", current.get("continueUntilComplete", False))
            metadata["overdueNagging"] = {
                "intervalMinutes": validate_overdue_nagging_interval(minutes),
                "maxFollowUps": validate_overdue_follow_up_limit(limit),
                "continueUntilComplete": continue_until_complete,
            }
        payload["notificationMetadata"] = metadata
    if "assigned_to" in changes:
        assignee = changes["assigned_to"]
        if assignee is not None and (type(assignee) is not int or assignee < 1):
            raise ValueError("Assignee must be a positive user ID or null for Anyone")
        payload["assignedTo"] = assignee
        members = payload.get("assignees") or []
        if assignee is None:
            payload.update(assignStrategy="no_assignee", assignees=[])
        elif payload.get("assignStrategy") == "no_assignee" or len(members) <= 1:
            payload["assignees"] = [{"userId": assignee}]
            if payload.get("assignStrategy") == "no_assignee":
                payload["assignStrategy"] = "keep_last_assigned"
        elif not any(member.get("userId") == assignee for member in members):
            payload["assignees"].append({"userId": assignee})
    return payload
