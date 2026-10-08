"""Verify row actions use current assignment and preserve task schedules."""
import ast
from datetime import datetime, timezone
import logging
from pathlib import Path
from types import SimpleNamespace
import unittest

ROOT = Path(__file__).resolve().parents[1] / 'custom_components/donetick'

class RowActionTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        source = ROOT / '__init__.py'
        tree = ast.parse(source.read_text(encoding='utf-8'))
        action = next(n for n in tree.body if isinstance(n, ast.AsyncFunctionDef) and n.name == 'async_task_row_action')

        self.task = SimpleNamespace(id=1, is_active=True, assigned_to=2,
                                    frequency_type="weekly", next_due_date=datetime(2026, 10, 24, 16, tzinfo=timezone.utc))
        self.calls = []
        async def resolve(hass, entry_id):
            return SimpleNamespace(entry_id='entry')
        async def tasks():
            return [self.task]
        async def complete(task_id, completed_by):
            self.calls.append(('complete', task_id, completed_by))
        async def update(task_id, **kwargs):
            self.calls.append(('update', task_id, kwargs))
        async def reschedule(task_id):
            self.calls.append(('reschedule', task_id))
        async def refresh():
            self.calls.append(('refresh',))
        namespace = dict(HomeAssistant=object, ServiceCall=object, HomeAssistantError=ValueError,
                         DOMAIN='donetick', _get_config_entry=resolve)
        exec(compile(ast.Module(body=[action], type_ignores=[]), str(source), 'exec'), namespace)
        self.action = namespace['async_task_row_action']
        self.hass = SimpleNamespace(data={'donetick': {'entry': {
            'client': SimpleNamespace(async_get_tasks=tasks, async_complete_task=complete, async_update_task=update, async_reschedule_task=reschedule),
            'coordinator': SimpleNamespace(async_request_refresh=refresh)}}})

    async def run_action(self, complete):
        await self.action(self.hass, SimpleNamespace(data={'task_id': 1}), complete=complete)

    async def test_completion_uses_current_server_assignee(self):
        await self.run_action(True)
        self.assertEqual(self.calls, [('complete', 1, 2), ('refresh',)])

    async def test_unassigned_and_inactive_tasks_are_rejected(self):
        for attribute in ('assigned_to', 'is_active'):
            with self.subTest(attribute=attribute):
                setattr(self.task, attribute, None if attribute == 'assigned_to' else False)
                with self.assertRaises(ValueError):
                    await self.run_action(True)
                setattr(self.task, attribute, 2 if attribute == 'assigned_to' else True)
        self.assertTrue(all(call[0] == 'refresh' for call in self.calls))

    async def test_postpone_uses_server_scheduler(self):
        await self.run_action(False)
        self.assertEqual(self.calls, [('reschedule', 1), ('refresh',)])
        self.assertEqual(self.task.assigned_to, 2)

    async def test_nonrecurring_task_cannot_be_postponed(self):
        self.task.frequency_type = "once"
        with self.assertRaisesRegex(ValueError, "no next scheduled"):
            await self.run_action(False)
        self.assertEqual(self.calls, [('refresh',)])

    async def test_regular_todo_completion_uses_task_assignee(self):
        tree = ast.parse((ROOT / 'todo.py').read_text(encoding='utf-8'))
        cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == 'DonetickTodoListBase')
        method = next(n for n in cls.body if isinstance(n, ast.AsyncFunctionDef) and n.name == '_get_completion_user_id')
        namespace = {}
        exec(compile(ast.Module(body=[method], type_ignores=[]), 'completion', 'exec'), namespace)
        async def tasks():
            return [self.task]
        # A stale per-user list and a different HA caller cannot override the current assignee.
        owner = SimpleNamespace(_member=SimpleNamespace(user_id=1))
        result = await namespace['_get_completion_user_id'](owner, SimpleNamespace(async_get_tasks=tasks),
                                                            SimpleNamespace(uid='1--old-date'), SimpleNamespace(user_id='caller'))
        self.assertEqual(result, 2)
