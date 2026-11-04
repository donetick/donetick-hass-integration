"""Check integration service routing without requiring a running HA installation."""
import ast
from datetime import date, datetime, time
import json
import logging
from pathlib import Path
import re
from types import SimpleNamespace
from typing import Optional
import unittest
from mapping_test_helpers import load_completion_user
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
COMPONENT = ROOT / "custom_components" / "donetick"
DOMAIN = "donetick"


class ServiceValidationError(Exception):
    """Stands in for homeassistant.exceptions.ServiceValidationError."""


class ServiceRoutingTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        tree = ast.parse((COMPONENT / "__init__.py").read_text(encoding="utf-8"))
        functions = [node for node in tree.body if isinstance(node, ast.AsyncFunctionDef)
                     and node.name in ("_get_config_entry", "async_complete_task_service")]
        registry = SimpleNamespace(async_get=lambda entity_id: SimpleNamespace(
            config_entry_id="upstream" if entity_id == "todo.upstream" else "dev"))
        namespace = {"DOMAIN": DOMAIN, "ConfigEntry": object, "HomeAssistant": object,
                     "ServiceCall": object, "_LOGGER": logging.getLogger(__name__),
                     "completion_user": load_completion_user(),
                     "er": SimpleNamespace(async_get=lambda hass: registry)}
        exec(compile(ast.Module(body=functions, type_ignores=[]), "routing", "exec"), namespace)
        self.resolve = namespace["_get_config_entry"]
        self.complete = namespace["async_complete_task_service"]
        self.dev = SimpleNamespace(entry_id="dev", domain=DOMAIN)
        self.upstream = SimpleNamespace(entry_id="upstream", domain="other_integration")
        entries = {entry.entry_id: entry for entry in (self.dev, self.upstream)}
        self.hass = SimpleNamespace(
            data={DOMAIN: {"dev": {}}, "other_integration": {"upstream": {}}},
            config_entries=SimpleNamespace(async_get_entry=entries.get,
                async_entries=lambda domain: [e for e in entries.values() if e.domain == domain]),
        )

    async def test_default_and_explicit_routes_use_integration(self):
        for selector in (None, "dev", "todo.dev"):
            self.assertIs(await self.resolve(self.hass, selector), self.dev)

    async def test_upstream_entry_and_entity_are_rejected(self):
        for selector in ("upstream", "todo.upstream", "missing"):
            self.assertIsNone(await self.resolve(self.hass, selector))
            # Would raise KeyError if the handler attempted to access a integration client.
            await self.complete(self.hass, SimpleNamespace(data={
                "task_id": 1, "config_entry_id": selector}))

    async def test_unloaded_entry_is_rejected(self):
        self.hass.data[DOMAIN].clear()
        self.assertIsNone(await self.resolve(self.hass, "dev"))

    def load_create_task_service(self):
        """Load async_create_task_service with the due date helper from api.py."""
        wanted = ("_get_config_entry", "async_create_task_service", "normalize_due_date")
        functions = []
        for name in ("__init__.py", "api.py"):
            tree = ast.parse((COMPONENT / name).read_text(encoding="utf-8"))
            functions += [node for node in tree.body if getattr(node, "name", None) in wanted
                          or isinstance(node, ast.Assign)
                          and getattr(node.targets[0], "id", None) == "_DATE_ONLY_PATTERN"]
        registry = SimpleNamespace(async_get=lambda entity_id: None)
        namespace = {"DOMAIN": DOMAIN, "ConfigEntry": object, "HomeAssistant": object,
                     "ServiceCall": object, "Optional": Optional, "_LOGGER": logging.getLogger(__name__),
                     "re": re, "date": date, "time": time, "datetime": datetime,
                     "dt_util": SimpleNamespace(
                         get_default_time_zone=lambda: ZoneInfo("Europe/Brussels")),
                     "ServiceValidationError": ServiceValidationError,
                     "er": SimpleNamespace(async_get=lambda hass: registry)}
        exec(compile(ast.Module(body=functions, type_ignores=[]), "create", "exec"), namespace)
        created = []

        async def async_create_task(*args):
            created.append(args)
            return SimpleNamespace(id=17)

        async def async_request_refresh():
            pass

        self.hass.data[DOMAIN]["dev"] = {
            "client": SimpleNamespace(async_create_task=async_create_task),
            "coordinator": SimpleNamespace(async_request_refresh=async_request_refresh),
        }
        return namespace["async_create_task_service"], created

    async def test_create_task_rejects_an_unusable_due_date_before_any_request(self):
        # Only logged, the call would count as a success in Home Assistant with nothing created.
        create, created = self.load_create_task_service()
        with self.assertRaisesRegex(ServiceValidationError, "'next Tuesday'; use RFC3339 or YYYY-MM-DD"):
            await create(self.hass, SimpleNamespace(data={"name": "Milk", "due_date": "next Tuesday"}))
        self.assertEqual(created, [])

    async def test_create_task_passes_a_usable_due_date_on(self):
        create, created = self.load_create_task_service()
        await create(self.hass, SimpleNamespace(data={"name": "Milk", "due_date": "2026-11-01"}))
        self.assertEqual(created, [("Milk", None, "2026-11-01T23:59:59+01:00", None)])

    def test_create_task_accepts_only_a_positive_created_by(self):
        # voluptuous is not installed here, so the schema runs against the few validators it uses.
        def coerce(kind):
            return kind

        def value_range(min=None):
            def check(value):
                if min is not None and value < min:
                    raise ValueError(f"{value} is below {min}")
                return value
            return check

        def all_of(*validators):
            def check(value):
                for validator in validators:
                    value = validator(value)
                return value
            return check

        vol = SimpleNamespace(Schema=lambda fields: fields, Optional=str, Required=str,
                              Coerce=coerce, Range=value_range, All=all_of)
        tree = ast.parse((COMPONENT / "__init__.py").read_text(encoding="utf-8"))
        schema = next(node for node in tree.body if isinstance(node, ast.Assign)
                      and getattr(node.targets[0], "id", None) == "CREATE_TASK_SCHEMA")
        fields = eval(compile(ast.Expression(schema.value), "schema", "eval"),
                      {"vol": vol, "cv": SimpleNamespace(string=str)})
        created_by = fields["created_by"]
        self.assertEqual(created_by("3"), 3)
        for value in ("0", "-2"):
            with self.assertRaises(ValueError):
                created_by(value)

    def test_the_registry_helper_the_routing_uses_is_imported(self):
        # setUp supplies er itself, so only the module's imports show it is really there.
        tree = ast.parse((COMPONENT / "__init__.py").read_text(encoding="utf-8"))
        imported = {(node.module, alias.name, alias.asname) for node in tree.body
                    if isinstance(node, ast.ImportFrom) for alias in node.names}
        self.assertIn(("homeassistant.helpers", "entity_registry", "er"), imported)

    def test_the_names_create_task_relies_on_are_imported(self):
        # load_create_task_service supplies them itself; without the imports the service raises NameError.
        tree = ast.parse((COMPONENT / "__init__.py").read_text(encoding="utf-8"))
        imported = {(node.module, alias.name) for node in tree.body
                    if isinstance(node, ast.ImportFrom) for alias in node.names}
        self.assertIn(("homeassistant.exceptions", "ServiceValidationError"), imported)
        self.assertIn(("api", "normalize_due_date"), imported)

    def test_the_options_listener_is_removed_when_the_entry_unloads(self):
        # A listener left behind by a reload would reload the entry once more per later change.
        tree = ast.parse((COMPONENT / "__init__.py").read_text(encoding="utf-8"))
        setup = next(node for node in tree.body if isinstance(node, ast.AsyncFunctionDef)
                     and node.name == "async_setup_entry")
        calls = [node for node in ast.walk(setup) if isinstance(node, ast.Call)
                 and isinstance(node.func, ast.Attribute)]
        listeners = [call for call in calls if call.func.attr == "add_update_listener"]
        self.assertEqual(len(listeners), 1)
        unloads = [call for call in calls if call.func.attr == "async_on_unload"]
        self.assertTrue(any(listeners[0] in call.args for call in unloads))

    def test_component_identity_and_python_syntax(self):
        manifest = json.loads((COMPONENT / "manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(manifest["domain"], COMPONENT.name)
        self.assertEqual(manifest["name"], "Donetick")
        constants = {}
        exec((COMPONENT / "const.py").read_text(encoding="utf-8"), constants)
        self.assertEqual(constants["DOMAIN"], manifest["domain"])
        self.assertEqual(constants["TODO_STORAGE_KEY"], "donetick_items")
        self.assertFalse((COMPONENT.parent / ("donetick" + "_dev")).exists())
        for path in COMPONENT.rglob("*.py"):
            compile(path.read_text(encoding="utf-8"), str(path), "exec")


if __name__ == "__main__":
    unittest.main()
