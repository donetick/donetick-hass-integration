"""The activity calendar serves the newest 90 days of a longer range."""
import ast
from datetime import UTC, date, datetime, timedelta, timezone
import logging
from pathlib import Path
from types import SimpleNamespace
from typing import List, Optional
import unittest
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

COMPONENT = Path(__file__).resolve().parents[1] / "custom_components" / "donetick"


def _load_activity_calendar():
    source = COMPONENT / "calendar.py"
    tree = ast.parse(source.read_text(encoding="utf-8"))
    nodes = ast.parse("from __future__ import annotations").body + [
        node
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.Assign))
        or (isinstance(node, ast.ClassDef) and node.name == "DonetickActivityCalendar")
    ]
    ns = {
        "__name__": __name__,
        "logging": logging,
        "date": date,
        "datetime": datetime,
        "timedelta": timedelta,
        "timezone": timezone,
        "List": List,
        "Optional": Optional,
        "ZoneInfo": ZoneInfo,
        "ZoneInfoNotFoundError": ZoneInfoNotFoundError,
        "CalendarEvent": SimpleNamespace,
        "CalendarEntity": type("CalendarEntity", (), {}),
        "CoordinatorEntity": type("CoordinatorEntity", (), {}),
        "DataUpdateCoordinator": object,
        "ConfigEntry": object,
        "HomeAssistant": object,
        "DonetickApiClient": object,
        "DonetickChoreHistory": object,
        "DonetickMember": object,
        "DonetickTask": object,
        "DOMAIN": "donetick",
        "dt_util": SimpleNamespace(
            as_local=lambda value: value if value.tzinfo else value.replace(tzinfo=UTC),
            as_utc=lambda value: value.astimezone(UTC) if value.tzinfo else value.replace(tzinfo=UTC),
            now=lambda: datetime.now(UTC),
        ),
    }
    exec(compile(ast.Module(body=nodes, type_ignores=[]), str(source), "exec"), ns)
    return ns["DonetickActivityCalendar"]


DonetickActivityCalendar = _load_activity_calendar()


class ActivityCalendarRangeTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.now = datetime.now(UTC)
        self.history = SimpleNamespace(
            id=1,
            chore_id=1,
            status=1,
            start_time=None,
            end_time=None,
            performed_at=self.now - timedelta(days=2),
            updated_at=None,
            created_at=None,
            completed_by=1,
            assigned_to=None,
            due_date=None,
            notes=None,
            duration=60,
        )
        self.calls = []

        async def get_history(days=30, include_members=True):
            self.calls.append((days, include_members))
            return [self.history]

        self.calendar = object.__new__(DonetickActivityCalendar)
        self.calendar._client = SimpleNamespace(async_get_task_history=get_history)
        self.calendar._circle_members = []
        self.calendar.coordinator = SimpleNamespace(
            data=[SimpleNamespace(id=1, name="Chore")]
        )

    async def events(self, start, end):
        return await self.calendar.async_get_events(None, start, end)

    async def test_long_range_returns_the_available_ninety_days(self):
        events = await self.events(
            self.now - timedelta(days=180),
            self.now + timedelta(days=1),
        )
        self.assertEqual(self.calls, [(90, True)])
        self.assertEqual(len(events), 1)

    async def test_short_range_still_asks_for_its_own_span(self):
        events = await self.events(
            self.now - timedelta(days=30),
            self.now + timedelta(days=1),
        )
        self.assertEqual(self.calls, [(31, True)])
        self.assertEqual(len(events), 1)

    async def test_future_range_has_no_activity(self):
        events = await self.events(
            self.now + timedelta(days=1),
            self.now + timedelta(days=2),
        )
        self.assertEqual(events, [])
        self.assertEqual(self.calls, [])


if __name__ == "__main__":
    unittest.main()
