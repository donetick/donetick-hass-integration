"""Action descriptions expose stable HA account IDs without losing service metadata."""
import ast
from copy import copy, deepcopy
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock, Mock


class ActionSelectorTests(unittest.IsolatedAsyncioTestCase):
    async def test_account_choices_refresh_and_listeners_are_removed_on_unload(self):
        source = Path(__file__).resolve().parents[1] / 'custom_components/donetick/action_selectors.py'
        tree = ast.parse(source.read_text())
        tree.body = [node for node in tree.body if isinstance(node, ast.AsyncFunctionDef)]
        descriptions = {'donetick': {name: {
            'name': name, 'response': {'optional': True},
            'fields': {'task_id': {'selector': {'number': {}}},
                       'completed_by': {'selector': {'number': {}}},
                       'completed_by_ha_user': {'selector': {'select': {}}}},
        } for name in ('complete_task', 'complete_assigned_task')}}
        original = deepcopy(descriptions)
        updated, listeners, removers = {}, {}, []
        def listen(event, callback):
            listeners[event] = callback
            return lambda: listeners.pop(event)
        namespace = {'DOMAIN': 'donetick', 'deepcopy': deepcopy, 'copy': copy,
            'EVENT_SERVICE_REGISTERED': 'service_registered',
            'EVENT_USER_ADDED': 'user_added', 'EVENT_USER_REMOVED': 'user_removed',
            'EVENT_USER_UPDATED': 'user_updated',
            'async_get_all_descriptions': AsyncMock(return_value=descriptions),
            'async_set_service_schema': lambda hass, domain, name, schema: updated.update({name: schema})}
        exec(compile(tree, str(source), 'exec'), namespace)
        def user(user_id, name, **extra):
            return SimpleNamespace(id=user_id, name=name, is_active=True, system_generated=False, **extra)
        users = [user('a', 'Same'), user('b', 'Same'), user('c', 'Alice')]
        inactive = user('inactive', 'Inactive')
        inactive.is_active = False
        system = user('system', 'System')
        system.system_generated = True
        hass = SimpleNamespace(auth=SimpleNamespace(async_get_users=AsyncMock(
            return_value=[*users, inactive, system])), bus=SimpleNamespace(async_listen=listen, async_fire=Mock()))
        coordinator = SimpleNamespace(data=[], async_add_listener=lambda callback: lambda: None)
        hass.data = {'donetick': {'entry': {'coordinator': coordinator}}}
        hass.config_entries = SimpleNamespace(async_get_entry=lambda entry_id: SimpleNamespace(title='Local'))
        await namespace['async_setup_action_selectors'](hass, SimpleNamespace(entry_id='entry', async_on_unload=removers.append))
        for schema in updated.values():
            choices = schema['fields']['completed_by_ha_user']['selector']['select']
            self.assertEqual(choices['options'], [
                {'value': 'c', 'label': 'Alice'}, {'value': 'a', 'label': 'Same (a)'},
                {'value': 'b', 'label': 'Same (b)'}])
            self.assertNotIn('custom_value', choices)
            self.assertEqual(schema['fields']['task_id'], original['donetick']['complete_task']['fields']['task_id'])
            self.assertEqual(schema['response'], {'optional': True})
        self.assertEqual(descriptions, original)
        users[0].name = 'Renamed'
        hass.auth.async_get_users.return_value = [users[0]]
        await listeners['user_updated'](None)
        self.assertEqual(updated['complete_task']['fields']['completed_by_ha_user']['selector']['select']['options'],
                         [{'value': 'a', 'label': 'Renamed'}])
        for remove in removers:
            remove()
        self.assertEqual(listeners, {})


class PickerResolutionTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        source = Path(__file__).resolve().parents[1] / 'custom_components/donetick/action_selectors.py'
        tree = ast.parse(source.read_text(encoding='utf-8'))
        tree.body = [node for node in tree.body if isinstance(node, ast.AsyncFunctionDef)]
        self.namespace = {'DOMAIN': 'donetick', 'deepcopy': deepcopy, 'copy': copy,
                          'EVENT_SERVICE_REGISTERED': 'service_registered',
                          'HomeAssistantError': ValueError}
        exec(compile(tree, str(source), 'exec'), self.namespace)
        self.prepare = self.namespace['async_prepare_action_call']
        self.members = [SimpleNamespace(user_id=7, username='alice', is_active=True)]
        self.client = SimpleNamespace(async_get_circle_members=AsyncMock(return_value=self.members))
        self.hass = SimpleNamespace(data={'donetick': {'one': {'client': self.client}}})
        self.entry = SimpleNamespace(entry_id='one')
        self.resolve = AsyncMock(return_value=self.entry)

    def call(self, data, service='update_task'):
        return SimpleNamespace(data=data, service=service, context=object(), return_response=True)

    async def test_task_and_username_resolve_to_legacy_ids_without_mutating_original(self):
        original = self.call({'task': 'one/42', 'assigned_to_username': 'one/alice'})
        prepared = await self.prepare(self.hass, original, self.resolve)
        self.assertEqual(prepared.data, {'task_id': 42, 'assigned_to': 7, 'config_entry_id': 'one'})
        self.resolve.assert_awaited_once_with(self.hass, 'one')
        self.assertEqual(original.data, {'task': 'one/42', 'assigned_to_username': 'one/alice'})
        self.assertIs(prepared.context, original.context)
        self.assertTrue(prepared.return_response)

    async def test_numeric_ids_and_anyone_are_preserved(self):
        for fields in ({'assigned_to': None}, {'assigned_to': 7}, {'completed_by': 7}):
            prepared = await self.prepare(self.hass, self.call({'task_id': 42, **fields}), self.resolve)
            self.assertEqual(prepared.data, {'task_id': 42, 'config_entry_id': 'one', **fields})
        self.client.async_get_circle_members.assert_not_awaited()

    async def test_raw_username_and_completion_username_are_supported(self):
        prepared = await self.prepare(self.hass, self.call(
            {'task_id': 42, 'completed_by_username': 'alice'}, 'complete_task'), self.resolve)
        self.assertEqual(prepared.data['completed_by'], 7)

    async def test_readable_search_value_keeps_a_stable_task_reference(self):
        prepared = await self.prepare(self.hass, self.call({
            'task': '#42 · alice · Previous task name · Local (one)',
            'assigned_to_username': 'alice'}), self.resolve)
        self.assertEqual(prepared.data['task_id'], 42)
        self.assertEqual(prepared.data['assigned_to'], 7)

    async def test_ambiguous_or_unloaded_picker_instance_is_rejected(self):
        self.hass.data['donetick']['other-one'] = {}
        for suffix in ('one', 'missing'):
            with self.assertRaisesRegex(ValueError, 'unavailable or ambiguous'):
                await self.prepare(self.hass, self.call({
                    'task': f'#42 · alice · Task · Local ({suffix})',
                    'assigned_to_username': 'alice'}), self.resolve)
        self.client.async_get_circle_members.assert_not_awaited()

    async def test_username_lookup_failure_is_actionable(self):
        self.client.async_get_circle_members.side_effect = OSError('offline')
        with self.assertRaisesRegex(ValueError, 'Unable to load current Donetick users'):
            await self.prepare(self.hass, self.call({
                'task_id': 42, 'assigned_to_username': 'alice'}), self.resolve)

    async def test_conflicting_or_missing_inputs_fail_before_member_lookup(self):
        for fields in ({}, {'task': 'one/42', 'task_id': 42},
                       {'task_id': 42, 'assigned_to': None, 'assigned_to_username': 'alice'},
                       {'task_id': 42, 'completed_by': 7, 'completed_by_username': 'alice'},
                       {'task_id': 42, 'completed_by_ha_user': 'ha', 'completed_by_username': 'alice'}):
            with self.subTest(fields=fields), self.assertRaises(ValueError):
                await self.prepare(self.hass, self.call(fields), self.resolve)
        self.client.async_get_circle_members.assert_not_awaited()

    async def test_cross_integration_selection_is_rejected(self):
        for data in ({'task': 'one/42', 'assigned_to_username': 'other/alice'},
                     {'task': 'other/42', 'config_entry_id': 'one'}):
            with self.assertRaisesRegex(ValueError, 'same Donetick integration|different Donetick integration'):
                await self.prepare(self.hass, self.call(data), self.resolve)
        self.client.async_get_circle_members.assert_not_awaited()

    async def test_invalid_task_selections_are_rejected(self):
        for value in ('42', 'one/zero', 'one/0', 'one/-1'):
            with self.subTest(value=value), self.assertRaises(ValueError):
                await self.prepare(self.hass, self.call({'task': value}), self.resolve)

    async def test_unavailable_inactive_and_ambiguous_usernames_are_rejected(self):
        for members in ([], [SimpleNamespace(user_id=7, username='alice', is_active=False)],
                        [*self.members, *self.members]):
            self.client.async_get_circle_members.return_value = members
            with self.assertRaisesRegex(ValueError, 'unavailable or ambiguous'):
                await self.prepare(self.hass, self.call(
                    {'task': 'one/42', 'assigned_to_username': 'alice'}), self.resolve)

    async def test_task_options_disambiguate_instances_and_hide_archived_tasks(self):
        descriptions = {'donetick': {'update_task': {'fields': {
            'task': {}, 'task_id': {'selector': {'number': {}}}, 'assigned_to_username': {}}}}}
        updates = {}
        self.namespace.update(async_get_all_descriptions=AsyncMock(return_value=descriptions),
                              async_set_service_schema=lambda hass, domain, name, schema: updates.update({name: schema}))
        for entry_id in ('one', 'two'):
            self.hass.data['donetick'][entry_id] = {'circle_members': self.members, 'coordinator': SimpleNamespace(data=[
                SimpleNamespace(id=42, name='Same task', assigned_to=7, project_id=3, is_active=True),
                SimpleNamespace(id=43, name='Archived', is_active=False)])}
        self.hass.auth = SimpleNamespace(async_get_users=AsyncMock(return_value=[]))
        self.hass.config_entries = SimpleNamespace(async_get_entry=lambda entry_id: SimpleNamespace(title='Local'))
        self.hass.bus = SimpleNamespace(async_fire=Mock())
        await self.namespace['async_refresh_action_selectors'](self.hass)
        choices = updates['update_task']['fields']['task']['selector']['select']['options']
        self.assertEqual({choice['value'] for choice in choices}, {
            '#42 · alice · Same task · Project #3 · Local (one)',
            '#42 · alice · Same task · Project #3 · Local (two)'})
        self.assertEqual(len({choice['label'] for choice in choices}), 2)
        self.assertTrue(all('alice' in choice['label'] and 'Project #3' in choice['label'] for choice in choices))
        self.assertTrue(all(choice['label'].startswith('#42 · alice ·') for choice in choices))
        self.assertTrue(updates['update_task']['fields']['task']['selector']['select']['custom_value'])
        self.assertEqual(updates['update_task']['fields']['task_id'], {'selector': {'number': {}}})
