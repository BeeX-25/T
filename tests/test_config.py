import json
import os
import tempfile
import unittest

from smarttv import config


class DeepMergeTests(unittest.TestCase):
    def test_nested_override_keeps_untouched_keys(self):
        base = {"a": {"x": 1, "y": 2}, "b": 3}
        merged = config.deep_merge(base, {"a": {"y": 9}})
        self.assertEqual(merged, {"a": {"x": 1, "y": 9}, "b": 3})

    def test_source_is_not_mutated(self):
        base = {"a": {"x": 1}}
        config.deep_merge(base, {"a": {"x": 2}})
        self.assertEqual(base["a"]["x"], 1)

    def test_lists_replace_rather_than_merge(self):
        merged = config.deep_merge({"order": ["cec", "webos"]}, {"order": ["samsung"]})
        self.assertEqual(merged["order"], ["samsung"])


class LoadTests(unittest.TestCase):
    def test_defaults_when_no_file(self):
        settings = config.load()
        self.assertEqual(settings["server"]["port"], 8099)
        self.assertIn("cec", settings["tv"]["order"])

    def test_partial_file_is_merged_over_defaults(self):
        with tempfile.TemporaryDirectory() as folder:
            path = os.path.join(folder, "config.json")
            with open(path, "w", encoding="utf-8") as handle:
                json.dump({"server": {"port": 9001}}, handle)
            settings = config.load(path)
        self.assertEqual(settings["server"]["port"], 9001)
        self.assertEqual(settings["server"]["host"], "0.0.0.0")
        self.assertTrue(settings["tv"]["cec"]["enabled"])

    def test_paths_are_expanded(self):
        settings = config.load()
        self.assertFalse(settings["tv"]["samsung"]["token_file"].startswith("~"))

    def test_non_object_root_is_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            path = os.path.join(folder, "config.json")
            with open(path, "w", encoding="utf-8") as handle:
                handle.write("[1, 2]")
            with self.assertRaises(ValueError):
                config.load(path)


if __name__ == "__main__":
    unittest.main()
