"""Patch task rewards and assignment while retaining unrelated settings."""
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


def apply_task_properties(task, changes):
    """Return an editor payload without changing unrelated task settings."""
    payload = deepcopy(task)
    if "points" in changes:
        points = changes["points"]
        if type(points) is not int or points < 0:
            raise ValueError("Points must be a non-negative whole number")
        payload["points"] = points
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
