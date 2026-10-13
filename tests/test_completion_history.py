"""Completed occurrences must not mutate or replace recurring pending tasks."""
import importlib.util
import ast
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest import IsolatedAsyncioTestCase
from unittest.mock import AsyncMock
from zoneinfo import ZoneInfo

spec = importlib.util.spec_from_file_location('completion_history', Path(__file__).resolve().parents[1] / 'custom_components/donetick/completion_history.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

class CompletionHistoryTests(IsolatedAsyncioTestCase):
    def setUp(self):
        source = Path(__file__).resolve().parents[1] / 'custom_components/donetick/todo.py'
        tree = ast.parse(source.read_text(encoding='utf-8'))
        base = next(node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == 'DonetickTodoListBase')
        methods = [node for node in base.body if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name in ('_completed_tasks','todo_items','async_update_todo_item','async_delete_todo_items')]
        for method in methods:
            method.decorator_list = []
        local = ZoneInfo('Europe/Brussels')
        namespace = {'datetime':datetime,'TodoItem':lambda **values:SimpleNamespace(**values),'TodoItemStatus':SimpleNamespace(COMPLETED='completed'),
                     'dt_util':SimpleNamespace(now=lambda:datetime(2026,10,13,12,tzinfo=local),as_local=lambda value:value.astimezone(local)),
                     'HomeAssistantError':ValueError,'_LOGGER':SimpleNamespace(debug=lambda *args:None)}
        exec(compile(ast.Module(body=methods,type_ignores=[]),str(source),'exec'),namespace)
        self.methods = namespace

    async def test_native_list_preserves_pending_and_uses_local_day(self):
        records = [dict(uid='history--1',task_id=10,name='Daily task',description='',completed_at='2026-10-12T22:30:00+00:00',completed_by=1,project_id=3),
                   dict(uid='history--2',task_id=10,name='Yesterday',description='',completed_at='2026-10-12T20:30:00+00:00',completed_by=1,project_id=3)]
        task=SimpleNamespace(id=10,name='Daily task',description='',next_due_date=datetime(2026,10,14,tzinfo=timezone.utc),is_active=True)
        entity=SimpleNamespace(coordinator=SimpleNamespace(data=[task],completed_tasks=records),_attr_name='Tasks',_filter_tasks=lambda tasks:tasks,_apply_due_window=lambda tasks:tasks,get_status=lambda *args:'needs_action')
        entity._completed_tasks=lambda:self.methods['_completed_tasks'](entity)
        items=self.methods['todo_items'](entity)
        self.assertEqual([item.status for item in items],['needs_action','completed'])
        self.assertNotEqual(items[0].uid,items[1].uid)
        entity._member=SimpleNamespace(user_id=2)
        self.assertEqual(entity._completed_tasks(),[])
        entity._member.user_id=1
        entity._project=SimpleNamespace(id=4)
        self.assertEqual(entity._completed_tasks(),[])

    async def test_native_history_cannot_change_underlying_task(self):
        with self.assertRaisesRegex(ValueError,'read-only'):
            await self.methods['async_update_todo_item'](None,SimpleNamespace(uid='history--1'))
        with self.assertRaisesRegex(ValueError,'read-only'):
            await self.methods['async_delete_todo_items'](None,['10--date','history--1'])

    async def test_history_keeps_occurrences_and_original_performer(self):
        task = SimpleNamespace(id=10, name='Daily task', description='', project_id=3, assigned_to=2, labels=[])
        def occurrence(i, status=1):
            return SimpleNamespace(id=i, chore_id=10, status=status, performed_at=datetime(2026,10,13,i,tzinfo=timezone.utc), assigned_to=1, completed_by=1, due_date=None)
        client = SimpleNamespace(async_get_task_history=AsyncMock(return_value=[occurrence(1),occurrence(2),occurrence(2),occurrence(3,2),occurrence(4,6),occurrence(5,3)]), async_get_task_detail=AsyncMock())
        records = await module.async_completed_occurrences(client, [task])
        self.assertEqual([r['uid'] for r in records], ['history--2','history--1'])
        self.assertEqual(records[0]['completed_by'], 1)
        self.assertEqual(task.assigned_to, 2)
        client.async_get_task_detail.assert_not_called()

    async def test_archived_and_inaccessible_tasks(self):
        history = [SimpleNamespace(id=1,chore_id=10,status=1,performed_at=datetime.now(timezone.utc),assigned_to=1,completed_by=1,due_date=None)]
        client = SimpleNamespace(async_get_task_history=AsyncMock(return_value=history), async_get_task_detail=AsyncMock(return_value=None))
        self.assertEqual(await module.async_completed_occurrences(client, []), [])
        client.async_get_task_detail.return_value = SimpleNamespace(id=10,name='One-off',description=None,project_id=None,labels=[])
        self.assertEqual((await module.async_completed_occurrences(client, []))[0]['name'], 'One-off')
