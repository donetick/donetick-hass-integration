"""Verify update failures retain useful authorization reasons."""
import ast
from datetime import datetime
import logging
from pathlib import Path
from types import SimpleNamespace
import unittest


class HttpError(Exception):
    pass


class Response:
    status = 403

    def __init__(self, body, status=403):
        self.body = body
        self.status = status

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return False

    async def json(self):
        if isinstance(self.body, Exception):
            raise self.body
        return self.body

    def raise_for_status(self):
        if self.status >= 400:
            raise HttpError(f"{self.status} from Donetick")


class UpdatePermissionTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        source = Path(__file__).resolve().parents[1] / "custom_components/donetick/api.py"
        tree = ast.parse(source.read_text(encoding="utf-8"))
        client = next(node for node in tree.body if isinstance(node, ast.ClassDef))
        client.body = [node for node in client.body if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
                       and node.name in ("__init__", "_headers", "_raise_for_status", "async_update_task",
                                         "async_delete_task", "async_complete_task")]
        future = ast.ImportFrom(module="__future__", names=[ast.alias(name="annotations")], level=0)
        module = ast.fix_missing_locations(ast.Module(body=[future, client], type_ignores=[]))
        namespace = {"aiohttp": SimpleNamespace(ClientError=HttpError), "API_TIMEOUT": 10,
                     "datetime": datetime,
                     "DonetickTask": SimpleNamespace(from_json=lambda data: SimpleNamespace(
                         next_due_date=datetime.fromisoformat(data["nextDueDate"].replace("Z", "+00:00")),
                         is_active=data["isActive"])),
                     "_LOGGER": logging.getLogger(__name__), "json": __import__("json")}
        exec(compile(module, str(source), "exec"), namespace)
        self.client_type = namespace["DonetickApiClient"]

    async def update(self, body):
        session = SimpleNamespace(put=lambda *args, **kwargs: Response(body))
        client = self.client_type("https://example.invalid", "test-token", session)
        return await client.async_update_task(46, name="Test")

    async def test_permission_and_membership_reasons_reach_caller(self):
        for reason in (
            "Only plus members can access this endpoint",
            "You can only update your own chores",
            "user does not have permission to edit this chore",
            "chore has been modified by another user, please refresh and try again",
            "updatedAt is in the future and cannot be used to edit the chore",
            "Only the chore creator or a circle admin/manager can update this chore",
        ):
            with self.assertRaisesRegex(ValueError, reason):
                await self.update({"error": reason})

    async def test_unknown_or_non_json_errors_preserve_http_failure(self):
        for body in ({"error": "Proxy denied request"}, [], ValueError("Not JSON"), HttpError("Not JSON")):
            with self.assertRaises(HttpError):
                await self.update(body)

    async def test_delete_permission_reason_reaches_caller(self):
        for reason in ("You can only delete your own chores",
                       "Only the chore creator or a circle admin/manager can delete this chore"):
            session = SimpleNamespace(delete=lambda *args, **kwargs: Response({"error": reason}))
            client = self.client_type("https://example.invalid", "test-token", session)
            with self.assertRaisesRegex(ValueError, reason):
                await client.async_delete_task(47)

    async def complete(self, body, status=400, completed_by=None):
        requests = []

        def post(url, **kwargs):
            requests.append((url, kwargs))
            return Response(body, status=status)

        client = self.client_type("https://example.invalid", "test-token", SimpleNamespace(post=post))
        task = await client.async_complete_task(47, completed_by=completed_by)
        return requests, task

    async def test_refused_completions_say_who_the_server_turned_down(self):
        for reason in ("User is not assigned to chore", "Chore is out of completion window"):
            with self.assertRaisesRegex(ValueError, reason):
                await self.complete({"error": reason})

    async def test_other_completion_failures_preserve_http_failure(self):
        for body, status in (({"error": "Invalid ID"}, 400), ({"error": "Error getting chore"}, 500),
                             ({"error": "You can only update your own chores"}, 400),
                             ({"error": "User is not assigned to chore"}, 500), ([], 400)):
            with self.assertRaises(HttpError):
                await self.complete(body, status=status)

    async def test_completion_sends_the_chosen_member_to_the_server(self):
        body = {"nextDueDate": "2026-10-09T12:00:00Z", "isActive": True}
        requests, _ = await self.complete(body, status=200, completed_by=3)
        url, arguments = requests[0]
        self.assertEqual(url, "https://example.invalid/eapi/v1/chore/47/complete")
        self.assertEqual(arguments["headers"]["secretkey"], "test-token")
        self.assertEqual(arguments["params"], {"completedBy": 3})
        # Without a chosen member the server credits the caller's own account.
        requests, _ = await self.complete(body, status=200)
        self.assertEqual(requests[0][1]["params"], {})

    async def test_update_sends_external_api_parameters(self):
        requests = []

        def put(url, **kwargs):
            requests.append((url, kwargs))
            return Response({"nextDueDate": "2026-10-09T12:00:00Z", "isActive": True}, status=200)

        client = self.client_type("https://example.invalid", "test-token", SimpleNamespace(put=put))
        await client.async_update_task(47, description="", due_date="2026-10-09T12:00:00Z")
        url, arguments = requests[0]
        self.assertEqual(url, "https://example.invalid/eapi/v1/chore/47")
        self.assertEqual(arguments["headers"]["secretkey"], "test-token")
        self.assertEqual(arguments["json"], {
            "description": "", "dueDate": "2026-10-09T12:00:00Z",
        })

    async def test_delete_sends_external_api_request(self):
        requests = []

        def delete(url, **kwargs):
            requests.append((url, kwargs))
            return Response({}, status=200)

        client = self.client_type("https://example.invalid", "test-token", SimpleNamespace(delete=delete))
        self.assertTrue(await client.async_delete_task(47))
        url, arguments = requests[0]
        self.assertEqual(url, "https://example.invalid/eapi/v1/chore/47")
        self.assertEqual(arguments["headers"]["secretkey"], "test-token")

    async def test_assignment_and_unarchive_can_be_used_together(self):
        source = Path(__file__).resolve().parents[1] / "custom_components/donetick/__init__.py"
        tree = ast.parse(source.read_text(encoding="utf-8"))
        handler = next(node for node in tree.body if isinstance(node, ast.AsyncFunctionDef)
                       and node.name == "async_update_task_service")
        calls = []

        async def resolve(hass, selector):
            return SimpleNamespace(entry_id="dev")

        async def update(*args):
            calls.append(("update", args))
            return SimpleNamespace(is_active=True)

        async def assign(*args):
            calls.append(("assign", args))

        async def refresh():
            calls.append(("refresh", ()))

        namespace = {"HomeAssistant": object, "ServiceCall": object, "DOMAIN": "donetick",
                     "_get_config_entry": resolve, "HomeAssistantError": ValueError,
                     "_LOGGER": logging.getLogger(__name__)}
        exec(compile(ast.Module(body=[handler], type_ignores=[]), str(source), "exec"), namespace)
        hass = SimpleNamespace(data={"donetick": {"dev": {
            "client": SimpleNamespace(async_update_task=update, async_assign_task=assign),
            "coordinator": SimpleNamespace(async_request_refresh=refresh),
        }}})
        for fields, expected in (
            ({"assigned_to": 2}, ["assign", "refresh"]),
            ({"assigned_to": None}, ["assign", "refresh"]),
            ({"force_unarchive": True}, ["update", "refresh"]),
            ({"force_unarchive": True, "assigned_to": 2}, ["update", "assign", "refresh"]),
        ):
            calls.clear()
            await namespace["async_update_task_service"](hass, SimpleNamespace(data={"task_id": 1, **fields}))
            self.assertEqual([name for name, _ in calls], expected)
            if "assigned_to" in fields:
                assignment = next(args for name, args in calls if name == "assign")
                self.assertEqual(assignment, (1, fields["assigned_to"]))
            if fields.get("force_unarchive"):
                self.assertTrue(calls[0][1][-1])

    async def test_delete_service_reports_failures_to_ha(self):
        source = Path(__file__).resolve().parents[1] / "custom_components/donetick/__init__.py"
        tree = ast.parse(source.read_text(encoding="utf-8"))
        handler = next(node for node in tree.body if isinstance(node, ast.AsyncFunctionDef)
                       and node.name == "async_delete_task_service")

        class HomeAssistantError(Exception):
            pass

        async def resolve(hass, selector):
            return SimpleNamespace(entry_id="dev")

        async def delete(task_id):
            raise ValueError("Permission denied")

        namespace = {"HomeAssistant": object, "ServiceCall": object, "DOMAIN": "donetick",
                     "_get_config_entry": resolve, "HomeAssistantError": HomeAssistantError,
                     "_LOGGER": logging.getLogger(__name__)}
        exec(compile(ast.Module(body=[handler], type_ignores=[]), str(source), "exec"), namespace)
        hass = SimpleNamespace(data={"donetick": {"dev": {
            "client": SimpleNamespace(async_delete_task=delete), "coordinator": object(),
        }}})
        with self.assertRaisesRegex(HomeAssistantError, "Permission denied"):
            await namespace["async_delete_task_service"](hass, SimpleNamespace(data={"task_id": 47}))
