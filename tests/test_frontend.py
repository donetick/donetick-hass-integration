"""Regression checks for the bundled frontend lifecycle."""
import ast
import asyncio
from hashlib import sha256
import json
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock, Mock

ROOT = Path(__file__).resolve().parents[1]


class FrontendTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        source = ROOT / "custom_components/donetick/frontend.py"
        tree = ast.parse(source.read_text(encoding="utf-8"))
        tree.body = [node for node in tree.body
                     if not isinstance(node, (ast.Import, ast.ImportFrom))]
        self.add_url = Mock()
        namespace = {"__file__": str(source), "asyncio": asyncio,
                     "sha256": sha256, "Path": Path, "HomeAssistant": object,
                     "StaticPathConfig": lambda *args: args,
                     "add_extra_js_url": self.add_url}
        exec(compile(tree, str(source), "exec"), namespace)
        self.setup_frontend = namespace["async_setup_frontend"]
        self.card_file = namespace["CARD_FILE"]

        async def executor(fn):
            await asyncio.sleep(0)
            return fn()

        self.hass = SimpleNamespace(data={}, async_add_executor_job=executor,
                                    http=SimpleNamespace(async_register_static_paths=AsyncMock()))

    async def test_concurrent_entries_and_reload_register_only_once(self):
        await asyncio.gather(self.setup_frontend(self.hass), self.setup_frontend(self.hass))
        await self.setup_frontend(self.hass)
        self.hass.http.async_register_static_paths.assert_awaited_once_with([
            ("/donetick/donetick-user-todo-card.js", str(self.card_file), False)])
        version = sha256(self.card_file.read_bytes()).hexdigest()[:12]
        self.add_url.assert_called_once_with(
            self.hass, f"/donetick/donetick-user-todo-card.js?v={version}")

    async def test_registration_failure_can_retry(self):
        self.hass.http.async_register_static_paths.side_effect = RuntimeError("Not ready")
        with self.assertRaises(RuntimeError):
            await self.setup_frontend(self.hass)
        self.add_url.assert_not_called()
        self.hass.http.async_register_static_paths.side_effect = None
        await self.setup_frontend(self.hass)
        self.add_url.assert_called_once()

    async def test_hacs_package_contains_card_and_setup_dependency(self):
        manifest = json.loads((ROOT / "custom_components/donetick/manifest.json").read_text())
        self.assertIn("frontend", manifest["dependencies"])
        self.assertTrue(self.card_file.is_file())
        self.assertIn("donetick-user-todo-card", self.card_file.read_text(encoding="utf-8"))
        tree = ast.parse((ROOT / "custom_components/donetick/__init__.py").read_text())
        setup = next(node for node in tree.body
                     if isinstance(node, ast.AsyncFunctionDef) and node.name == "async_setup_entry")
        self.assertTrue(any(isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
                            and node.func.id == "async_setup_frontend" for node in ast.walk(setup)))
