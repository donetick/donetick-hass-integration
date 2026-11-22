"""Thing entities are scoped to their config entry in the entity registry."""
import ast
import logging
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Optional
import unittest

COMPONENT = Path(__file__).resolve().parents[1] / "custom_components" / "donetick"
DOMAIN = "donetick"


class _StubEntity:
    @property
    def unique_id(self):
        return self._attr_unique_id


def _load_thing_module():
    source = COMPONENT / "thing.py"
    tree = ast.parse(source.read_text(encoding="utf-8"))
    keep_names = {
        "_platform_for_thing",
        "_migrate_unique_ids",
        "DonetickThingBase",
        "DonetickThingSensor",
        "DonetickThingSwitch",
    }
    nodes = [
        node
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.ClassDef)) and node.name in keep_names
    ]
    ns = {
        "__name__": __name__,
        "Any": Any,
        "Optional": Optional,
        "logging": logging,
        "_LOGGER": logging.getLogger(__name__),
        "DOMAIN": DOMAIN,
        "Entity": _StubEntity,
        "SensorEntity": type("SensorEntity", (), {}),
        "SwitchEntity": type("SwitchEntity", (), {}),
        "DonetickApiClient": object,
        "DonetickThing": object,
        "DataUpdateCoordinator": object,
    }
    exec(compile(ast.Module(body=nodes, type_ignores=[]), str(source), "exec"), ns)
    return ns


_MOD = _load_thing_module()
DonetickThingSensor = _MOD["DonetickThingSensor"]
DonetickThingSwitch = _MOD["DonetickThingSwitch"]
_migrate_unique_ids = _MOD["_migrate_unique_ids"]


class FakeRegistry:
    def __init__(self, entities):
        self.entities = entities
        self.updated = []

    def async_get_entity_id(self, platform, domain, unique_id):
        return self.entities.get((platform, unique_id))

    def async_update_entity(self, entity_id, *, new_unique_id):
        self.updated.append((entity_id, new_unique_id))


def thing(thing_id=1, thing_type="boolean"):
    return SimpleNamespace(
        id=thing_id,
        name="Washer",
        type=thing_type,
        state="false",
        user_id=1,
        circle_id=1,
    )


class ThingEntityIdTests(unittest.TestCase):
    def test_two_integrations_get_distinct_unique_ids(self):
        first = DonetickThingSwitch(None, thing(), None, "entry-a")
        second = DonetickThingSwitch(None, thing(), None, "entry-b")
        self.assertEqual(
            (first.unique_id, second.unique_id),
            ("entry-a_thing_1", "entry-b_thing_1"),
        )

    def test_sensor_uses_the_same_entry_prefix(self):
        sensor = DonetickThingSensor(None, thing(7, "action"), None, "entry")
        self.assertEqual(sensor.unique_id, "entry_thing_7")


class ThingUniqueIdMigrationTests(unittest.TestCase):
    def test_old_entity_is_renamed_in_place(self):
        registry = FakeRegistry({("switch", "donetick_thing_1"): "switch.washer"})
        _migrate_unique_ids(registry, "entry-b", [thing()])
        self.assertEqual(
            registry.updated,
            [("switch.washer", "entry-b_thing_1")],
        )

    def test_existing_scoped_entity_is_not_overwritten(self):
        registry = FakeRegistry({
            ("switch", "donetick_thing_1"): "switch.old",
            ("switch", "entry-b_thing_1"): "switch.new",
        })
        _migrate_unique_ids(registry, "entry-b", [thing()])
        self.assertEqual(registry.updated, [])

    def test_missing_old_entity_is_a_no_op(self):
        registry = FakeRegistry({})
        _migrate_unique_ids(registry, "entry-b", [thing()])
        self.assertEqual(registry.updated, [])


if __name__ == "__main__":
    unittest.main()
