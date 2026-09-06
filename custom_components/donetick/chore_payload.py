"""Translate Home Assistant service data to Donetick chore requests."""

import re
from collections.abc import Mapping
from datetime import datetime
from typing import Any

_RFC3339_PATTERN = re.compile(
    r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})$"
)

FREQUENCY_TYPES = frozenset(
    {
        "once",
        "daily",
        "weekly",
        "monthly",
        "yearly",
        "adaptive",
        "interval",
        "days_of_the_week",
        "day_of_the_month",
        "trigger",
        "no_repeat",
    }
)

ASSIGNMENT_STRATEGIES = frozenset(
    {
        "no_assignee",
        "least_assigned",
        "least_completed",
        "random",
        "keep_last_assigned",
        "random_except_last_assigned",
        "round_robin",
    }
)

STRATEGIES_REQUIRING_ASSIGNEES = frozenset(
    {
        "least_assigned",
        "least_completed",
        "random",
        "random_except_last_assigned",
        "round_robin",
    }
)


def _validate_frequency(data: Mapping[str, Any]) -> None:
    frequency_type = data.get("frequency_type", "once")
    if frequency_type not in FREQUENCY_TYPES:
        raise ValueError(f"Unsupported frequency_type: {frequency_type}")

    metadata = data.get("frequency_metadata") or {}
    if frequency_type == "interval" and not metadata.get("unit"):
        raise ValueError("frequency_metadata.unit is required for interval")
    if frequency_type == "days_of_the_week" and not metadata.get("days"):
        raise ValueError("frequency_metadata.days is required for days_of_the_week")
    if frequency_type == "day_of_the_month":
        if not metadata.get("months"):
            raise ValueError(
                "frequency_metadata.months is required for day_of_the_month"
            )
        frequency = data.get("frequency", 1)
        if not 1 <= frequency <= 31:
            raise ValueError("frequency must be between 1 and 31")


def _validate_due_date(data: Mapping[str, Any]) -> None:
    next_due_date = data.get("next_due_date")
    if data.get("is_rolling") and not next_due_date:
        raise ValueError("is_rolling requires next_due_date")
    if next_due_date is None:
        return
    if not isinstance(next_due_date, str) or not _RFC3339_PATTERN.fullmatch(
        next_due_date
    ):
        raise ValueError("next_due_date must be RFC3339 with a timezone")
    try:
        datetime.fromisoformat(next_due_date)
    except ValueError as err:
        raise ValueError("next_due_date must be RFC3339 with a timezone") from err


def _validate_assignment(
    assign_strategy: str, assignee_ids: list[int], assigned_to: int | None
) -> None:
    if assign_strategy not in ASSIGNMENT_STRATEGIES:
        raise ValueError(f"Unsupported assign_strategy: {assign_strategy}")
    if assign_strategy == "no_assignee" and (assignee_ids or assigned_to is not None):
        raise ValueError("no_assignee forbids assignee_ids and assigned_to")
    if assign_strategy in STRATEGIES_REQUIRING_ASSIGNEES and not assignee_ids:
        raise ValueError(f"{assign_strategy} requires assignee_ids")
    if assigned_to is not None and assigned_to not in assignee_ids:
        raise ValueError("assigned_to must be included in assignee_ids")


def build_create_chore_payload(data: Mapping[str, Any]) -> dict[str, Any]:
    """Build a Donetick full-API create payload from service data."""
    assigned_to = data.get("assigned_to")
    assignee_ids = list(data.get("assignee_ids", []))
    # Treat assigned_to on its own as a one-person assignment before validation.
    if assigned_to is not None and "assignee_ids" not in data:
        assignee_ids = [assigned_to]

    assign_strategy = data.get("assign_strategy")
    if assign_strategy is None:
        assign_strategy = "keep_last_assigned" if assignee_ids else "no_assignee"

    _validate_frequency(data)
    _validate_due_date(data)
    _validate_assignment(assign_strategy, assignee_ids, assigned_to)

    payload = {
        "name": data["name"],
        "frequencyType": data.get("frequency_type", "once"),
        "frequency": data.get("frequency", 1),
        "assignStrategy": assign_strategy,
        "priority": data.get("priority", 0),
    }

    field_names = {
        "description": "description",
        "next_due_date": "nextDueDate",
        "frequency_metadata": "frequencyMetadata",
        "assigned_to": "assignedTo",
        "is_rolling": "isRolling",
    }
    for service_name, api_name in field_names.items():
        if service_name in data:
            payload[api_name] = data[service_name]

    if assignee_ids:
        payload["assignees"] = [{"userId": user_id} for user_id in assignee_ids]

    return payload
