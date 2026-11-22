"""Calendar regression coverage for local dates and UTC day boundaries (#41)."""
import ast
from datetime import UTC, date, datetime, timedelta, timezone
import logging
from pathlib import Path
from types import SimpleNamespace
import unittest
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


class CalendarDateTests(unittest.TestCase):
    def setUp(self):
        self.local = ZoneInfo("America/New_York")
        source = Path(__file__).resolve().parents[1] / "custom_components/donetick_dev/calendar.py"
        tree = ast.parse(source.read_text(encoding="utf-8"))
        # Follow the existing lightweight tests: execute the actual helpers without
        # requiring an installed Home Assistant server.
        nodes = ast.parse("from __future__ import annotations").body + [
            node for node in tree.body if isinstance(node, (ast.FunctionDef, ast.Assign))
        ]
        self.ns = {
            "datetime": datetime, "date": date, "timedelta": timedelta,
            "timezone": timezone, "ZoneInfo": ZoneInfo,
            "ZoneInfoNotFoundError": ZoneInfoNotFoundError, "logging": logging,
            "__name__": __name__, "CalendarEvent": SimpleNamespace,
            "dt_util": SimpleNamespace(
                as_local=lambda value: self.aware(value).astimezone(self.local),
                as_utc=lambda value: self.aware(value).astimezone(timezone.utc),
                now=lambda: datetime(2026, 4, 28, 22, tzinfo=self.local),
            ),
        }
        exec(compile(ast.Module(body=nodes, type_ignores=[]), str(source), "exec"), self.ns)
        calendar = next(node for node in tree.body if isinstance(node, ast.ClassDef)
                        and node.name == "DonetickCalendar")
        method = next(node for node in calendar.body if isinstance(node, ast.FunctionDef)
                      and node.name == "event")
        method.decorator_list = []
        methods = ast.parse("from __future__ import annotations").body + [method]
        exec(compile(ast.Module(body=methods, type_ignores=[]), str(source), "exec"), self.ns)

    def aware(self, value):
        return value if value.tzinfo is not None else value.replace(tzinfo=self.local)

    def task(self, value, **overrides):
        values = dict(id=1, name="Task", description="", assigned_to=None,
                      next_due_date=datetime.fromisoformat(value.replace("Z", "+00:00")),
                      frequency_metadata={}, status=0, is_active=True,
                      frequency_type="once", frequency=1, is_rolling=False)
        return SimpleNamespace(**(values | overrides))

    def event(self, task):
        return self.ns["_task_to_event"](task, [])

    def test_end_of_day_keeps_local_date_in_both_offset_directions(self):
        cases = [
            ("America/New_York", "2026-04-29T03:59:59Z", date(2026, 4, 28)),
            ("America/New_York", "2026-01-29T04:59:59Z", date(2026, 1, 28)),
            ("Europe/Brussels", "2026-04-28T21:59:59.999Z", date(2026, 4, 28)),
            ("Asia/Tokyo", "2026-04-28T14:59:00Z", date(2026, 4, 28)),
        ]
        for zone, timestamp, expected in cases:
            with self.subTest(zone=zone, timestamp=timestamp):
                self.local = ZoneInfo(zone)
                task = self.task(timestamp)
                event = self.event(task)
                self.assertEqual(event.start, expected)
                self.assertEqual(event.end, expected + timedelta(days=1))
                self.assertEqual(self.ns["_scheduled_task_event"](task, [], task.next_due_date).start,
                                 expected)

    def test_midnight_and_other_explicit_times_preserve_the_instant(self):
        for timestamp in ("2026-04-29T00:00:00Z", "2026-04-29T01:00:00Z",
                          "2026-04-29T04:00:00Z"):
            with self.subTest(timestamp=timestamp):
                task = self.task(timestamp)
                event = self.event(task)
                self.assertIsInstance(event.start, datetime)
                self.assertEqual(event.start, task.next_due_date)
                self.assertEqual(event.end - event.start, timedelta(hours=1))

    def test_explicit_metadata_time_overrides_end_of_day_heuristic(self):
        task = self.task("2026-04-29T03:59:59Z", frequency_metadata={
            "time": "2026-04-28T23:59:59-04:00"})
        self.assertIsInstance(self.event(task).start, datetime)

    def test_daily_occurrences_use_local_dates(self):
        task = self.task("2026-04-29T03:59:59Z", frequency_type="daily")
        events = self.ns["_generate_occurrences"](
            task, [], datetime(2026, 4, 28, tzinfo=self.local),
            datetime(2026, 5, 1, tzinfo=self.local))
        self.assertEqual([event.start for event in events],
                         [date(2026, 4, 28), date(2026, 4, 29), date(2026, 4, 30)])

    def test_overdue_recurring_task_reaches_the_requested_range(self):
        # Every occurrence before the range must still be walked. Stepping only
        # 365 times hid an hourly chore that had been overdue for two weeks.
        task = self.task("2026-10-01T00:00:00Z", frequency_type="interval",
                         frequency=1, frequency_metadata={"unit": "hours"})
        events = self.ns["_generate_occurrences"](
            task, [], datetime(2026, 11, 15, tzinfo=UTC),
            datetime(2026, 11, 15, 3, tzinfo=UTC))
        self.assertEqual([event.start for event in events],
                         [datetime(2026, 11, 15, hour, tzinfo=UTC)
                          for hour in (0, 1, 2)])

    def test_all_day_range_boundaries_follow_local_midnight_and_dst(self):
        for day, next_day, hours in [(date(2026, 3, 8), date(2026, 3, 9), 23),
                                      (date(2026, 11, 1), date(2026, 11, 2), 25)]:
            with self.subTest(day=day):
                event = SimpleNamespace(start=day, end=next_day)
                start = datetime.combine(day, datetime.min.time(), self.local)
                end = datetime.combine(next_day, datetime.min.time(), self.local)
                compare = self.ns["_comparison_datetime"]
                self.assertEqual(compare(next_day) - compare(day), timedelta(hours=hours))
                in_range = self.ns["_event_in_range"]
                self.assertTrue(in_range(event, start, end))
                self.assertTrue(in_range(event, end - timedelta(minutes=30), end))
                self.assertFalse(in_range(event, end, end + timedelta(days=1)))
                self.assertFalse(in_range(event, start - timedelta(days=1), start))

    def test_entity_does_not_select_yesterdays_late_utc_event(self):
        yesterday = self.task("2026-04-28T01:00:00Z")
        today = self.task("2026-04-29T01:00:00Z", id=2)
        entity = SimpleNamespace(coordinator=SimpleNamespace(data=[yesterday, today]),
                                 _circle_members=[])
        self.assertEqual(self.ns["event"](entity).uid, "donetick_2")

    def schedule(self, due, frequency_type, **overrides):
        task = self.task(due, frequency_type=frequency_type, **overrides)
        return self.ns["_schedule_next_due"](task, task.next_due_date)

    def test_monthly_projection_normalizes_the_day_like_donetick(self):
        # Go's AddDate turns January 31 plus one month into March 3.
        self.assertEqual(self.schedule("2026-01-31T09:00:00Z", "monthly"),
                         datetime(2026, 3, 3, 9, tzinfo=timezone.utc))

    def test_yearly_projection_normalizes_a_leap_day(self):
        # Go's AddDate turns February 29 plus one year into March 1.
        self.assertEqual(self.schedule("2024-02-29T09:00:00Z", "yearly"),
                         datetime(2025, 3, 1, 9, tzinfo=timezone.utc))

    def test_interval_months_and_years_use_the_same_normalization(self):
        self.assertEqual(
            self.schedule("2026-01-31T09:00:00Z", "interval", frequency=1,
                          frequency_metadata={"unit": "months"}),
            datetime(2026, 3, 3, 9, tzinfo=timezone.utc),
        )
        self.assertEqual(
            self.schedule("2024-02-29T09:00:00Z", "interval", frequency=1,
                          frequency_metadata={"unit": "years"}),
            datetime(2025, 3, 1, 9, tzinfo=timezone.utc),
        )

    def test_day_of_the_month_still_clamps_the_day(self):
        next_due = self.schedule(
            "2026-01-31T09:00:00Z", "day_of_the_month", frequency=31,
            frequency_metadata={"months": ["february"], "time": "2026-01-31T09:00:00Z"},
        )
        self.assertEqual(next_due, datetime(2026, 2, 28, 9, tzinfo=timezone.utc))

    def test_monthly_occurrences_follow_the_server_sequence(self):
        task = self.task("2026-01-31T09:00:00Z", frequency_type="monthly")
        events = self.ns["_generate_occurrences"](
            task, [], datetime(2026, 1, 1, tzinfo=timezone.utc),
            datetime(2026, 5, 1, tzinfo=timezone.utc))
        self.assertEqual([event.start for event in events], [
            datetime(2026, 1, 31, 9, tzinfo=timezone.utc),
            datetime(2026, 3, 3, 9, tzinfo=timezone.utc),
            datetime(2026, 4, 3, 9, tzinfo=timezone.utc),
        ])


if __name__ == "__main__":
    unittest.main()
