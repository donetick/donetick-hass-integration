"""complete_chore credits any circle member through Donetick's full API."""
import ast
import logging
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock

COMPONENT = Path(__file__).resolve().parents[1] / "custom_components" / "donetick"
DOMAIN = "donetick"


class HttpError(Exception):
    pass


class HomeAssistantError(Exception):
    pass


class ServiceValidationError(HomeAssistantError):
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


class CompleteChoreClientTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        source = COMPONENT / "api.py"
        tree = ast.parse(source.read_text(encoding="utf-8"))
        client = next(node for node in tree.body if isinstance(node, ast.ClassDef))
        client.body = [node for node in client.body if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
                       and node.name in ("__init__", "_headers", "_raise_for_status", "async_complete_chore")]
        future = ast.ImportFrom(module="__future__", names=[ast.alias(name="annotations")], level=0)
        module = ast.fix_missing_locations(ast.Module(body=[future, client], type_ignores=[]))
        namespace = {"aiohttp": SimpleNamespace(ClientError=HttpError), "API_TIMEOUT": 10,
                     "_LOGGER": logging.getLogger(__name__)}
        exec(compile(module, str(source), "exec"), namespace)
        self.client_type = namespace["DonetickApiClient"]

    async def complete(self, response):
        session = Session(response)
        client = self.client_type("https://donetick.invalid/", "test-token", session)
        await client.async_complete_chore(46, 3)
        return session.requests

    async def test_posts_the_performer_to_the_full_api(self):
        requests = await self.complete(Response(200, {"res": {"id": 46}}))
        self.assertEqual(len(requests), 1)
        url, kwargs = requests[0]
        self.assertEqual(url, "https://donetick.invalid/api/v1/chores/46/do")
        self.assertEqual(kwargs["json"], {"completedBy": 3})
        self.assertNotIn("params", kwargs)
        # The token owner acts; no other member is impersonated.
        self.assertEqual(kwargs["headers"], {"secretkey": "test-token", "Content-Type": "application/json"})

    async def test_success_does_not_depend_on_the_response_body(self):
        await self.complete(Response(200, ValueError("Not JSON")))

    async def test_completion_refusals_reach_caller(self):
        for status, reason in (
            (403, "You are not allowed to complete this action, either you are not admin "
                  "or the completed by user is not in the circle"),
            (403, "The selected user cannot see this task"),
            (400, "User is not assigned to chore"),
            (400, "Chore is out of completion window"),
        ):
            with self.subTest(reason=reason), self.assertRaisesRegex(ValueError, reason):
                await self.complete(Response(status, {"error": reason}))

    async def test_other_failures_keep_the_http_error(self):
        for response in (Response(403, {"error": "Proxy denied request"}), Response(500, ValueError("Not JSON"))):
            with self.subTest(status=response.status), self.assertRaises(HttpError):
                await self.complete(response)


class CompleteChoreServiceTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        source = COMPONENT / "__init__.py"
        tree = ast.parse(source.read_text(encoding="utf-8"))
        functions = [node for node in tree.body if isinstance(node, ast.AsyncFunctionDef)
                     and node.name in ("async_complete_chore_service", "_validate_circle_member")]
        self.entry = SimpleNamespace(entry_id="entry")

        async def resolve(hass, config_entry_id):
            self.resolved = config_entry_id
            return self.entry

        namespace = {"DOMAIN": DOMAIN, "HomeAssistant": object, "ServiceCall": object,
                     "HomeAssistantError": HomeAssistantError,
                     "ServiceValidationError": ServiceValidationError,
                     "_get_config_entry": resolve, "_LOGGER": logging.getLogger(__name__)}
        exec(compile(ast.Module(body=functions, type_ignores=[]), str(source), "exec"), namespace)
        self.service = namespace["async_complete_chore_service"]
        self.client = SimpleNamespace(async_complete_chore=AsyncMock(),
                                      async_get_circle_members=AsyncMock(return_value=[]))
        self.coordinator = SimpleNamespace(async_request_refresh=AsyncMock())
        self.config = {"client": self.client, "coordinator": self.coordinator,
                       "circle_members": [self.member(2), self.member(3)]}
        self.hass = SimpleNamespace(data={DOMAIN: {"entry": self.config}})

    @staticmethod
    def member(user_id, active=True):
        return SimpleNamespace(user_id=user_id, is_active=active)

    async def call(self, **data):
        await self.service(self.hass, SimpleNamespace(data={"chore_id": 46, "completed_by": 3, **data}))

    async def test_completes_for_the_member_and_refreshes(self):
        await self.call(config_entry_id="entry")
        self.assertEqual(self.resolved, "entry")
        self.client.async_complete_chore.assert_awaited_once_with(46, 3)
        self.client.async_get_circle_members.assert_not_awaited()
        self.coordinator.async_request_refresh.assert_awaited_once()

    async def test_missing_integration_is_an_error(self):
        self.entry = None
        with self.assertRaises(HomeAssistantError):
            await self.call()
        self.client.async_complete_chore.assert_not_awaited()

    async def test_unknown_member_is_rejected_after_refetching_members(self):
        self.client.async_get_circle_members.return_value = [self.member(2), self.member(3)]
        with self.assertRaisesRegex(ServiceValidationError, "User 9"):
            await self.call(completed_by=9)
        self.client.async_get_circle_members.assert_awaited_once()
        self.client.async_complete_chore.assert_not_awaited()

    async def test_inactive_member_is_rejected(self):
        self.config["circle_members"] = [self.member(2), self.member(3, active=False)]
        self.client.async_get_circle_members.return_value = self.config["circle_members"]
        with self.assertRaises(ServiceValidationError):
            await self.call()
        self.client.async_complete_chore.assert_not_awaited()

    async def test_member_who_joined_later_is_accepted(self):
        members = [self.member(2), self.member(3), self.member(9)]
        self.client.async_get_circle_members.return_value = members
        await self.call(completed_by=9)
        self.client.async_complete_chore.assert_awaited_once_with(46, 9)
        self.assertIs(self.config["circle_members"], members)

    async def test_without_member_list_donetick_decides(self):
        self.config["circle_members"] = []
        await self.call(completed_by=9)
        self.client.async_complete_chore.assert_awaited_once_with(46, 9)

        # A failed refetch must not block the completion either.
        self.client.async_complete_chore.reset_mock()
        self.config["circle_members"] = [self.member(2)]
        self.client.async_get_circle_members.side_effect = HttpError("offline")
        await self.call(completed_by=9)
        self.client.async_complete_chore.assert_awaited_once_with(46, 9)

    async def test_donetick_refusal_is_raised(self):
        self.client.async_complete_chore.side_effect = ValueError(
            "Donetick denied the completion (403): The selected user cannot see this task")
        with self.assertRaisesRegex(HomeAssistantError, "cannot see this task") as raised:
            await self.call()
        self.assertNotIsInstance(raised.exception, ServiceValidationError)
        self.coordinator.async_request_refresh.assert_not_awaited()

    async def test_refresh_failure_says_the_chore_was_completed(self):
        self.coordinator.async_request_refresh.side_effect = HttpError("timeout")
        with self.assertRaisesRegex(HomeAssistantError, "was completed"):
            await self.call()


class CompleteChoreRegistrationTests(unittest.TestCase):
    def setUp(self):
        self.tree = ast.parse((COMPONENT / "__init__.py").read_text(encoding="utf-8"))
        self.assignments = {target.id: node.value for node in self.tree.body if isinstance(node, ast.Assign)
                            for target in node.targets if isinstance(target, ast.Name)}

    def test_service_is_registered_with_its_schema(self):
        self.assertEqual(self.assignments["SERVICE_COMPLETE_CHORE"].value, "complete_chore")
        registered = {}
        for call in (node for node in ast.walk(self.tree) if isinstance(node, ast.Call)):
            if getattr(call.func, "attr", None) == "async_register" and len(call.args) >= 2:
                schema = next((kw.value for kw in call.keywords if kw.arg == "schema"), None)
                registered[getattr(call.args[1], "id", None)] = getattr(schema, "id", None)
        self.assertEqual(registered.get("SERVICE_COMPLETE_CHORE"), "COMPLETE_CHORE_SCHEMA")

    def test_service_is_removed_with_the_last_entry(self):
        unload = next(node for node in self.tree.body
                      if isinstance(node, ast.AsyncFunctionDef) and node.name == "async_unload_entry")
        loop = next(node for node in ast.walk(unload) if isinstance(node, ast.For))
        self.assertIn("SERVICE_COMPLETE_CHORE", [getattr(elt, "id", None) for elt in loop.iter.elts])

    def test_schema_requires_chore_and_performer(self):
        mapping = self.assignments["COMPLETE_CHORE_SCHEMA"].args[0]
        fields = {marker.args[0].value: marker.func.attr for marker in mapping.keys}
        self.assertEqual(fields, {"chore_id": "Required", "completed_by": "Required",
                                  "config_entry_id": "Optional"})

    def test_service_is_documented(self):
        blocks, service = {}, None
        for line in (COMPONENT / "services.yaml").read_text(encoding="utf-8").splitlines():
            if line[:1].isalpha() and line.rstrip().endswith(":"):
                service = line.rstrip()[:-1]
                blocks[service] = []
            elif service:
                blocks[service].append(line.strip())
        fields = [line[:-1] for line in blocks["complete_chore"]
                  if line.endswith(":") and line[:-1] in ("chore_id", "completed_by", "config_entry_id")]
        self.assertEqual(fields, ["chore_id", "completed_by", "config_entry_id"])


if __name__ == "__main__":
    unittest.main()
