"""Tests for translating Home Assistant service data to Donetick."""

import pytest

from custom_components.donetick.chore_payload import build_create_chore_payload


def test_build_create_chore_payload_applies_explicit_safe_defaults() -> None:
    payload = build_create_chore_payload({"name": "Clean kitchen"})

    assert payload == {
        "name": "Clean kitchen",
        "frequencyType": "once",
        "frequency": 1,
        "assignStrategy": "no_assignee",
        "priority": 0,
    }


def test_build_create_chore_payload_translates_extended_service_fields() -> None:
    payload = build_create_chore_payload(
        {
            "name": "Clean kitchen",
            "description": "Including the worktop",
            "next_due_date": "2026-09-07T18:00:00+02:00",
            "frequency_type": "days_of_the_week",
            "frequency": 1,
            "frequency_metadata": {
                "days": ["monday", "thursday"],
                "timezone": "Europe/Berlin",
            },
            "assignee_ids": [2, 3],
            "assigned_to": 2,
            "assign_strategy": "round_robin",
            "priority": 2,
            "is_rolling": True,
            "config_entry_id": "ignored-by-donetick",
        }
    )

    assert payload == {
        "name": "Clean kitchen",
        "description": "Including the worktop",
        "nextDueDate": "2026-09-07T18:00:00+02:00",
        "frequencyType": "days_of_the_week",
        "frequency": 1,
        "frequencyMetadata": {
            "days": ["monday", "thursday"],
            "timezone": "Europe/Berlin",
        },
        "assignees": [{"userId": 2}, {"userId": 3}],
        "assignedTo": 2,
        "assignStrategy": "round_robin",
        "priority": 2,
        "isRolling": True,
    }


def test_build_create_chore_payload_infers_single_assignee_strategy() -> None:
    payload = build_create_chore_payload({"name": "Clean kitchen", "assigned_to": 2})

    assert payload["assignees"] == [{"userId": 2}]
    assert payload["assignedTo"] == 2
    assert payload["assignStrategy"] == "keep_last_assigned"


@pytest.mark.parametrize(
    ("service_data", "message"),
    [
        (
            {
                "name": "Task",
                "assign_strategy": "no_assignee",
                "assignee_ids": [2],
            },
            "no_assignee",
        ),
        (
            {"name": "Task", "assignee_ids": [2], "assigned_to": 3},
            "assigned_to",
        ),
        (
            {"name": "Task", "assign_strategy": "round_robin"},
            "requires assignee_ids",
        ),
        (
            {
                "name": "Task",
                "frequency_type": "interval",
                "frequency_metadata": {},
            },
            "unit",
        ),
        (
            {"name": "Task", "frequency_type": "days_of_the_week"},
            "days",
        ),
        (
            {
                "name": "Task",
                "frequency_type": "day_of_the_month",
                "frequency": 32,
                "frequency_metadata": {"months": ["january"]},
            },
            "between 1 and 31",
        ),
        (
            {"name": "Task", "frequency_type": "sometimes"},
            "frequency_type",
        ),
        (
            {"name": "Task", "assign_strategy": "oldest_first"},
            "assign_strategy",
        ),
    ],
)
def test_build_create_chore_payload_rejects_server_invalid_combinations(
    service_data: dict, message: str
) -> None:
    with pytest.raises(ValueError, match=message):
        build_create_chore_payload(service_data)


def test_build_create_chore_payload_requires_due_date_for_rolling_schedule() -> None:
    with pytest.raises(ValueError, match="is_rolling requires next_due_date"):
        build_create_chore_payload({"name": "Clean kitchen", "is_rolling": True})


@pytest.mark.parametrize(
    "next_due_date",
    ["2026-09-07", "2026-09-07T18:00:00"],
)
def test_build_create_chore_payload_requires_rfc3339_due_date(
    next_due_date: str,
) -> None:
    with pytest.raises(ValueError, match="next_due_date must be RFC3339"):
        build_create_chore_payload(
            {"name": "Clean kitchen", "next_due_date": next_due_date}
        )
