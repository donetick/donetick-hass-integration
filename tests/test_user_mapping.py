"""Completion identities must be explicit, scoped, and backward compatible."""
from types import SimpleNamespace
import unittest
from mapping_test_helpers import load_completion_user, load_username_mappings


class UserMappingTests(unittest.TestCase):
    def setUp(self):
        self.resolve = load_completion_user()
        self.entry = SimpleNamespace(data={"map_completion_user":True, "user_mapping":{"ha-a":3}})
        self.context = SimpleNamespace(user_id="ha-a")

    def test_disabled_mapping_preserves_existing_defaults(self):
        self.entry.data["map_completion_user"] = False
        self.assertEqual(self.resolve(self.entry, self.context, default=2), 2)
        self.assertIsNone(self.resolve(self.entry, self.context))

    def test_selected_account_works_without_caller_or_automatic_mapping(self):
        self.entry.data["map_completion_user"] = False
        self.assertEqual(self.resolve(self.entry, None, default=2, ha_user="ha-a"), 3)
        other = SimpleNamespace(data={"user_mapping": {"ha-a": 7}})
        self.assertEqual(self.resolve(other, None, ha_user="ha-a"), 7)

    def test_selected_account_never_falls_back_to_caller_or_assignee(self):
        for value in (None, True, 0, -1, "3"):
            self.entry.data["user_mapping"]["selected"] = value
            with self.assertRaisesRegex(ValueError, "selected HA user has no Donetick mapping"):
                self.resolve(self.entry, self.context, default=2, ha_user="selected")

    def test_conflicting_performers_are_rejected(self):
        with self.assertRaisesRegex(ValueError, "not both"):
            self.resolve(self.entry, self.context, explicit=3, ha_user="ha-a")

    def test_mapping_uses_ids_and_is_scoped_to_the_integration(self):
        self.assertEqual(self.resolve(self.entry, self.context, default=2), 3)
        other = SimpleNamespace(data={"map_completion_user":True,"user_mapping":{"ha-a":7}})
        self.assertEqual(self.resolve(other, self.context), 7)
        self.assertEqual(self.resolve(self.entry, SimpleNamespace(user_id="same-name"), default=2), 2)

    def test_no_caller_or_mapping_keeps_defaults(self):
        for context in (None, SimpleNamespace(user_id=None), SimpleNamespace(user_id="ha-b")):
            self.assertEqual(self.resolve(self.entry, context, default=2), 2)
            self.assertIsNone(self.resolve(self.entry, context))

    def test_required_mapping_rejects_automations_and_unmapped_users(self):
        self.entry.data["unmapped_user"] = "require_mapping"
        for context in (None, SimpleNamespace(user_id="ha-b")):
            with self.assertRaisesRegex(ValueError, "No Donetick user is mapped"):
                self.resolve(self.entry, context, default=2)
        self.assertEqual(self.resolve(self.entry, None, explicit=5), 5)

    def test_corrupt_mapping_cannot_credit_the_wrong_user(self):
        self.entry.data["unmapped_user"] = "require_mapping"
        for value in (None, True, 0, -1, "3"):
            self.entry.data["user_mapping"]["ha-a"] = value
            with self.assertRaises(ValueError):
                self.resolve(self.entry, self.context)


class MappingOptionsTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        import ast
        from pathlib import Path
        root = Path(__file__).resolve().parents[1] / "custom_components/donetick"
        tree = ast.parse((root / "config_flow.py").read_text(encoding="utf-8"))
        cls = next(node for node in tree.body if isinstance(node, ast.ClassDef)
                   and node.name == "DonetickOptionsFlowHandler")
        cls.bases = [ast.Name(id="object", ctx=ast.Load())]
        cls.body = [node for node in cls.body if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
                    and node.name != "__init__"]
        namespace = {"FlowResult":dict, "Any":object, "username_mappings":load_username_mappings()}
        exec((root / "const.py").read_text(), namespace)
        from datetime import timedelta
        namespace.update(_config_to_seconds=lambda value:timedelta(**value).total_seconds())
        exec(compile(ast.fix_missing_locations(ast.Module(body=[cls], type_ignores=[])), "mapping_flow", "exec"), namespace)
        self.namespace = namespace
        self.flow = namespace["DonetickOptionsFlowHandler"]()
        self.flow.entry = SimpleNamespace(entry_id="entry", data={"url":"local", "token":"test", "extra":"preserved",
            "user_mapping":{"ha-a":2}, "map_completion_user":True})
        self.saved = []
        async def reload(entry_id):
            pass
        self.flow.hass = SimpleNamespace(config_entries=SimpleNamespace(
            async_update_entry=lambda entry, **kwargs:self.saved.append(kwargs["data"]), async_reload=reload),
            async_create_task=lambda coro:coro.close())
        self.flow.async_create_entry = lambda **kwargs:kwargs
        self.flow.async_abort = lambda **kwargs:kwargs

    async def test_mapping_can_be_disabled_without_loading_server_users(self):
        await self.flow.async_step_user_mapping({"ha_user":"save", "map_completion_user":False,
                                                 "unmapped_user":"require_mapping"})
        self.assertFalse(self.saved[0]["map_completion_user"])
        self.assertEqual(self.saved[0]["user_mapping"], {"ha-a":2})
        self.assertEqual(self.saved[0]["extra"], "preserved")

    async def test_link_and_unlink_preserve_other_mappings_and_settings(self):
        from unittest.mock import AsyncMock
        self.flow.hass.auth = SimpleNamespace(async_get_users=AsyncMock(return_value=[
            SimpleNamespace(id="ha-b", name="Other user", is_active=True, system_generated=False)]))
        client = SimpleNamespace(async_get_circle_members=AsyncMock(return_value=[
            SimpleNamespace(user_id=3, display_name="Member", username="member", is_active=True)]))
        self.namespace.update(DonetickApiClient=lambda *args:client, async_get_clientsession=lambda hass:None)
        settings = {"map_completion_user":True, "unmapped_user":"existing"}
        await self.flow.async_step_user_mapping({**settings, "HA user: Other user":"3"})
        self.assertEqual(self.saved[-1]["user_mapping"], {"ha-a":2,"ha-b":3})
        self.assertEqual(self.saved[-1]["extra"], "preserved")
        self.flow.entry.data = self.saved[-1]
        await self.flow.async_step_user_mapping({**settings, "HA user: Other user":"unmapped"})
        self.assertEqual(self.saved[-1]["user_mapping"], {"ha-a":2})

    async def test_editing_task_settings_keeps_mappings(self):
        self.flow.entry.options = {}
        await self.flow.async_step_settings({"show_due_in":14})
        self.assertEqual(self.saved[0]["user_mapping"], {"ha-a":2})
        self.assertTrue(self.saved[0]["map_completion_user"])
        self.assertEqual(self.saved[0]["show_due_in"], 14)

    async def test_multiple_rows_save_together_without_losing_hidden_mappings(self):
        from unittest.mock import AsyncMock
        self.flow.entry.data["user_mapping"]["hidden-account"] = 8
        self.flow.hass.auth = SimpleNamespace(async_get_users=AsyncMock(return_value=[
            SimpleNamespace(id="ha-a",name="First",is_active=True,system_generated=False),
            SimpleNamespace(id="ha-b",name="Second",is_active=True,system_generated=False)]))
        client = SimpleNamespace(async_get_circle_members=AsyncMock(return_value=[
            SimpleNamespace(user_id=3,display_name="Member 3",username="three",is_active=True),
            SimpleNamespace(user_id=4,display_name="Member 4",username="four",is_active=True)]))
        self.namespace.update(DonetickApiClient=lambda *args:client, async_get_clientsession=lambda hass:None)
        await self.flow.async_step_user_mapping({"map_completion_user":True,"unmapped_user":"existing",
            "HA user: First":"4", "HA user: Second":"3"})
        self.assertEqual(len(self.saved),1)
        self.assertEqual(self.saved[0]["user_mapping"], {"ha-a":4,"ha-b":3,"hidden-account":8})


class UsernameMappingTests(unittest.TestCase):
    def setUp(self):
        self.match = load_username_mappings()

    def user(self, user_id, username, **kwargs):
        return SimpleNamespace(id=user_id, name="Display name", is_active=True, system_generated=False,
            credentials=[SimpleNamespace(auth_provider_type=kwargs.get("provider", "homeassistant"),
                                         data={"username":username})])

    def member(self, user_id, username):
        return SimpleNamespace(user_id=user_id, username=username, is_active=True)

    def test_login_match_ignores_case_and_whitespace(self):
        self.assertEqual(self.match([self.user("ha", " Torben ")], [self.member(2,"torben")]), {"ha":2})

    def test_ambiguous_names_are_not_linked(self):
        self.assertEqual(self.match([self.user("ha","name")], [self.member(1,"name"),self.member(2,"NAME")]), {})
        self.assertEqual(self.match([self.user("a","name"),self.user("b","NAME")], [self.member(2,"name")]), {})

    def test_display_names_and_external_logins_are_not_matched(self):
        self.assertEqual(self.match([self.user("ha","other")], [self.member(2,"Display name")]), {})
        self.assertEqual(self.match([self.user("ha","torben",provider="external")], [self.member(2,"torben")]), {})

    def test_existing_links_win_and_inactive_accounts_are_skipped(self):
        user = self.user("ha","torben")
        member = self.member(2,"torben")
        self.assertEqual(self.match([user],[member],{"ha":5}), {"ha":5})
        member.is_active=False
        self.assertEqual(self.match([user],[member]), {})
        member.is_active=True
        user.is_active=False
        self.assertEqual(self.match([user],[member]), {})


class UsernameConfirmationTests(unittest.TestCase):
    def setUp(self):
        import ast
        from pathlib import Path
        root = Path(__file__).resolve().parents[1] / "custom_components/donetick"
        tree = ast.parse((root / "config_flow.py").read_text(encoding="utf-8"))
        cls = next(node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == "DonetickOptionsFlowHandler")
        method = next(node for node in cls.body if isinstance(node, ast.FunctionDef) and node.name == "_confirmed_mapping_defaults")
        namespace = {"CONF_USER_MAPPING":"user_mapping"}
        exec(compile(ast.Module(body=[method], type_ignores=[]), "confirmation", "exec"), namespace)
        self.confirm = namespace["_confirmed_mapping_defaults"]
        self.flow = SimpleNamespace(entry=SimpleNamespace(data={"user_mapping":{"existing":7}}),
                                    _mapping_defaults={"existing":7,"suggested":2})

    def test_matches_require_explicit_confirmation(self):
        self.assertEqual(self.confirm(self.flow, {}), {"existing":7})
        self.assertEqual(self.confirm(self.flow, {"apply_username_matches":False}), {"existing":7})
        self.assertEqual(self.confirm(self.flow, {"apply_username_matches":True}), {"existing":7,"suggested":2})
