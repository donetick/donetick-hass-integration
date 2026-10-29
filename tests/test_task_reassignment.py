"""Check Anyone reassignment preserves task settings and server errors."""
import ast
from copy import deepcopy
from datetime import datetime, timezone
import logging
from pathlib import Path
from types import SimpleNamespace
import unittest

from test_update_permissions import Response, HttpError


class TaskReassignmentTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        source = Path(__file__).resolve().parents[1] / "custom_components/donetick/api.py"
        tree = ast.parse(source.read_text(encoding="utf-8"))
        client = next(node for node in tree.body if isinstance(node, ast.ClassDef))
        client.body = [node for node in client.body if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
                       and node.name in ("__init__", "_headers", "_raise_for_status", "async_assign_task")]
        future = ast.ImportFrom(module="__future__", names=[ast.alias(name="annotations")], level=0)
        module = ast.fix_missing_locations(ast.Module(body=[future, client], type_ignores=[]))
        namespace = {"datetime": datetime, "timezone": timezone, "API_TIMEOUT": 10,
                     "aiohttp": SimpleNamespace(ClientError=HttpError), "_LOGGER": logging.getLogger(__name__)}
        exec(compile(module, str(source), "exec"), namespace)
        self.task = {
            "id": 5, "name": "Weekly", "frequencyType": "weekly", "frequency": 2,
            "frequencyMetadata": {"days": [1, 3]}, "nextDueDate": "2026-10-20T16:00:00Z",
            "assignedTo": 1, "assignees": [{"userId": 1}, {"userId": 2}],
            "assignStrategy": "round_robin", "updatedAt": "2026-10-11T15:00:00Z",
            "isActive": True, "isRolling": True, "isPrivate": False, "projectId": 3,
            "description": "Keep this", "priority": 2, "points": 4, "requireApproval": True,
            "notification": True, "notificationMetadata": {"templates": [{"value": 1, "unit": "h"}]},
            "labelsV2": [{"id": 8, "name": "Home"}, {"id": 10, "name": "Weekly"}], "subTasks": [{"id": 9, "name": "Step"}],
            "completionActions": [{"type": "test"}],
            "thingChore": {"thingId": 6, "triggerState": "on", "condition": "eq"},
        }
        self.requests = []
        self.put_response = Response({}, status=200)

        def get(url, **kwargs):
            self.requests.append(("get", url, kwargs))
            return Response({"res": deepcopy(self.task)}, status=200)

        def put(url, **kwargs):
            self.requests.append(("put", url, kwargs))
            return self.put_response

        self.client = namespace["DonetickApiClient"]("https://example.invalid", "token", SimpleNamespace(get=get, put=put))

    async def test_anyone_preserves_full_task_configuration(self):
        original = deepcopy(self.task)
        await self.client.async_assign_task(5, None)
        method, url, args = self.requests[-1]
        self.assertEqual((method, url), ("put", "https://example.invalid/api/v1/chores/"))
        payload = args["json"]
        self.assertIsNone(payload["assignedTo"])
        self.assertEqual(payload["assignStrategy"], "no_assignee")
        self.assertEqual(payload["assignees"], [])
        self.assertEqual(payload["labelsV2"], [{"id": 8}, {"id": 10}])
        self.assertEqual(payload["thingTrigger"], {"thingID": 6, "triggerState": "on", "condition": "eq"})
        for key, value in original.items():
            if key not in ("assignedTo", "assignStrategy", "assignees", "labelsV2"):
                self.assertEqual(payload[key], value, key)
        self.assertEqual(self.task, original)

    async def test_anyone_can_be_assigned_back_to_a_user(self):
        self.task.update(assignStrategy="no_assignee", assignedTo=None, assignees=[])
        await self.client.async_assign_task(5, 2)
        payload = self.requests[-1][2]["json"]
        self.assertEqual(payload["assignedTo"], 2)
        self.assertEqual(payload["assignStrategy"], "keep_last_assigned")
        self.assertEqual(payload["assignees"], [{"userId": 2}])

    async def test_existing_user_reassignment_uses_dedicated_endpoint(self):
        await self.client.async_assign_task(5, 2)
        _, url, args = self.requests[-1]
        self.assertEqual(url, "https://example.invalid/api/v1/chores/5/assignee")
        self.assertEqual(args["json"]["assignee"], 2)

    async def test_new_circle_member_is_added_without_losing_task_settings(self):
        original = deepcopy(self.task)
        await self.client.async_assign_task(5, 3)
        _, url, args = self.requests[-1]
        self.assertEqual(url, "https://example.invalid/api/v1/chores/")
        payload = args["json"]
        self.assertEqual(payload["assignedTo"], 3)
        self.assertEqual(payload["assignees"], [*original["assignees"], {"userId": 3}])
        self.assertEqual(payload["assignStrategy"], "round_robin")
        self.assertEqual(payload["updatedAt"], original["updatedAt"])
        for key, value in original.items():
            if key not in ("assignedTo", "assignees", "labelsV2"):
                self.assertEqual(payload[key], value, key)
        self.assertEqual(self.task, original)

    async def test_single_person_list_is_replaced_by_the_new_member(self):
        self.task.update(assignees=[{"userId": 1}], assignedTo=1, assignStrategy="random")
        original = deepcopy(self.task)
        await self.client.async_assign_task(5, 3)
        method, url, args = self.requests[-1]
        self.assertEqual((method, url), ("put", "https://example.invalid/api/v1/chores/"))
        payload = args["json"]
        self.assertEqual(payload["assignees"], [{"userId": 3}])
        self.assertEqual(payload["assignedTo"], 3)
        self.assertEqual(payload["assignStrategy"], "random")
        for key, value in original.items():
            if key not in ("assignedTo", "assignees", "labelsV2"):
                self.assertEqual(payload[key], value, key)

    async def test_new_member_edit_denial_is_reported(self):
        self.put_response = Response({"error": "user does not have permission to edit this chore"})
        with self.assertRaisesRegex(ValueError, "permission to edit"):
            await self.client.async_assign_task(5, 3)

    async def test_new_member_edit_requires_update_timestamp(self):
        self.task.pop("updatedAt")
        with self.assertRaisesRegex(ValueError, "no update timestamp"):
            await self.client.async_assign_task(5, 3)
        self.assertEqual(len(self.requests), 1)

    async def test_missing_timestamp_prevents_full_edit(self):
        self.task.pop("updatedAt")
        with self.assertRaisesRegex(ValueError, "no update timestamp"):
            await self.client.async_assign_task(5, None)
        self.assertEqual(len(self.requests), 1)

    async def test_edit_denial_is_reported(self):
        self.put_response = Response({"error": "user does not have permission to edit this chore"})
        with self.assertRaisesRegex(ValueError, "permission to edit"):
            await self.client.async_assign_task(5, None)

    async def test_stale_edit_is_reported(self):
        self.put_response = Response({"error": "chore has been modified by another user, please refresh and try again"})
        with self.assertRaisesRegex(ValueError, "modified by another user"):
            await self.client.async_assign_task(5, None)

    async def test_server_prefixed_edit_denial_is_reported_on_both_endpoints(self):
        # Donetick 0.1.80 prefixes CanEdit errors on the editor and assignee endpoints.
        for assigned_to in (None, 2):
            with self.subTest(assigned_to=assigned_to):
                self.put_response = Response({"error": "You cannot edit this chore: "
                                              "chore has been modified by another user, please refresh and try again"})
                with self.assertRaisesRegex(ValueError, "reassignment \\(403\\): chore has been modified"):
                    await self.client.async_assign_task(5, assigned_to)
