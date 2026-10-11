"""Verify row actions use current assignment and preserve task schedules."""
import ast
from dataclasses import dataclass
from datetime import datetime, timezone
import logging
from pathlib import Path
from types import SimpleNamespace
import unittest
from typing import Any, List, Optional

ROOT = Path(__file__).resolve().parents[1] / 'custom_components/donetick'

class RowActionTests(unittest.IsolatedAsyncioTestCase):
    def test_task_assignee_candidates_are_preserved(self):
        tree = ast.parse((ROOT / 'model.py').read_text(encoding='utf-8'))
        model = next(node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == 'DonetickTask')
        namespace = dict(__name__=__name__, dataclass=dataclass, datetime=datetime,
                         Any=Any, Optional=Optional, List=List, _parse_datetime=lambda value: None)
        exec(compile(ast.Module(body=[model], type_ignores=[]), 'task_model', 'exec'), namespace)
        task = namespace['DonetickTask'].from_json({'id':1, 'name':'Shared', 'assignedTo':1,
                                                  'assignees':[{'userId':1},{'userId':2},{'userId':None},None]})
        self.assertEqual(task.assigned_to, 1)
        self.assertEqual(task.assignee_ids, [1, 2])
        self.assertEqual(namespace['DonetickTask'].from_json({'id':2,'name':'Unassigned'}).assignee_ids, [])

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

    async def test_anyone_task_completion_uses_api_default(self):
        self.task.assigned_to = None
        await self.run_action(True)
        self.assertEqual(self.calls, [('complete', 1, None), ('refresh',)])

    async def test_inactive_tasks_are_rejected(self):
        self.task.is_active = False
        with self.assertRaisesRegex(ValueError, 'no longer active'):
            await self.run_action(True)
        self.assertEqual(self.calls, [('refresh',)])

    async def test_missing_tasks_are_rejected(self):
        self.task.id = 2
        with self.assertRaisesRegex(ValueError, 'no longer active'):
            await self.run_action(True)
        self.assertEqual(self.calls, [('refresh',)])

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

        self.task.assigned_to = None
        result = await namespace['_get_completion_user_id'](owner, SimpleNamespace(async_get_tasks=tasks),
                                                            SimpleNamespace(uid='1--old-date'))
        self.assertIsNone(result)

        for attribute, value in (('is_active', False), ('id', 2)):
            with self.subTest(attribute=attribute):
                original = getattr(self.task, attribute)
                setattr(self.task, attribute, value)
                with self.assertRaisesRegex(ValueError, 'no longer active'):
                    await namespace['_get_completion_user_id'](owner, SimpleNamespace(async_get_tasks=tasks),
                                                               SimpleNamespace(uid='1--old-date'))
                setattr(self.task, attribute, original)
