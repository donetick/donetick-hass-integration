"""Skip Task uses the endpoint Donetick has and reports its failures."""
import ast
import json
import logging
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

COMPONENT = Path(__file__).resolve().parents[1] / "custom_components" / "donetick"
DOMAIN = "donetick"


class HttpError(Exception):
    pass


class HomeAssistantError(Exception):
    pass


class Response:
    def __init__(self, status=200, body=None):
        self.status = status
        self.body = body

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


class Session:
    """Records POST requests and answers each with the same response."""

    def __init__(self, response):
        self.response = response
        self.requests = []

    def post(self, url, **kwargs):
        self.requests.append((url, kwargs))
        return self.response


def api_class():
    source = COMPONENT / "api.py"
    tree = ast.parse(source.read_text(encoding="utf-8"))
    client = next(node for node in tree.body if isinstance(node, ast.ClassDef))
    client.body = [
        node for node in client.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and node.name in ("__init__", "_headers", "_raise_for_status", "async_skip_task")
    ]
    future = ast.ImportFrom(module="__future__", names=[ast.alias(name="annotations")], level=0)
    module = ast.fix_missing_locations(ast.Module(body=[future, client], type_ignores=[]))
    namespace = {
        "aiohttp": SimpleNamespace(ClientError=HttpError),
        "API_TIMEOUT": 10,
        "json": json,
        "DonetickTask": SimpleNamespace(from_json=lambda data: SimpleNamespace(**data)),
        "_LOGGER": logging.getLogger(__name__),
    }
    exec(compile(module, str(source), "exec"), namespace)
    return namespace["DonetickApiClient"]


class SkipTaskApiTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.client_type = api_class()

    async def skip(self, completed_by=None, response=None):
        session = Session(response or Response(200, {"res": {"id": 42, "name": "Dishes"}}))
        client = self.client_type("https://donetick.invalid/", "test-token", session)
        task = await client.async_skip_task(42, completed_by)
        return task, session.requests

    async def test_skips_through_the_full_api_instead_of_a_missing_external_route(self):
        task, requests = await self.skip()
        self.assertEqual(task.id, 42)
        self.assertEqual(len(requests), 1)
        url, kwargs = requests[0]
        self.assertEqual(url, "https://donetick.invalid/api/v1/chores/42/skip")
        self.assertNotIn("params", kwargs)
        self.assertEqual(kwargs["headers"],
                         {"secretkey": "test-token", "Content-Type": "application/json"})

    async def test_completed_by_asks_the_server_to_act_as_that_member(self):
        _, requests = await self.skip(completed_by=7)
        headers = requests[0][1]["headers"]
        self.assertEqual(headers["X-Impersonate-User-ID"], "7")

    async def test_missing_performer_leaves_attribution_to_the_token_owner(self):
        _, requests = await self.skip()
        self.assertNotIn("X-Impersonate-User-ID", requests[0][1]["headers"])

    async def test_refusals_reach_the_caller(self):
        reason = "Insufficient permissions for impersonation"
        with self.assertRaisesRegex(ValueError, reason):
            await self.skip(completed_by=7, response=Response(403, {"error": reason}))

    async def test_a_malformed_body_is_not_reported_as_success(self):
        with self.assertRaises(KeyError):
            await self.skip(response=Response(200, {"id": 42}))


class SkipTaskServiceTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        source = COMPONENT / "__init__.py"
        tree = ast.parse(source.read_text(encoding="utf-8"))
        function = next(node for node in tree.body if isinstance(node, ast.AsyncFunctionDef)
                        and node.name == "async_skip_task_service")
        self.entry = SimpleNamespace(entry_id="dev", domain=DOMAIN)
        self.resolve = AsyncMock(return_value=self.entry)
        namespace = {
            "DOMAIN": DOMAIN,
            "HomeAssistant": object,
            "ServiceCall": object,
            "HomeAssistantError": HomeAssistantError,
            "_get_config_entry": self.resolve,
            "_LOGGER": logging.getLogger(__name__),
        }
        exec(compile(ast.Module(body=[function], type_ignores=[]), str(source), "exec"), namespace)
        self.skip_service = namespace["async_skip_task_service"]
        self.client = SimpleNamespace(async_skip_task=AsyncMock(
            return_value=SimpleNamespace(id=42)))
        self.coordinator = SimpleNamespace(async_request_refresh=AsyncMock())
        self.hass = SimpleNamespace(data={DOMAIN: {"dev": {
            "client": self.client, "coordinator": self.coordinator}}})

    async def call(self, **data):
        await self.skip_service(self.hass, SimpleNamespace(data={"task_id": 42, **data}))

    async def test_a_successful_skip_refreshes_the_lists(self):
        await self.call(completed_by=3)
        self.client.async_skip_task.assert_awaited_once_with(42, 3)
        self.coordinator.async_request_refresh.assert_awaited_once_with()

    async def test_a_failed_skip_raises_instead_of_looking_successful(self):
        self.client.async_skip_task.side_effect = HttpError("404 from Donetick")
        with self.assertRaisesRegex(HomeAssistantError, "Failed to skip Donetick task 42"):
            await self.call()
        self.coordinator.async_request_refresh.assert_not_awaited()


if __name__ == "__main__":
    unittest.main()
