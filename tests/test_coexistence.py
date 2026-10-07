"""Check coexistence routing without requiring a running HA installation."""
import ast
import json
import logging
from pathlib import Path
from types import SimpleNamespace
import unittest

ROOT = Path(__file__).resolve().parents[1]
COMPONENT = ROOT / "custom_components" / "donetick_dev"
DOMAIN = "donetick_dev"


class CoexistenceTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        tree = ast.parse((COMPONENT / "__init__.py").read_text(encoding="utf-8"))
        functions = [node for node in tree.body if isinstance(node, ast.AsyncFunctionDef)
                     and node.name in ("_get_config_entry", "async_complete_task_service")]
        namespace = {"DOMAIN": DOMAIN, "ConfigEntry": object, "HomeAssistant": object,
                     "ServiceCall": object, "_LOGGER": logging.getLogger(__name__)}
        exec(compile(ast.Module(body=functions, type_ignores=[]), "routing", "exec"), namespace)
        self.resolve = namespace["_get_config_entry"]
        self.complete = namespace["async_complete_task_service"]
        self.dev = SimpleNamespace(entry_id="dev", domain=DOMAIN)
        self.upstream = SimpleNamespace(entry_id="upstream", domain="donetick")
        entries = {entry.entry_id: entry for entry in (self.dev, self.upstream)}
        registry = SimpleNamespace(async_get=lambda entity_id: SimpleNamespace(
            config_entry_id="upstream" if entity_id == "todo.upstream" else "dev"))
        self.hass = SimpleNamespace(
            data={DOMAIN: {"dev": {}}, "donetick": {"upstream": {}}},
            config_entries=SimpleNamespace(async_get_entry=entries.get,
                async_entries=lambda domain: [e for e in entries.values() if e.domain == domain]),
            helpers=SimpleNamespace(entity_registry=SimpleNamespace(async_get=lambda: registry)),
        )

    async def test_default_and_explicit_routes_use_fork(self):
        for selector in (None, "dev", "todo.dev"):
            self.assertIs(await self.resolve(self.hass, selector), self.dev)

    async def test_upstream_entry_and_entity_are_rejected(self):
        for selector in ("upstream", "todo.upstream", "missing"):
            self.assertIsNone(await self.resolve(self.hass, selector))
            # Would raise KeyError if the handler attempted to access a fork client.
            await self.complete(self.hass, SimpleNamespace(data={
                "task_id": 1, "config_entry_id": selector}))

    async def test_unloaded_entry_is_rejected(self):
        self.hass.data[DOMAIN].clear()
        self.assertIsNone(await self.resolve(self.hass, "dev"))

    def test_component_identity_and_python_syntax(self):
        manifest = json.loads((COMPONENT / "manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(manifest["domain"], COMPONENT.name)
        self.assertEqual(manifest["name"], "Donetick Dev")
        constants = {}
        exec((COMPONENT / "const.py").read_text(encoding="utf-8"), constants)
        self.assertEqual(constants["DOMAIN"], manifest["domain"])
        self.assertEqual(constants["TODO_STORAGE_KEY"], "donetick_dev_items")
        self.assertFalse((COMPONENT.parent / "donetick").exists())
        for path in COMPONENT.rglob("*.py"):
            compile(path.read_text(encoding="utf-8"), str(path), "exec")


if __name__ == "__main__":
    unittest.main()
