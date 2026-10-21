"""Regression checks for upstream project lists and the existing due window."""
import ast
from datetime import datetime, timedelta, timezone
import logging
from pathlib import Path
from types import SimpleNamespace
import unittest


class TaskFilteringTests(unittest.TestCase):
    def setUp(self):
        source = Path(__file__).resolve().parents[1] / "custom_components/donetick/todo.py"
        tree = ast.parse(source.read_text(encoding="utf-8"))
        base = next(node for node in tree.body if isinstance(node, ast.ClassDef)
                    and node.name == "DonetickTodoListBase")
        project = next(node for node in tree.body if isinstance(node, ast.ClassDef)
                       and node.name == "DonetickProjectTasksList")
        functions = [next(node for node in base.body if isinstance(node, ast.FunctionDef)
                          and node.name == "_apply_due_window"),
                     next(node for node in project.body if isinstance(node, ast.FunctionDef)
                          and node.name == "_filter_tasks")]
        namespace = {"datetime": datetime, "timedelta": timedelta, "timezone": timezone,
                     "CONF_SHOW_DUE_IN": "show_due_in", "CONF_SHOW_NO_DUE_DATE": "show_no_due_date",
                     "_LOGGER": logging.getLogger(__name__)}
        exec(compile(ast.Module(body=functions, type_ignores=[]), str(source), "exec"), namespace)
        self.window = namespace["_apply_due_window"]
        self.project_filter = namespace["_filter_tasks"]
        now = datetime.now(timezone.utc)
        self.overdue = SimpleNamespace(next_due_date=now - timedelta(days=1))
        self.near = SimpleNamespace(next_due_date=now + timedelta(days=1))
        self.far = SimpleNamespace(next_due_date=now + timedelta(days=30))
        self.undated = SimpleNamespace(next_due_date=None)
        self.tasks = [self.overdue, self.near, self.far, self.undated]

    def filter_window(self, days, show_undated=True):
        entity = SimpleNamespace(_config_entry=SimpleNamespace(data={
            "show_due_in": days, "show_no_due_date": show_undated}))
        return self.window(entity, self.tasks)

    def test_zero_days_retains_all_scheduled_tasks(self):
        self.assertEqual(self.filter_window(0), self.tasks)
        self.assertEqual(self.filter_window(0, False), self.tasks[:3])

    def test_finite_window_respects_undated_option(self):
        self.assertEqual(self.filter_window(7), [self.overdue, self.near, self.undated])
        self.assertEqual(self.filter_window(7, False), [self.overdue, self.near])

    def test_project_list_excludes_other_projects_and_archived_tasks(self):
        matching = SimpleNamespace(is_active=True, project_id=2)
        other = SimpleNamespace(is_active=True, project_id=3)
        archived = SimpleNamespace(is_active=False, project_id=2)
        unassigned = SimpleNamespace(is_active=True, project_id=None)
        self.assertEqual(self.project_filter(SimpleNamespace(_project_id=2),
                         [matching, other, archived, unassigned]), [matching])

    def test_card_task_attributes_expose_labels(self):
        source = Path(__file__).resolve().parents[1] / "custom_components/donetick/todo.py"
        tree = ast.parse(source.read_text(encoding="utf-8"))
        base = next(node for node in tree.body if isinstance(node, ast.ClassDef)
                    and node.name == "DonetickTodoListBase")
        method = next(node for node in base.body if isinstance(node, ast.FunctionDef)
                      and node.name == "extra_state_attributes")
        method.decorator_list = []
        namespace = {"CONF_URL": "url"}
        exec(compile(ast.Module(body=[method], type_ignores=[]), str(source), "exec"), namespace)
        labels = [{"id": 7, "name": "maintenance"}]
        task = SimpleNamespace(id=1, name="HVAC", assigned_to=2, assignee_ids=[2],
                               description=None, priority=1, labels=labels,
                               next_due_date=None, frequency_type="yearly", is_active=True)
        entity = SimpleNamespace(_config_entry=SimpleNamespace(entry_id="entry", data={"url": "http://donetick"}),
                                 coordinator=SimpleNamespace(data=[task]),
                                 _filter_tasks=lambda tasks: tasks, _apply_due_window=lambda tasks: tasks)
        attributes = namespace["extra_state_attributes"](entity)
        self.assertEqual(attributes["tasks"][0]["labels"], labels)
        self.assertEqual(attributes["tasks"][0]["task_id"], 1)
        task.labels = None
        self.assertEqual(namespace["extra_state_attributes"](entity)["tasks"][0]["labels"], [])
        entity._circle_members = [SimpleNamespace(user_id=2,display_name='Member',username='member',is_active=True),
                                  SimpleNamespace(user_id=3,display_name='Inactive',username='inactive',is_active=False)]
        members = namespace["extra_state_attributes"](entity)["circle_members"]
        self.assertEqual([member["is_active"] for member in members], [True,False])

    def test_member_attributes_expose_anyone_tasks_with_same_due_window(self):
        source = Path(__file__).resolve().parents[1] / "custom_components/donetick/todo.py"
        tree = ast.parse(source.read_text(encoding="utf-8"))
        base = next(node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == 'DonetickTodoListBase')
        method = next(node for node in base.body if isinstance(node, ast.FunctionDef) and node.name == 'extra_state_attributes')
        method.decorator_list = []
        namespace = {'CONF_URL': 'url'}
        exec(compile(ast.Module(body=[method], type_ignores=[]), str(source), 'exec'), namespace)
        def task(task_id, assigned_to, due, active=True):
            return SimpleNamespace(id=task_id, assigned_to=assigned_to, next_due_date=due,
                                   is_active=active, name='Task', assignee_ids=[], description='',
                                   priority=1, frequency_type='weekly', labels=[], points=10, frequency=6, interval_type=None)
        tasks = [task(1, 2, self.near.next_due_date), task(2, None, self.near.next_due_date),
                 task(3, None, self.far.next_due_date), task(4, None, self.near.next_due_date, False),
                 task(5, 3, self.near.next_due_date)]
        owner = SimpleNamespace(_member=SimpleNamespace(user_id=2),
                                _config_entry=SimpleNamespace(entry_id='entry', data={'url':'test', 'show_due_in':7}),
                                coordinator=SimpleNamespace(data=tasks),
                                _filter_tasks=lambda items:[task for task in items if task.assigned_to == 2])
        owner._apply_due_window = lambda items:self.window(owner, items)
        attributes = namespace['extra_state_attributes'](owner)
        self.assertEqual([task['task_id'] for task in attributes['tasks']], [1])
        self.assertEqual([task['task_id'] for task in attributes['anyone_tasks']], [2])
        self.assertIsNone(attributes['anyone_tasks'][0]['assigned_to'])
        self.assertEqual(attributes['donetick_user_id'], 2)
        self.assertEqual(attributes['tasks'][0]['points'], 10)
        self.assertEqual(attributes['anyone_tasks'][0]['points'], 10)
    def test_card_task_attributes_expose_labels(self):
        source = Path(__file__).resolve().parents[1] / "custom_components/donetick/todo.py"
        tree = ast.parse(source.read_text(encoding="utf-8"))
        base = next(node for node in tree.body if isinstance(node, ast.ClassDef)
                    and node.name == "DonetickTodoListBase")
        method = next(node for node in base.body if isinstance(node, ast.FunctionDef)
                      and node.name == "extra_state_attributes")
        method.decorator_list = []
        namespace = {"CONF_URL": "url"}
        exec(compile(ast.Module(body=[method], type_ignores=[]), str(source), "exec"), namespace)
        labels = [{"id": 7, "name": "maintenance"}]
        task = SimpleNamespace(id=1, name="HVAC", assigned_to=2, assignee_ids=[2],
                               description=None, priority=1, labels=labels,
                               next_due_date=None, frequency_type="yearly", is_active=True,
                               points=0, frequency=1, interval_type=None)
        entity = SimpleNamespace(_config_entry=SimpleNamespace(entry_id="entry", data={"url": "http://donetick"}),
                                 coordinator=SimpleNamespace(data=[task]),
                                 _filter_tasks=lambda tasks: tasks, _apply_due_window=lambda tasks: tasks)
        attributes = namespace["extra_state_attributes"](entity)
        self.assertEqual(attributes["tasks"][0]["labels"], labels)
        self.assertEqual(attributes["tasks"][0]["task_id"], 1)
        task.labels = None
        self.assertEqual(namespace["extra_state_attributes"](entity)["tasks"][0]["labels"], [])
