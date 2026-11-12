"""Patch task properties while retaining unrelated settings."""
from copy import deepcopy
from decimal import Decimal, InvalidOperation

PROPERTY_FIELDS = ("points",)


def validate_points(value):
    """Accept an integer from YAML or the number selector without truncating it."""
    try:
        number = Decimal(str(value))
        if not number.is_finite() or number < 0 or number != number.to_integral_value():
            raise ValueError()
    except (InvalidOperation, ValueError):
        raise ValueError("Points must be a non-negative whole number") from None
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


def apply_task_properties(task, changes):
    """Return an editor payload without changing unrelated task settings."""
    payload = deepcopy(task)
    if "points" in changes:
        points = changes["points"]
        if type(points) is not int or points < 0:
            raise ValueError("Points must be a non-negative whole number")
        payload["points"] = points
    if "reminders" in changes:
        templates = changes["reminders"]
        if not isinstance(templates, list) or len(templates) > 5:
            raise ValueError("Reminders must contain at most five offsets")
        metadata = deepcopy(payload.get("notificationMetadata") or {})
        metadata["templates"] = deepcopy(templates)
        payload["notificationMetadata"] = metadata
        payload["notification"] = bool(templates)
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
