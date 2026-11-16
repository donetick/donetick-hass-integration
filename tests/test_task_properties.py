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
RECURRENCE = runpy.run_path(str(COMPONENT / 'recurrence.py'))
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


    def test_priority_levels_preserve_unrelated_fields_and_input(self):
        for priority in (0, 1, 4):
            task = task_fixture()
            original = deepcopy(task)
            result = apply(task, {'priority': priority})
            self.assertEqual(result, {**original, 'priority': priority})
            self.assertEqual(task, original)

    def test_priority_outside_donetick_levels_is_rejected(self):
        validate = PROPERTIES['validate_priority']
        for priority in (-1, 5, 1.5, True, 'NaN', 'urgent'):
            with self.subTest(priority=priority), self.assertRaises(ValueError):
                validate(priority)
        # The service selector sends the level as a string.
        self.assertEqual(validate('3'), 3)
        self.assertEqual(validate(0), 0)
        self.assertEqual(validate(4.0), 4)
        for priority in (5, True, '2'):
            with self.subTest(priority=priority), self.assertRaisesRegex(ValueError, 'Priority'):
                apply(task_fixture(), {'priority': priority})

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



class CreationSchemaTests(unittest.TestCase):
    """voluptuous is not installed here, so the schemas are checked structurally."""

    def setUp(self):
        tree = ast.parse((COMPONENT / '__init__.py').read_text())
        self.schemas = {node.targets[0].id: node.value for node in tree.body
                        if isinstance(node, ast.Assign) and isinstance(node.targets[0], ast.Name)}

    def spreads(self, name):
        fields = self.schemas[name].args[0]
        return {value.id for key, value in zip(fields.keys, fields.values) if key is None}

    def test_create_and_update_accept_the_same_repeat_fields_and_properties(self):
        for name in ('CREATE_TASK_SCHEMA', 'UPDATE_TASK_SCHEMA'):
            with self.subTest(schema=name):
                self.assertLessEqual({'RECURRENCE_SCHEMA', 'TASK_PROPERTY_SCHEMA'}, self.spreads(name))
        keys = {key.args[0].value for key in self.schemas['RECURRENCE_SCHEMA'].keys}
        self.assertEqual(keys, set(RECURRENCE['RECURRENCE_FIELDS']))

    def test_priority_is_validated_like_points(self):
        properties = self.schemas['TASK_PROPERTY_SCHEMA']
        validators = {key.args[0].value: value.id for key, value in zip(properties.keys, properties.values)}
        self.assertEqual(validators, {'points': 'validate_points', 'priority': 'validate_priority'})
        self.assertEqual(PROPERTIES['PROPERTY_FIELDS'], ('points', 'priority'))

    def test_services_document_repeat_schedule_and_priority_for_creation(self):
        blocks, service = {}, None
        for line in (COMPONENT / 'services.yaml').read_text(encoding='utf-8').splitlines():
            if line[:1].isalpha() and line.rstrip().endswith(':'):
                service = line.rstrip()[:-1]
                blocks[service] = []
            elif service:
                blocks[service].append(line.strip())
        create, update = blocks['create_task'], blocks['update_task']
        self.assertIn('fields: &repeat_schedule_fields', create)
        self.assertIn('fields: *repeat_schedule_fields', update)
        for field in RECURRENCE['RECURRENCE_FIELDS']:
            self.assertIn(f'{field}:', create)
        self.assertIn('priority:', create)
        self.assertIn('priority:', update)

class PropertyServiceTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        tree = ast.parse((COMPONENT / '__init__.py').read_text())
        methods = [node for node in tree.body if isinstance(node, ast.AsyncFunctionDef)
                   and node.name in ('async_create_task_service', 'async_update_task_service')]
        namespace = {**PROPERTIES, 'HomeAssistant': object, 'ServiceCall': object,
                     'HomeAssistantError': ValueError, 'ServiceValidationError': ValueError,
                     'normalize_due_date': lambda date: date, 'DOMAIN': 'donetick',
                     'RECURRENCE_FIELDS': RECURRENCE['RECURRENCE_FIELDS'],
                     'build_recurrence_payload': RECURRENCE['build_recurrence_payload'],
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

    async def test_creation_saves_repeat_schedule_and_priority_with_one_editor_write(self):
        await self.create(self.hass, SimpleNamespace(data={
            'name': 'Water the plants', 'due_date': '2026-11-15T23:59:59+01:00',
            'frequency_type': 'weekly', 'schedule_from': 'completion', 'priority': 3}))
        self.client.async_create_task.assert_awaited_once_with(
            'Water the plants', None, '2026-11-15T23:59:59+01:00', None)
        self.client.async_update_task_recurrence.assert_awaited_once_with(
            17, {'frequency_type': 'weekly', 'schedule_from': 'completion'}, 'UTC',
            properties={'priority': 3})
        self.refresh.assert_awaited_once()

    async def test_creation_with_only_a_repeat_schedule_sets_it_after_creation(self):
        await self.create(self.hass, SimpleNamespace(data={
            'name': 'Filter', 'due_date': '2026-11-15T09:00:00Z', 'frequency_type': 'interval',
            'frequency': 3, 'interval_unit': 'weeks'}))
        self.client.async_update_task_recurrence.assert_awaited_once_with(
            17, {'frequency_type': 'interval', 'frequency': 3, 'interval_unit': 'weeks'}, 'UTC',
            properties={})

    async def test_creation_without_extras_makes_no_editor_write(self):
        await self.create(self.hass, SimpleNamespace(data={'name': 'Milk'}))
        self.client.async_create_task.assert_awaited_once()
        self.client.async_update_task_recurrence.assert_not_awaited()

    async def test_repeating_task_without_due_date_fails_before_creation(self):
        with self.assertRaisesRegex(ValueError, 'Due Date for the first occurrence'):
            await self.create(self.hass, SimpleNamespace(data={'name': 'Filter', 'frequency_type': 'weekly'}))
        self.client.async_create_task.assert_not_awaited()

    async def test_inapplicable_repeat_field_fails_before_creation(self):
        with self.assertRaisesRegex(ValueError, 'do not apply to daily: weekdays'):
            await self.create(self.hass, SimpleNamespace(data={
                'name': 'Filter', 'due_date': '2026-11-15T09:00:00Z',
                'frequency_type': 'daily', 'weekdays': ['monday']}))
        self.client.async_create_task.assert_not_awaited()

    async def test_invalid_custom_schedule_fails_before_creation(self):
        with self.assertRaisesRegex(ValueError, 'weekday'):
            await self.create(self.hass, SimpleNamespace(data={
                'name': 'Filter', 'due_date': '2026-11-15T09:00:00Z', 'frequency_type': 'days_of_the_week'}))
        self.client.async_create_task.assert_not_awaited()

    async def test_invalid_priority_fails_before_creation(self):
        with self.assertRaisesRegex(ValueError, 'Priority'):
            await self.create(self.hass, SimpleNamespace(data={'name': 'Dishwasher', 'priority': 5}))
        self.client.async_create_task.assert_not_awaited()

    async def test_partial_creation_of_a_repeating_task_names_the_task(self):
        self.client.async_update_task_recurrence.side_effect = ValueError('Permission denied')
        with self.assertRaisesRegex(ValueError, 'Task 17 was created.*do not retry create_task'):
            await self.create(self.hass, SimpleNamespace(data={
                'name': 'Filter', 'due_date': '2026-11-15T09:00:00Z', 'frequency_type': 'daily'}))
        self.client.async_create_task.assert_awaited_once()
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

    async def test_update_changes_priority_through_the_editor(self):
        await self.update(self.hass, SimpleNamespace(data={'task_id': 17, 'priority': 0}))
        self.client.async_update_task_recurrence.assert_awaited_once_with(17, {}, 'UTC',
            name=None, description=None, due_date=None, force_unarchive=False,
            properties={'priority': 0})
        self.refresh.assert_awaited_once()
