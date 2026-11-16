"""The activity calendar serves the newest 90 days of a longer range."""
import sys
import unittest
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from custom_components.donetick.calendar import DonetickActivityCalendar
from custom_components.donetick.model import DonetickChoreHistory


class ActivityCalendarRangeTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.now = datetime.now(UTC)
        self.history = DonetickChoreHistory(
            id=1, chore_id=1, status=1,
            performed_at=self.now - timedelta(days=2),
            completed_by=1, assigned_to=None, due_date=None, duration=60,
        )
        self.calls = []

        async def get_history(days=30, include_members=True):
            self.calls.append((days, include_members))
            return [self.history]

        self.calendar = object.__new__(DonetickActivityCalendar)
        self.calendar._client = SimpleNamespace(async_get_task_history=get_history)
        self.calendar._circle_members = []
        self.calendar.coordinator = SimpleNamespace(
            data=[SimpleNamespace(id=1, name="Chore")])

    async def events(self, start, end):
        return await self.calendar.async_get_events(None, start, end)

    async def test_long_range_returns_the_available_ninety_days(self):
        events = await self.events(self.now - timedelta(days=180),
                                   self.now + timedelta(days=1))
        self.assertEqual(self.calls, [(90, True)])
        self.assertEqual(len(events), 1)

    async def test_short_range_still_asks_for_its_own_span(self):
        events = await self.events(self.now - timedelta(days=30),
                                   self.now + timedelta(days=1))
        self.assertEqual(self.calls, [(31, True)])
        self.assertEqual(len(events), 1)

    async def test_future_range_has_no_activity(self):
        events = await self.events(self.now + timedelta(days=1),
                                   self.now + timedelta(days=2))
        self.assertEqual(events, [])
        self.assertEqual(self.calls, [])


if __name__ == "__main__":
    unittest.main()
