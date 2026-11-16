"""Thing entities are scoped to their config entry in the entity registry."""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from custom_components.donetick.model import DonetickThing
from custom_components.donetick.thing import (
    DonetickThingSensor,
    DonetickThingSwitch,
    _migrate_unique_ids,
)


class FakeRegistry:
    def __init__(self, entities):
        self.entities = entities
        self.updated = []

    def async_get_entity_id(self, platform, domain, unique_id):
        return self.entities.get((platform, unique_id))

    def async_update_entity(self, entity_id, *, new_unique_id):
        self.updated.append((entity_id, new_unique_id))


def thing(thing_id=1, thing_type="boolean"):
    return DonetickThing(id=thing_id, name="Washer", type=thing_type,
                         state="false", user_id=1, circle_id=1)


class ThingEntityIdTests(unittest.TestCase):
    def test_two_integrations_get_distinct_unique_ids(self):
        first = DonetickThingSwitch(None, thing(), None, "entry-a")
        second = DonetickThingSwitch(None, thing(), None, "entry-b")
        self.assertEqual((first.unique_id, second.unique_id),
                         ("entry-a_thing_1", "entry-b_thing_1"))

    def test_sensor_uses_the_same_entry_prefix(self):
        sensor = DonetickThingSensor(None, thing(7, "action"), None, "entry")
        self.assertEqual(sensor.unique_id, "entry_thing_7")


class ThingUniqueIdMigrationTests(unittest.TestCase):
    def test_old_entity_is_renamed_in_place(self):
        registry = FakeRegistry({("switch", "donetick_thing_1"): "switch.washer"})
        _migrate_unique_ids(registry, "entry-b", [thing()])
        self.assertEqual(registry.updated,
                         [("switch.washer", "entry-b_thing_1")])

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
