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
