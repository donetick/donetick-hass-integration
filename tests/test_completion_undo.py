"""complete_task reports the history entry it created, and delete_history removes it."""
import ast
from datetime import datetime, timezone
import logging
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock
from mapping_test_helpers import load_completion_user

ROOT = Path(__file__).resolve().parents[1]
COMPONENT = ROOT / "custom_components" / "donetick"
DOMAIN = "donetick"


class CompletionUndoTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        tree = ast.parse((COMPONENT / "__init__.py").read_text(encoding="utf-8"))
        functions = [node for node in tree.body if isinstance(node, ast.AsyncFunctionDef)
                     and node.name in ("_get_config_entry", "async_complete_task_service",
                                       "async_delete_history_service")]
        constants = {}
        exec((COMPONENT / "const.py").read_text(encoding="utf-8"), constants)
        namespace = {"DOMAIN": DOMAIN, "ConfigEntry": object, "HomeAssistant": object,
                     "ServiceCall": object, "_LOGGER": logging.getLogger(__name__),
                     "HomeAssistantError": RuntimeError,
                     "completion_user": load_completion_user(),
                     "HISTORY_COMPLETED": constants["HISTORY_COMPLETED"],
                     "HISTORY_PENDING_APPROVAL": constants["HISTORY_PENDING_APPROVAL"]}
        exec(compile(ast.Module(body=functions, type_ignores=[]), "undo", "exec"), namespace)
        self.complete = namespace["async_complete_task_service"]
        self.delete_history = namespace["async_delete_history_service"]
        self.client = SimpleNamespace(
            async_complete_task=AsyncMock(return_value=SimpleNamespace(
                next_due_date=datetime(2026, 11, 3, 18, tzinfo=timezone.utc))),
            async_get_task_history_entries=AsyncMock(return_value=[
                SimpleNamespace(id=12, status=constants["HISTORY_COMPLETED"],
                                due_date=datetime(2026, 10, 27, 18, tzinfo=timezone.utc)),
                SimpleNamespace(id=11, status=constants["HISTORY_COMPLETED"],
                                due_date=datetime(2026, 10, 20, 18, tzinfo=timezone.utc)),
            ]),
            async_delete_task_history=AsyncMock(return_value=True),
        )
        self.coordinator = SimpleNamespace(async_request_refresh=AsyncMock())
        entry = self.entry = SimpleNamespace(entry_id="dev", domain=DOMAIN, data={})
        self.hass = SimpleNamespace(
            data={DOMAIN: {"dev": {"client": self.client, "coordinator": self.coordinator}}},
            config_entries=SimpleNamespace(async_get_entry={"dev": entry}.get,
                                           async_entries=lambda domain: [entry]),
        )

    def call(self, data, return_response=True):
        return SimpleNamespace(data=data, return_response=return_response)

    async def test_complete_returns_created_history_entry_and_previous_due_date(self):
        response = await self.complete(self.hass, self.call({"task_id": 7}))
        self.assertEqual(response, {
            "task_id": 7,
            "history_id": 12,
            "due_date": "2026-10-27T18:00:00+00:00",
            "next_due_date": "2026-11-03T18:00:00+00:00",
        })
        self.client.async_get_task_history_entries.assert_awaited_once_with(7)

    async def test_complete_without_response_skips_history_lookup(self):
        self.assertIsNone(await self.complete(self.hass, self.call({"task_id": 7}, False)))
        self.client.async_get_task_history_entries.assert_not_awaited()

    async def test_mapping_and_explicit_performer_preserve_undo_response(self):
        self.entry.data = {"map_completion_user": True, "user_mapping": {"ha-user": 3}}
        for extra, expected in (({}, 3), ({"completed_by": 4}, 4),
                                ({"completed_by_ha_user": "ha-user"}, 3)):
            with self.subTest(explicit=extra):
                call = self.call({"task_id": 7, **extra})
                call.context = SimpleNamespace(user_id="ha-user")
                response = await self.complete(self.hass, call)
                self.client.async_complete_task.assert_awaited_with(7, expected)
                self.assertEqual(response["history_id"], 12)
                self.assertEqual(response["due_date"], "2026-10-27T18:00:00+00:00")

    async def test_required_mapping_refuses_completion_before_writing_history(self):
        self.entry.data = {"map_completion_user": True, "unmapped_user": "require_mapping"}
        with self.assertRaisesRegex(ValueError, "No Donetick user is mapped"):
            await self.complete(self.hass, self.call({"task_id": 7}))
        self.client.async_complete_task.assert_not_awaited()
        self.client.async_get_task_history_entries.assert_not_awaited()

    async def test_complete_failure_is_raised_not_swallowed(self):
        self.client.async_complete_task.side_effect = ValueError("Donetick denied the completion (400)")
        with self.assertRaises(RuntimeError):
            await self.complete(self.hass, self.call({"task_id": 7}))
        self.client.async_complete_task.side_effect = None

    async def test_delete_history_removes_entry_and_refreshes(self):
        await self.delete_history(self.hass, self.call({"task_id": 7, "history_id": 12}, False))
        self.client.async_delete_task_history.assert_awaited_once_with(7, 12)
        self.coordinator.async_request_refresh.assert_awaited()

    async def test_delete_history_failure_is_raised(self):
        self.client.async_delete_task_history.side_effect = ValueError("Donetick denied the history deletion (403)")
        with self.assertRaises(RuntimeError):
            await self.delete_history(self.hass, self.call({"task_id": 7, "history_id": 12}, False))

    def test_services_are_documented(self):
        services = (COMPONENT / "services.yaml").read_text(encoding="utf-8")
        self.assertIn("\ndelete_history:", services)


if __name__ == "__main__":
    unittest.main()
