"""Connection changes validate before updating the existing integration entry."""
import ast
import copy
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock, Mock


class ClientError(Exception):
    """Stand-in for aiohttp connection errors in the isolated flow tests."""


class ClientResponseError(ClientError):
    def __init__(self, status):
        self.status = status


class ReconfigureTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        root = Path(__file__).resolve().parents[1] / "custom_components/donetick"
        tree = ast.parse((root / "config_flow.py").read_text(encoding="utf-8"))
        flow = next(node for node in tree.body if isinstance(node, ast.ClassDef)
                    and node.name == "DonetickConfigFlow")
        method = next(node for node in flow.body if isinstance(node, ast.AsyncFunctionDef)
                      and node.name == "async_step_reconfigure")
        self.vol = SimpleNamespace(
            Schema=lambda fields: fields,
            Required=Mock(side_effect=lambda key, **kwargs: key),
            Optional=Mock(side_effect=lambda key, **kwargs: key),
        )
        self.client = SimpleNamespace(async_get_tasks=AsyncMock(return_value=[]))
        self.client_factory = Mock(return_value=self.client)
        namespace = {"Any": object, "FlowResult": dict, "vol": self.vol,
                     "DonetickApiClient": self.client_factory,
                     "async_get_clientsession": lambda hass: "session",
                     "aiohttp": SimpleNamespace(ClientError=ClientError,
                                                ClientResponseError=ClientResponseError)}
        exec((root / "const.py").read_text(), namespace)
        exec(compile(ast.Module(body=[method], type_ignores=[]), str(root / "config_flow.py"), "exec"), namespace)
        self.entry = SimpleNamespace(entry_id="existing-entry", data={
            "url": "http://old:2021", "token": "old-token", "show_due_in": 2,
            "create_assignee_lists": True, "refresh_interval": 900,
            "user_mapping": {"ha-user": 3}, "map_completion_user": True,
        }, options={"other": "preserved"})
        self.original = copy.deepcopy(self.entry.data)
        self.flow = SimpleNamespace(
            context={"entry_id": self.entry.entry_id},
            hass=SimpleNamespace(config_entries=SimpleNamespace(
                async_get_entry=Mock(return_value=self.entry))),
            async_show_form=Mock(side_effect=lambda **kwargs: {"type": "form", **kwargs}),
            async_update_reload_and_abort=Mock(return_value={"type": "abort", "reason": "reconfigure_successful"}),
        )
        self.step = lambda user_input=None: namespace["async_step_reconfigure"](self.flow, user_input)

    async def test_form_suggests_url_without_exposing_saved_token(self):
        result = await self.step()
        self.assertEqual(result["step_id"], "reconfigure")
        self.vol.Required.assert_called_once_with("url", default="http://old:2021")
        self.vol.Optional.assert_called_once_with("token")
        self.client.async_get_tasks.assert_not_awaited()
        self.flow.async_update_reload_and_abort.assert_not_called()

    async def test_valid_connection_updates_only_connection_fields_on_existing_entry(self):
        result = await self.step({"url": " http://new:2021/ ", "token": "replacement"})
        self.client_factory.assert_called_once_with("http://new:2021", "replacement", "session")
        self.client.async_get_tasks.assert_awaited_once()
        self.flow.async_update_reload_and_abort.assert_called_once_with(
            self.entry, data={**self.original, "url": "http://new:2021", "token": "replacement"},
            reason="reconfigure_successful")
        self.flow.hass.config_entries.async_get_entry.assert_called_once_with("existing-entry")
        self.assertEqual(result["reason"], "reconfigure_successful")
        self.assertEqual(self.entry.data, self.original)
        self.assertEqual(self.entry.options, {"other": "preserved"})

    async def test_blank_or_omitted_token_keeps_existing_token(self):
        for value in ({}, {"token": ""}, {"token": "   "}):
            with self.subTest(value=value):
                await self.step({"url": "http://new:2021", **value})
                self.assertEqual(self.client_factory.call_args.args[1], "old-token")
                self.assertEqual(self.flow.async_update_reload_and_abort.call_args.kwargs[
                    "data"]["token"], "old-token")

    async def test_connection_and_auth_failures_never_update_saved_configuration(self):
        for error, expected in ((ClientError(), "cannot_connect"),
                                (TimeoutError(), "cannot_connect"),
                                (ClientResponseError(401), "invalid_auth"),
                                (ClientResponseError(403), "invalid_auth"),
                                (ClientResponseError(500), "cannot_connect"),
                                (ValueError(), "unknown")):
            with self.subTest(error=type(error).__name__, expected=expected):
                self.client.async_get_tasks.side_effect = error
                result = await self.step({"url": "http://new:2021", "token": "bad-token"})
                self.assertEqual(result["errors"], {"base": expected})
                self.flow.async_update_reload_and_abort.assert_not_called()
                self.assertEqual(self.entry.data, self.original)
                self.assertEqual(self.vol.Required.call_args.kwargs["default"], "http://new:2021")
                # Failed submissions must not put a token into schema defaults either.
                self.assertEqual(self.vol.Optional.call_args.kwargs, {})

    async def test_failed_connection_can_be_corrected_in_same_flow(self):
        self.client.async_get_tasks.side_effect = [ClientError(), []]
        failed = await self.step({"url": "http://wrong:2021"})
        self.assertEqual(failed["errors"], {"base": "cannot_connect"})
        succeeded = await self.step({"url": "http://correct:2021"})
        self.assertEqual(succeeded["reason"], "reconfigure_successful")
        self.flow.async_update_reload_and_abort.assert_called_once()


if __name__ == "__main__":
    unittest.main()
