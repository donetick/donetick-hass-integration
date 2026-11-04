"""Check creating a task from a to-do list without a running HA installation."""
import ast
import logging
from pathlib import Path
from types import SimpleNamespace
import unittest

SOURCE = Path(__file__).resolve().parents[1] / "custom_components/donetick/todo.py"
LOGGER = logging.getLogger(__name__)


class TodoCreateTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        tree = ast.parse(SOURCE.read_text(encoding="utf-8"))
        base = next(node for node in tree.body if isinstance(node, ast.ClassDef)
                    and node.name == "DonetickTodoListBase")
        create = next(node for node in base.body if isinstance(node, ast.AsyncFunctionDef)
                      and node.name == "async_create_todo_item")
        self.calls = []
        calls = self.calls

        class Client:
            def __init__(self, url, token, session):
                pass

            async def async_create_task(self, **kwargs):
                calls.append(kwargs)
                return SimpleNamespace(id=17)

        namespace = {"TodoItem": object, "DonetickApiClient": Client,
                     "async_get_clientsession": lambda hass: None,
                     "CONF_URL": "url", "CONF_TOKEN": "token", "_LOGGER": LOGGER}
        exec(compile(ast.Module(body=[create], type_ignores=[]), str(SOURCE), "exec"), namespace)
        self.create = namespace["async_create_todo_item"]
        self.item = SimpleNamespace(summary="Rubbish out", description="Tonight", due=None)

    def entity(self, **kwargs):
        async def refresh():
            pass
        return SimpleNamespace(hass=None, coordinator=SimpleNamespace(async_refresh=refresh),
                               _config_entry=SimpleNamespace(data={"url": "https://example.invalid",
                                                                   "token": "token"}), **kwargs)

    async def test_the_debug_line_is_written_on_every_kind_of_list(self):
        # No list has both a project and a member, so one of the two is always None.
        lists = {"unified": ({}, "project None by user None"),
                 "project": ({"_project": SimpleNamespace(id=3), "_project_id": 3}, "project 3 by user None"),
                 "member": ({"_member": SimpleNamespace(user_id=4)}, "project None by user 4")}
        for kind, (attributes, expected) in lists.items():
            with self.subTest(kind):
                with self.assertLogs(LOGGER, logging.DEBUG) as logs:
                    await self.create(self.entity(**attributes), self.item)
                self.assertIn(f"DEBUG:{__name__}:Creating task 'Rubbish out' in {expected}", logs.output)
