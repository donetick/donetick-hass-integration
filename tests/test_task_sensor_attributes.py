"""Check task metadata parsing and sensor exposure without an HA installation."""
import ast
from dataclasses import dataclass
from datetime import datetime
from html.parser import HTMLParser
import logging
from pathlib import Path
import re
from types import SimpleNamespace
from typing import Any, List, Optional
import unittest


ROOT = Path(__file__).resolve().parents[1] / "custom_components/donetick_dev"


def load_definitions(filename, names, namespace):
    source = ROOT / filename
    tree = ast.parse(source.read_text(encoding="utf-8"))
    definitions = [node for node in tree.body if getattr(node, "name", None) in names]
    future = ast.ImportFrom(module="__future__", names=[ast.alias(name="annotations")], level=0)
    module = ast.fix_missing_locations(ast.Module(body=[future, *definitions], type_ignores=[]))
    exec(compile(module, str(source), "exec"), namespace)


def load_task_model(namespace):
    namespace.update(HTMLParser=HTMLParser, re=re)
    load_definitions(
        "model.py",
        {"_InlineImageParser", "_strip_inline_images", "_parse_datetime", "DonetickTask"},
        namespace,
    )


class CoordinatorStub:
    def __init__(self, coordinator):
        self.coordinator = coordinator


class TaskSensorAttributeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        namespace = dict(dataclass=dataclass, datetime=datetime, Any=Any, List=List,
                         Optional=Optional, _LOGGER=logging.getLogger(__name__),
                         CoordinatorEntity=CoordinatorStub, SensorEntity=type("SensorStub", (), {}))
        load_task_model(namespace)
        load_definitions("chore_sensor.py", {"DonetickChoreSensor"}, namespace)
        cls.task_class = namespace["DonetickTask"]
        cls.sensor_class = namespace["DonetickChoreSensor"]

    def attributes(self, **fields):
        task = self.task_class.from_json({"id": 1, "name": "Maintenance", **fields})
        sensor = self.sensor_class(SimpleNamespace(data=[task]), SimpleNamespace(entry_id="test"), task.id)
        return sensor.extra_state_attributes

    def test_inline_images_are_removed_without_changing_surrounding_html(self):
        prefix = '<p>Clean &amp; inspect.</p>\n'
        link_image = '<img src="https://example.invalid/chore.jpg" alt="Example">'
        suffix = '<p><strong>Replace</strong> if worn.</p>'
        large_image = '<img src="data:image/png;base64,' + "A" * 4_500_000 + '">'
        other_image = "<IMG alt='angle > limit'\n SRC='DATA:IMAGE/JPEG;BASE64,AAAA' />"
        attributes = self.attributes(
            description=prefix + large_image + link_image + other_image + suffix,
            points=5,
        )
        self.assertEqual(attributes["description"], prefix + link_image + suffix)
        self.assertEqual(attributes["points"], 5)

    def test_preserves_empty_and_text_only_descriptions(self):
        for value in (None, "", "Plain text\nCheck the filter."):
            with self.subTest(value=value):
                self.assertEqual(self.attributes(description=value)["description"], value)

    def test_points_preserve_zero_and_unset_values(self):
        for value in (10, 0, None):
            with self.subTest(value=value):
                self.assertEqual(self.attributes(points=value)["points"], value)
        self.assertIsNone(self.attributes()["points"])

    def test_interval_units_accompany_existing_frequency(self):
        for unit in ("hours", "days", "weeks", "months", "years"):
            with self.subTest(unit=unit):
                attrs = self.attributes(frequencyType="interval", frequency=6,
                                        frequencyMetadata={"unit": unit})
                self.assertEqual(attrs["interval_type"], unit)
                self.assertEqual(attrs["frequency"], 6)
                self.assertEqual(attrs["frequency_type"], "interval")

    def test_missing_or_invalid_interval_metadata(self):
        for metadata in (None, {}, "weeks", [], {"unit": None}, {"unit": 6}, {"unit": ""}):
            with self.subTest(metadata=metadata):
                self.assertIsNone(self.attributes(frequencyType="interval",
                                                 frequencyMetadata=metadata)["interval_type"])

    def test_other_schedules_do_not_expose_stale_interval_units(self):
        for schedule in ("once", "daily", "weekly", "trigger"):
            with self.subTest(schedule=schedule):
                self.assertIsNone(self.attributes(frequencyType=schedule,
                                                 frequencyMetadata={"unit": "weeks"})["interval_type"])


if __name__ == "__main__":
    unittest.main()
