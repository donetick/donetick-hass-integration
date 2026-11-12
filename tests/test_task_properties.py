"""Task configuration validates points, retains settings and reports partial creation."""
import ast
from copy import deepcopy
import logging
from pathlib import Path
import runpy
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock

from test_recurrence import task_fixture

COMPONENT = Path(__file__).resolve().parents[1] / 'custom_components/donetick'
PROPERTIES = runpy.run_path(str(COMPONENT / 'task_properties.py'))
apply = PROPERTIES['apply_task_properties']


class PropertyPayloadTests(unittest.TestCase):
    def test_points_and_zero_preserve_unrelated_fields_and_input(self):
        for points in (0, 3):
            task = task_fixture()
            original = deepcopy(task)
            result = apply(task, {'points': points})
            self.assertEqual(result, {**original, 'points': points})
            self.assertEqual(task, original)


    def test_points_keep_existing_notification_settings(self):
        for enabled in (False, True):
            task = task_fixture()
            task['notification'] = enabled
            result = apply(task, {'points': 3})
            self.assertEqual(result['notification'], enabled)
            self.assertEqual(result['notificationMetadata'], task['notificationMetadata'])

    def test_invalid_points_are_rejected(self):
        validate = PROPERTIES['validate_points']
        for points in (-1, 1.5, True, 'NaN', 'three'):
            with self.subTest(points=points), self.assertRaises(ValueError):
                validate(points)
        self.assertEqual(validate('3'), 3)
        self.assertEqual(validate(3.0), 3)


    def test_independent_assignment_preserves_rotation_and_anyone_clears_it(self):
        task = task_fixture()
        result = apply(task, {'assigned_to': 3})
        self.assertEqual(result['assignedTo'], 3)
        self.assertEqual(result['assignees'], [{'userId': 1}, {'userId': 2}, {'userId': 3}])
        self.assertEqual(result['assignStrategy'], 'round_robin')
        anyone = apply(task, {'assigned_to': None})
        self.assertEqual(anyone['assignees'], [])
        self.assertEqual(anyone['assignStrategy'], 'no_assignee')
        self.assertIsNone(anyone['assignedTo'])
        task.update(assignStrategy='no_assignee', assignedTo=None, assignees=[])
        assigned = apply(task, {'assigned_to': 3})
        self.assertEqual(assigned['assignStrategy'], 'keep_last_assigned')
        self.assertEqual(assigned['assignees'], [{'userId': 3}])


class PropertyServiceTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        tree = ast.parse((COMPONENT / '__init__.py').read_text())
        methods = [node for node in tree.body if isinstance(node, ast.AsyncFunctionDef)
                   and node.name in ('async_create_task_service', 'async_update_task_service')]
        namespace = {**PROPERTIES, 'HomeAssistant': object, 'ServiceCall': object,
                     'HomeAssistantError': ValueError, 'ServiceValidationError': ValueError,
                     'normalize_due_date': lambda date: date, 'DOMAIN': 'donetick',
                     'RECURRENCE_FIELDS': ('frequency_type',),
                     '_LOGGER': logging.getLogger(__name__),
                     '_get_config_entry': AsyncMock(return_value=SimpleNamespace(entry_id='test'))}
        exec(compile(ast.Module(body=methods, type_ignores=[]), 'task-properties-service', 'exec'), namespace)
        self.create = namespace['async_create_task_service']
        self.update = namespace['async_update_task_service']
        self.client = SimpleNamespace(
            async_create_task=AsyncMock(return_value=SimpleNamespace(id=17)),
            async_update_task_recurrence=AsyncMock(return_value=SimpleNamespace(is_active=True)),
            async_assign_task=AsyncMock())
        self.refresh = AsyncMock()
        self.hass = SimpleNamespace(config=SimpleNamespace(time_zone='UTC'), data={'donetick': {'test': {
            'client': self.client, 'coordinator': SimpleNamespace(async_request_refresh=self.refresh)}}})

    async def test_creation_keeps_creator_and_assigns_independently(self):
        await self.create(self.hass, SimpleNamespace(data={
            'name': 'Dishwasher', 'created_by': 1, 'assigned_to': 2,
            'due_date': '2026-12-01T12:00:00Z', 'points': 3}))
        self.client.async_create_task.assert_awaited_once_with('Dishwasher', None, '2026-12-01T12:00:00Z', 1)
        self.client.async_update_task_recurrence.assert_awaited_once_with(17, {}, 'UTC', properties={
            'assigned_to': 2, 'points': 3})
        self.refresh.assert_awaited_once()

    async def test_invalid_points_fail_before_creation(self):
        with self.assertRaisesRegex(ValueError, 'Points'):
            await self.create(self.hass, SimpleNamespace(data={'name': 'Dishwasher', 'points': -1}))
        self.client.async_create_task.assert_not_awaited()

    async def test_partial_creation_names_existing_task_and_never_retries(self):
        self.client.async_update_task_recurrence.side_effect = ValueError('Permission denied')
        with self.assertRaisesRegex(ValueError, 'Task 17 was created.*do not retry create_task'):
            await self.create(self.hass, SimpleNamespace(data={'name': 'Dishwasher', 'points': 3}))
        self.client.async_create_task.assert_awaited_once()
        self.refresh.assert_awaited_once()

    async def test_creation_failure_is_reported(self):
        self.client.async_create_task.side_effect = ValueError('Permission denied')
        with self.assertRaisesRegex(ValueError, 'Failed to create Donetick task'):
            await self.create(self.hass, SimpleNamespace(data={'name': 'Dishwasher'}))
        self.client.async_update_task_recurrence.assert_not_awaited()

    async def test_update_applies_properties_and_assignment_with_one_write(self):
        await self.update(self.hass, SimpleNamespace(data={'task_id': 17, 'points': 0,
            'assigned_to': None, 'frequency_type': 'daily'}))
        self.client.async_update_task_recurrence.assert_awaited_once_with(17, {'frequency_type': 'daily'}, 'UTC',
            name=None, description=None, due_date=None, force_unarchive=False,
            properties={'points': 0, 'assigned_to': None})
        self.client.async_assign_task.assert_not_awaited()
        self.refresh.assert_awaited_once()
