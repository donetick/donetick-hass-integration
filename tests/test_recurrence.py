"""Recurrence edits follow Donetick's editor contract and preserve task settings."""
import ast
from copy import deepcopy
from datetime import datetime
import logging
from pathlib import Path
import runpy
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock

from test_update_permissions import HttpError, Response

COMPONENT = Path(__file__).resolve().parents[1] / 'custom_components/donetick'
RECURRENCE = runpy.run_path(str(COMPONENT / 'recurrence.py'))
build_payload = RECURRENCE['build_recurrence_payload']


def task_fixture():
    return {
        'id': 5, 'name': 'Filter maintenance', 'description': 'Preserve description',
        'frequencyType': 'weekly', 'frequency': 1, 'frequencyMetadata': None,
        'nextDueDate': '2026-11-02T09:00:00+01:00', 'isRolling': False,
        'assignedTo': 1, 'assignees': [{'userId': 1}, {'userId': 2}],
        'assignStrategy': 'round_robin', 'updatedAt': '2026-10-29T12:00:00Z',
        'isActive': True, 'isPrivate': True, 'projectId': 3, 'priority': 2, 'points': 10,
        'requireApproval': True, 'labelsV2': [{'id': 8, 'name': 'Home'}],
        'subTasks': [{'id': 9, 'name': 'Step'}],
        'notification': True, 'notificationMetadata': {'templates': [{'value': 1, 'unit': 'h'}]},
        'completionActions': [{'type': 'test'}],
        'thingChore': {'thingId': 6, 'triggerState': 'on', 'condition': 'eq'},
    }


class RecurrencePayloadTests(unittest.TestCase):
    def setUp(self):
        self.task = task_fixture()

    def build(self, **changes):
        return build_payload(self.task, changes, 'Europe/Brussels')

    def test_interval_preserves_unrelated_task_settings_and_concurrency(self):
        original = deepcopy(self.task)
        result = self.build(frequency_type='interval', frequency=3, interval_unit='weeks',
                            schedule_time='18:30:00', schedule_from='completion')
        self.assertEqual(result['frequency'], 3)
        self.assertEqual(result['frequencyMetadata']['unit'], 'weeks')
        self.assertEqual(result['frequencyMetadata']['time'], '2026-11-02T18:30:00+00:00')
        self.assertNotIn('timezone', result['frequencyMetadata'])
        self.assertTrue(result['isRolling'])
        for key in ('name', 'description', 'assignedTo', 'assignees', 'assignStrategy', 'updatedAt',
                    'isActive', 'isPrivate', 'projectId', 'priority', 'points', 'requireApproval',
                    'subTasks', 'notification', 'notificationMetadata', 'completionActions', 'nextDueDate'):
            self.assertEqual(result[key], original[key], key)
        self.assertEqual(result['labelsV2'], [{'id': 8}])
        self.assertEqual(result['thingTrigger'], {'thingID': 6, 'triggerState': 'on', 'condition': 'eq'})
        self.assertEqual(self.task, original)

    def test_partial_interval_edit_preserves_other_schedule_fields(self):
        self.task.update(frequencyType='interval', frequency=6, frequencyMetadata={
            'unit': 'months', 'time': '2026-11-02T18:00:00+01:00', 'timezone': 'Europe/Brussels'})
        result = self.build(frequency=2)
        self.assertEqual(result['frequency'], 2)
        self.assertEqual(result['frequencyMetadata'], self.task['frequencyMetadata'])

    def test_partial_edits_preserve_legacy_timezone_and_week_numbers(self):
        for zone_data in ({}, {'timezone': ''}):
            self.task.update(frequencyType='interval', frequency=3, frequencyMetadata={
                'unit': 'days', 'time': '2026-11-02T23:30:00Z', **zone_data})
            result = self.build(frequency=4)
            self.assertEqual(result['frequencyMetadata'], self.task['frequencyMetadata'])
        self.task.update(frequencyType='days_of_the_week', frequency=1, frequencyMetadata={
            'days': ['monday'], 'weekPattern': 'week_of_month', 'weekNumbers': [5],
            'time': '2026-11-02T09:00:00Z', 'timezone': 'UTC'})
        result = self.build(schedule_from='completion')
        self.assertEqual(result['frequencyMetadata'], self.task['frequencyMetadata'])

    def test_weekday_edit_preserves_legacy_fifth_occurrence(self):
        self.task.update(frequencyType='days_of_the_week', frequencyMetadata={
            'days': ['monday'], 'weekPattern': 'week_of_month', 'weekNumbers': [5],
            'time': '2026-11-02T09:00:00Z', 'timezone': 'UTC'})
        result = self.build(weekdays=['friday'])
        self.assertEqual(result['frequencyMetadata']['weekNumbers'], [5])
        self.assertNotIn('occurrences', result['frequencyMetadata'])

    def test_weekday_patterns_match_donetick_values(self):
        result = self.build(frequency_type='days_of_the_week', weekdays=['monday', 'friday'],
                            week_pattern='week_of_month', occurrences=[1, -1], schedule_time='09:15')
        self.assertEqual(result['frequencyMetadata']['days'], ['monday', 'friday'])
        self.assertEqual(result['frequencyMetadata']['occurrences'], [1, -1])
        self.task.update(frequencyType='days_of_the_week', frequencyMetadata=result['frequencyMetadata'])
        weekly = self.build(week_pattern='every_week')
        self.assertNotIn('occurrences', weekly['frequencyMetadata'])
        self.assertEqual(weekly['frequencyMetadata']['days'], ['monday', 'friday'])

    def test_selected_months_use_frequency_as_day_of_month(self):
        result = self.build(frequency_type='day_of_the_month', day_of_month=15,
                            months=['january', 'april', 'july', 'october'])
        self.assertEqual(result['frequency'], 15)
        self.assertEqual(result['frequencyMetadata']['months'], ['january', 'april', 'july', 'october'])

    def test_standard_patterns_and_one_time_are_supported(self):
        for kind in ('daily', 'weekly', 'monthly', 'yearly', 'adaptive', 'once', 'no_repeat', 'always'):
            with self.subTest(kind=kind):
                result = self.build(frequency_type=kind)
                self.assertEqual(result['frequencyType'], kind)
                self.assertEqual(result['nextDueDate'], self.task['nextDueDate'])

    def test_missing_or_incompatible_fields_are_rejected(self):
        invalid = (
            {'frequency_type': 'days_of_the_week'},
            {'frequency_type': 'days_of_the_week', 'weekdays': []},
            {'frequency_type': 'days_of_the_week', 'weekdays': ['monday'], 'week_pattern': 'week_of_month'},
            {'frequency_type': 'days_of_the_week', 'weekdays': ['monday'], 'occurrences': [1]},
            {'frequency_type': 'days_of_the_week', 'weekdays': ['monday'], 'week_pattern': 'week_of_month', 'occurrences': [0]},
            {'frequency_type': 'day_of_the_month'},
            {'frequency_type': 'day_of_the_month', 'months': ['january'], 'day_of_month': 32},
            {'frequency_type': 'interval', 'frequency': 0},
            {'frequency_type': 'interval', 'frequency': True},
            {'frequency_type': 'interval', 'interval_unit': 'fortnights'},
            {'frequency_type': 'daily', 'weekdays': ['monday']},
            {'frequency_type': 'once', 'schedule_from': 'completion'},
            {'frequency_type': 'interval', 'schedule_timezone': 'Not/A_Zone'},
        )
        for changes in invalid:
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                build_payload(self.task, changes, 'Europe/Brussels')

    def test_repeating_task_requires_first_due_date(self):
        self.task['nextDueDate'] = None
        with self.assertRaisesRegex(ValueError, 'first occurrence'):
            self.build(frequency_type='daily')
        result = build_payload(self.task, {'frequency_type': 'daily'}, 'Europe/Brussels',
                               due_date='2026-11-03', force_unarchive=True, description='')
        self.assertEqual(result['nextDueDate'], '2026-11-03T23:59:59+01:00')
        self.assertTrue(result['isActive'])
        self.assertEqual(result['description'], '')

    def test_explicit_time_uses_server_default_without_timezone_metadata(self):
        self.task.update(frequencyType='interval', frequencyMetadata={
            'unit': 'days', 'time': '2026-07-01T16:00:00Z', 'timezone': 'Europe/Brussels'})
        result = self.build(schedule_time='18:30')
        self.assertEqual(result['frequencyMetadata']['time'], '2026-11-02T18:30:00+00:00')
        self.assertNotIn('timezone', result['frequencyMetadata'])

    def test_new_schedule_uses_due_in_server_default_timezone(self):
        result = self.build(frequency_type='interval')
        self.assertEqual(result['frequencyMetadata']['time'], '2026-11-02T08:00:00+00:00')
        self.assertNotIn('timezone', result['frequencyMetadata'])

    def test_trigger_conversion_retains_or_removes_association_as_editor_does(self):
        self.task['frequencyType'] = 'trigger'
        self.assertIsNone(self.build(frequency_type='daily')['thingTrigger'])
        self.assertEqual(self.build(frequency_type='trigger')['thingTrigger']['thingID'], 6)
        self.task['thingChore'] = None
        with self.assertRaisesRegex(ValueError, 'Configure a Thing trigger'):
            self.build(frequency_type='trigger')

    def test_edit_requires_concurrency_timestamp(self):
        self.task.pop('updatedAt')
        with self.assertRaisesRegex(ValueError, 'update timestamp'):
            self.build(frequency_type='daily')


class RecurrenceApiTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        source = COMPONENT / 'api.py'
        tree = ast.parse(source.read_text())
        client = next(node for node in tree.body if isinstance(node, ast.ClassDef))
        client.body = [node for node in client.body if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
                       and node.name in ('__init__', '_headers', '_raise_for_status', '_async_get_editor_task', 'async_update_task_recurrence')]
        future = ast.ImportFrom(module='__future__', names=[ast.alias(name='annotations')], level=0)
        namespace = {'build_recurrence_payload': build_payload, 'datetime': datetime, 'API_TIMEOUT': 10,
                     'aiohttp': SimpleNamespace(ClientError=HttpError), '_LOGGER': logging.getLogger(__name__)}
        def parse(data):
            return SimpleNamespace(frequency_type=data['frequencyType'], frequency=data['frequency'] or 1,
                is_rolling=data['isRolling'], frequency_metadata=data['frequencyMetadata'],
                is_active=data['isActive'], next_due_date=datetime.fromisoformat(data['nextDueDate']))
        namespace['DonetickTask'] = SimpleNamespace(from_json=parse)
        exec(compile(ast.fix_missing_locations(ast.Module(body=[future, client], type_ignores=[])), str(source), 'exec'), namespace)
        self.task = task_fixture()
        self.requests = []
        self.response = Response({}, status=200)
        self.ignore_update = False
        def get(url, **kwargs):
            self.requests.append(('get', url))
            data = deepcopy(self.task if self.ignore_update or not hasattr(self, 'payload') else self.payload)
            if data['frequencyMetadata'] is not None:
                data['frequencyMetadata'].setdefault('weekPattern', None)
            return Response({'res': data}, status=200)
        def put(url, **kwargs):
            self.requests.append(('put', url, kwargs['json']))
            self.payload = kwargs['json']
            return self.response
        self.client = namespace['DonetickApiClient']('http://example.invalid', 'test', SimpleNamespace(get=get, put=put))

    async def test_editor_api_round_trip_includes_concurrency_and_preserves_response_defaults(self):
        result = await self.client.async_update_task_recurrence(5,
            {'frequency_type': 'interval', 'frequency': 3, 'interval_unit': 'days'}, 'Europe/Brussels')
        self.assertEqual(result.frequency_type, 'interval')
        self.assertEqual([request[1] for request in self.requests],
                         ['http://example.invalid/api/v1/chores/5', 'http://example.invalid/api/v1/chores/',
                          'http://example.invalid/api/v1/chores/5'])
        self.assertEqual(self.payload['updatedAt'], self.task['updatedAt'])

    async def test_invalid_schedule_never_writes(self):
        with self.assertRaises(ValueError):
            await self.client.async_update_task_recurrence(5, {'frequency_type': 'days_of_the_week'}, 'UTC')
        self.assertEqual(len(self.requests), 1)

    async def test_legacy_zero_frequency_does_not_cause_a_false_verification_error(self):
        self.task.update(frequencyType='once', frequency=0)
        result = await self.client.async_update_task_recurrence(5, {'frequency_type': 'once'}, 'UTC')
        self.assertEqual(result.frequency_type, 'once')
        self.assertEqual(self.payload['frequency'], 0)

    async def test_stale_edit_is_reported_without_retry(self):
        self.response = Response({'error': 'You cannot edit this chore: chore has been modified by another user, please refresh and try again'})
        with self.assertRaisesRegex(ValueError, 'modified by another user'):
            await self.client.async_update_task_recurrence(5, {'frequency_type': 'daily'}, 'UTC')
        self.assertEqual(len(self.requests), 2)

    async def test_ignored_schedule_changes_are_reported(self):
        self.ignore_update = True
        with self.assertRaisesRegex(ValueError, 'did not apply'):
            await self.client.async_update_task_recurrence(5, {'frequency_type': 'daily'}, 'UTC')


class RecurrenceServiceTests(unittest.IsolatedAsyncioTestCase):
    async def test_service_routes_schedule_and_other_edits_to_editor_and_keeps_assignment(self):
        tree = ast.parse((COMPONENT / '__init__.py').read_text())
        handler = next(node for node in tree.body if isinstance(node, ast.AsyncFunctionDef)
                       and node.name == 'async_update_task_service')
        namespace = {'HomeAssistant': object, 'ServiceCall': object, 'DOMAIN': 'donetick',
                     'HomeAssistantError': ValueError, 'RECURRENCE_FIELDS': RECURRENCE['RECURRENCE_FIELDS'],
                     '_get_config_entry': AsyncMock(return_value=SimpleNamespace(entry_id='test')),
                     '_LOGGER': logging.getLogger(__name__)}
        exec(compile(ast.Module(body=[handler], type_ignores=[]), 'recurrence-service', 'exec'), namespace)
        client = SimpleNamespace(async_update_task_recurrence=AsyncMock(return_value=SimpleNamespace(is_active=True)),
                                 async_update_task=AsyncMock(), async_assign_task=AsyncMock())
        refresh = AsyncMock()
        hass = SimpleNamespace(config=SimpleNamespace(time_zone='Europe/Brussels'),
            data={'donetick': {'test': {'client': client, 'coordinator': SimpleNamespace(async_request_refresh=refresh)}}})
        await namespace['async_update_task_service'](hass, SimpleNamespace(data={
            'task_id': 5, 'frequency_type': 'interval', 'frequency': 3, 'interval_unit': 'days',
            'description': '', 'force_unarchive': True, 'assigned_to': 2}))
        client.async_update_task_recurrence.assert_awaited_once_with(5,
            {'frequency_type': 'interval', 'frequency': 3, 'interval_unit': 'days'}, 'Europe/Brussels',
            name=None, description='', due_date=None, force_unarchive=True)
        client.async_update_task.assert_not_awaited()
        client.async_assign_task.assert_awaited_once_with(5, 2)
        refresh.assert_awaited_once()
