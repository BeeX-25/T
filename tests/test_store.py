import json
import os
import tempfile
import unittest

from smarttv.store import Store


class StoreTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.path = os.path.join(self.folder.name, "nested", "state.json")
        self.store = Store(self.path)

    def test_favorites_toggle_and_persist(self):
        self.assertTrue(self.store.toggle_favorite({"url": "u1", "name": "قناة"})["favorite"])
        self.assertTrue(Store(self.path).is_favorite("u1"))
        self.assertFalse(self.store.toggle_favorite({"url": "u1"})["favorite"])
        self.assertFalse(Store(self.path).is_favorite("u1"))

    def test_favorite_needs_a_url(self):
        with self.assertRaises(ValueError):
            self.store.toggle_favorite({"name": "بدون رابط"})

    def test_resume_round_trip(self):
        self.store.remember_position("u2", 125.4, 3600, "فيلم")
        self.assertEqual(Store(self.path).resume_position("u2"), 125.4)

    def test_finished_playback_clears_the_resume_point(self):
        self.store.remember_position("u3", 100, 3600)
        self.store.remember_position("u3", 3590, 3600)
        self.assertIsNone(self.store.resume_position("u3"))

    def test_resume_list_is_newest_first(self):
        self.store.remember_position("old", 10, 600)
        self.store.data["resume"]["old"]["at"] = 1
        self.store.remember_position("new", 10, 600)
        self.assertEqual(self.store.resume_list()[0]["url"], "new")

    def test_history_is_deduplicated_and_capped(self):
        for index in range(120):
            self.store.add_history({"url": "u%d" % index, "name": str(index)})
        self.store.add_history({"url": "u119", "name": "again"})
        history = self.store.history(limit=200)
        self.assertEqual(len(history), 100)
        self.assertEqual(history[0]["url"], "u119")
        self.assertEqual(len([e for e in history if e["url"] == "u119"]), 1)

    def test_corrupt_state_file_is_ignored(self):
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        with open(self.path, "w", encoding="utf-8") as handle:
            handle.write("{not json")
        store = Store(self.path)
        self.assertEqual(store.favorites(), [])

    def test_writes_are_atomic_and_valid_json(self):
        self.store.toggle_favorite({"url": "u4", "name": "x"})
        with open(self.path, "r", encoding="utf-8") as handle:
            self.assertIn("favorites", json.load(handle))
        self.assertEqual(
            [name for name in os.listdir(os.path.dirname(self.path))], ["state.json"]
        )

    def test_unwritable_location_does_not_raise(self):
        store = Store("/proc/definitely-not-writable/state.json")
        self.assertFalse(store.save())


if __name__ == "__main__":
    unittest.main()
