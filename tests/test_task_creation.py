"""Regressions for external API task creation and creator/assignee attribution."""
import ast
from dataclasses import dataclass
from datetime import datetime
import json
import logging
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock
import unittest

from test_task_sensor_attributes import load_definitions
from test_update_permissions import HttpError, Response


COMPONENT = Path(__file__).resolve().parents[1] / "custom_components/donetick"


class TaskCreationTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        namespace = {"dataclass": dataclass, "datetime": datetime,
                     "_LOGGER": logging.getLogger(__name__), "json": json,
                     "aiohttp": SimpleNamespace(ClientError=HttpError), "API_TIMEOUT": 10}
        load_definitions("model.py", {"_parse_datetime", "DonetickTask"}, namespace)
        tree = ast.parse((COMPONENT / "api.py").read_text(encoding="utf-8"))
        client = next(node for node in tree.body if isinstance(node, ast.ClassDef))
        client.body = [node for node in client.body if getattr(node, "name", None)
                       in ("__init__", "_headers", "async_create_task")]
        future = ast.ImportFrom(module="__future__", names=[ast.alias(name="annotations")], level=0)
        module = ast.fix_missing_locations(ast.Module(body=[future, client], type_ignores=[]))
        exec(compile(module, "creation", "exec"), namespace)
        self.requests = []
        self.response = Response({
            "id": 79, "name": "Laundry", "createdBy": 4, "assignedTo": 4,
            "assignees": [{"userId": 4}], "nextDueDate": "2026-10-30T18:00:00Z",
            "description": "Wash towels", "projectId": 3,
        }, status=201)

        def post(url, **kwargs):
            self.requests.append((url, kwargs))
            return self.response

        self.client = namespace["DonetickApiClient"](
            "https://example.invalid/", "test-token", SimpleNamespace(post=post))

    async def test_explicit_creator_uses_external_api_contract(self):
        task = await self.client.async_create_task(
            "Laundry", "Wash towels", "2026-10-30T18:00:00Z", created_by=4, project_id=3)
        url, args = self.requests[0]
        self.assertEqual(url, "https://example.invalid/eapi/v1/chore")
        self.assertEqual(args["json"], {
            "name": "Laundry", "description": "Wash towels", "dueDate": "2026-10-30T18:00:00Z",
            "createdBy": 4, "projectId": 3,
        })
        self.assertEqual(args["headers"]["secretkey"], "test-token")
        self.assertEqual((task.id, task.assigned_to, task.assignee_ids), (79, 4, [4]))
        self.assertEqual(task.next_due_date.isoformat(), "2026-10-30T18:00:00+00:00")
        self.assertEqual((task.description, task.project_id), ("Wash towels", 3))
        self.assertEqual(len(self.requests), 1)

    async def test_omitted_creator_leaves_token_owner_default_to_server(self):
        self.response.body.update(createdBy=1, assignedTo=1, assignees=[{"userId": 1}])
        task = await self.client.async_create_task("Laundry")
        self.assertEqual(self.requests[0][1]["json"], {"name": "Laundry"})
        self.assertEqual(task.assigned_to, 1)

    async def test_server_rejects_invalid_creator_without_retrying_creation(self):
        self.response = Response({"error": "Specified user not found in circle"}, status=400)
        with self.assertRaises(HttpError):
            await self.client.async_create_task("Laundry", created_by=999)
        self.assertEqual(len(self.requests), 1)

    async def test_service_forwards_creator_and_refreshes_lists(self):
        client = SimpleNamespace(async_create_task=AsyncMock(return_value=SimpleNamespace(id=79)))
        coordinator = SimpleNamespace(async_request_refresh=AsyncMock())
        resolve = AsyncMock(return_value=SimpleNamespace(entry_id="test"))
        namespace = {"HomeAssistant": object, "ServiceCall": object, "DOMAIN": "donetick",
                     "_LOGGER": logging.getLogger(__name__), "_get_config_entry": resolve}
        load_definitions("__init__.py", {"async_create_task_service"}, namespace)
        hass = SimpleNamespace(data={"donetick": {"test": {"client": client, "coordinator": coordinator}}})
        await namespace["async_create_task_service"](hass, SimpleNamespace(data={
            "name": "Laundry", "description": "Wash towels", "due_date": "2026-10-30T18:00:00Z",
            "created_by": 4, "config_entry_id": "test",
        }))
        client.async_create_task.assert_awaited_once_with("Laundry", "Wash towels", "2026-10-30T18:00:00Z", 4)
        coordinator.async_request_refresh.assert_awaited_once()
