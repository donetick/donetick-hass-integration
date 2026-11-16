"""Deleted chores must remove their sensor, not leave it unavailable forever."""
import ast
import asyncio
import logging
import unittest
from pathlib import Path
from types import SimpleNamespace

COMPONENT = Path(__file__).resolve().parents[1] / "custom_components" / "donetick"
DOMAIN = "donetick"


class Sensor:
    """Stand-in for DonetickChoreSensor that records its removal."""

    def __init__(self, coordinator, config_entry, task_id):
        self._task_id = task_id
        self.unique_id = f"dt_chore_{config_entry.entry_id}_{task_id}"
        self.hass = None
        self.removal_requests = []

    async def async_remove(self, *, force_remove=False):
        self.removal_requests.append(force_remove)


class Registry:
    def __init__(self):
        self.entities = {}
        self.removed = []

    def async_get_entity_id(self, domain, platform, unique_id):
        return self.entities.get(unique_id)

    def async_remove(self, entity_id):
        self.removed.append(entity_id)
        self.entities = {key: value for key, value in self.entities.items()
                         if value != entity_id}


class SensorCleanupTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        source = COMPONENT / "chore_sensor.py"
        tree = ast.parse(source.read_text(encoding="utf-8"))
        functions = [node for node in tree.body if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
                     and node.name in ("async_setup_chore_sensors", "_track_new_chores", "_remove_entity")]
        self.registry = Registry()
        namespace = {
            "DOMAIN": DOMAIN,
            "HomeAssistant": object,
            "ConfigEntry": object,
            "AddEntitiesCallback": object,
            "DataUpdateCoordinator": object,
            "DonetickMember": object,
            "DonetickTask": object,
            "DonetickChoreSensor": Sensor,
            "callback": lambda function: function,
            "er": SimpleNamespace(async_get=lambda hass: self.registry),
            "_LOGGER": logging.getLogger(__name__),
        }
        exec(compile(ast.Module(body=functions, type_ignores=[]), str(source), "exec"), namespace)
        self.setup_sensors = namespace["async_setup_chore_sensors"]

        self.listeners = []
        self.added = []
        self.tasks = []
        self.coordinator = SimpleNamespace(
            data=[self.task(1), self.task(2, active=False)],
            async_add_listener=self.listeners.append,
        )
        self.hass = SimpleNamespace(
            data={DOMAIN: {"dev": {"coordinator": self.coordinator}}},
            async_create_task=self.tasks.append,
        )

        def add_entities(entities):
            for entity in entities:
                entity.hass = self.hass
                self.added.append(entity)

        self.add_entities = add_entities

    @staticmethod
    def task(task_id, active=True):
        return SimpleNamespace(id=task_id, is_active=active)

    async def setup(self):
        await self.setup_sensors(
            self.hass, SimpleNamespace(entry_id="dev"), self.add_entities)
        for entity in self.added:
            self.registry.entities[entity.unique_id] = f"sensor.chore_{entity._task_id}"
        return self.listeners[0]

    async def update(self, tasks):
        self.coordinator.data = tasks
        self.listeners[0]()
        if self.tasks:
            await asyncio.gather(*self.tasks)
            self.tasks.clear()

    async def test_only_active_chores_get_a_sensor(self):
        await self.setup()
        self.assertEqual([entity._task_id for entity in self.added], [1])

    async def test_deleting_every_chore_removes_the_live_sensor(self):
        await self.setup()
        sensor = self.added[0]
        await self.update([])
        self.assertEqual(self.registry.removed, ["sensor.chore_1"])
        self.assertEqual(sensor.removal_requests, [True])

    async def test_deleting_one_chore_keeps_the_others(self):
        self.coordinator.data = [self.task(1), self.task(2)]
        await self.setup()
        first, second = self.added
        await self.update([self.task(2)])
        self.assertEqual(self.registry.removed, ["sensor.chore_1"])
        self.assertEqual(first.removal_requests, [True])
        self.assertEqual(second.removal_requests, [])

    async def test_a_failed_refresh_does_not_remove_sensors(self):
        await self.setup()
        await self.update(None)
        self.assertEqual(self.registry.removed, [])
        self.assertEqual(self.added[0].removal_requests, [])

    async def test_a_new_chore_adds_a_sensor(self):
        await self.setup()
        await self.update([self.task(1), self.task(3)])
        self.assertEqual([entity._task_id for entity in self.added], [1, 3])
        self.assertIsNotNone(self.added[1].hass)
        self.assertEqual(self.registry.removed, [])


if __name__ == "__main__":
    unittest.main()
