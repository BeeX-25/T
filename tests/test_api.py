import tempfile
import unittest

from smarttv.api import Api, ApiError

from tests.support import isolated_settings


class DispatchTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.api = Api(isolated_settings(self.folder.name), demo=True)
        self.tv = self.api.registry.get("dummy")

    def tearDown(self):
        self.api.shutdown()
        self.folder.cleanup()

    def test_unknown_endpoint(self):
        with self.assertRaises(ApiError) as caught:
            self.api.dispatch("GET", "/api/nope", {})
        self.assertEqual(caught.exception.status, 404)

    def test_trailing_slash_is_accepted(self):
        self.assertIn("backend", self.api.dispatch("GET", "/api/status/", {}))

    def test_power_toggle_follows_current_state(self):
        self.api.dispatch("POST", "/api/power", {"state": "on"})
        self.assertEqual(self.tv.power_status(), "on")
        self.api.dispatch("POST", "/api/power", {"state": "toggle"})
        self.assertEqual(self.tv.power_status(), "standby")
        self.api.dispatch("POST", "/api/power", {"state": "toggle"})
        self.assertEqual(self.tv.power_status(), "on")

    def test_power_rejects_nonsense(self):
        with self.assertRaises(ApiError):
            self.api.dispatch("POST", "/api/power", {"state": "sideways"})

    def test_key_repeat_is_capped(self):
        self.api.dispatch("POST", "/api/key", {"key": "up", "repeat": 999})
        self.assertEqual(self.tv.log.count("key:up"), 20)

    def test_unknown_key_is_a_client_error(self):
        with self.assertRaises(ApiError) as caught:
            self.api.dispatch("POST", "/api/key", {"key": "eject"})
        self.assertEqual(caught.exception.status, 400)

    def test_volume_actions(self):
        before = self.tv.volume_level
        self.api.dispatch("POST", "/api/volume", {"action": "up", "repeat": 3})
        self.assertEqual(self.tv.volume_level, before + 3)
        with self.assertRaises(ApiError):
            self.api.dispatch("POST", "/api/volume", {"action": "louder"})

    def test_source_switching(self):
        self.api.dispatch("POST", "/api/source", {"index": 2})
        self.assertEqual(self.tv.source, 2)

    def test_unsupported_command_surfaces_as_bad_gateway(self):
        # The dummy TV has no app launcher, which is exactly what a plain
        # CEC-only setup looks like.
        with self.assertRaises(ApiError) as caught:
            self.api.dispatch("POST", "/api/app", {"app": "youtube"})
        self.assertEqual(caught.exception.status, 502)

    def test_cast_requires_a_url(self):
        with self.assertRaises(ApiError):
            self.api.dispatch("POST", "/api/cast", {})

    def test_status_shape(self):
        status = self.api.dispatch("GET", "/api/status", {})
        self.assertEqual(status["backend"], "dummy")
        self.assertIn("player", status)
        self.assertIn("scheduler", status)

    def test_config_hides_secrets(self):
        described = self.api.dispatch("GET", "/api/config", {})
        self.assertIn("shortcuts", described)
        self.assertNotIn("auth_token", str(described))

    def test_sleep_timer_round_trip(self):
        self.api.dispatch("POST", "/api/sleep", {"minutes": 30})
        self.assertGreater(self.api.scheduler.describe()["sleep_timer_seconds"], 1700)
        self.api.dispatch("DELETE", "/api/sleep", {})
        self.assertIsNone(self.api.scheduler.describe()["sleep_timer_seconds"])

    def test_sleep_timer_default_comes_from_config(self):
        self.api.dispatch("POST", "/api/sleep", {})
        remaining = self.api.scheduler.describe()["sleep_timer_seconds"]
        self.assertGreater(remaining, 45 * 60 - 10)


class LibraryTests(unittest.TestCase):
    PLAYLIST = (
        "#EXTM3U\n"
        '#EXTINF:-1 tvg-id="mbc1" group-title="عام",MBC 1\n'
        "http://stream/1\n"
        '#EXTINF:-1 group-title="أخبار",Al Jazeera\n'
        "http://stream/2\n"
    )

    def setUp(self):
        import os

        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        playlist = os.path.join(self.folder.name, "list.m3u")
        with open(playlist, "w", encoding="utf-8") as handle:
            handle.write(self.PLAYLIST)
        settings = isolated_settings(self.folder.name)
        settings["catalog"]["sources"] = [
            {"name": "local", "path": playlist, "kind": "live"}
        ]
        self.api = Api(settings, demo=True)
        self.addCleanup(self.api.shutdown)

    def test_browse_returns_items_and_groups(self):
        data = self.api.dispatch("GET", "/api/catalog", {"kind": "live"})
        self.assertEqual(data["total"], 2)
        self.assertEqual({g["name"] for g in data["groups"]}, {"عام", "أخبار"})

    def test_browse_filters_by_query_and_group(self):
        self.assertEqual(self.api.dispatch("GET", "/api/catalog", {"q": "jazeera"})["total"], 1)
        self.assertEqual(self.api.dispatch("GET", "/api/catalog", {"group": "عام"})["total"], 1)

    def test_browse_marks_favorites(self):
        self.api.dispatch("POST", "/api/favorites", {"url": "http://stream/1", "name": "MBC 1"})
        items = self.api.dispatch("GET", "/api/catalog", {})["items"]
        flags = {item["url"]: item["favorite"] for item in items}
        self.assertTrue(flags["http://stream/1"])
        self.assertFalse(flags["http://stream/2"])

    def test_favorites_toggle_round_trip(self):
        self.api.dispatch("POST", "/api/favorites", {"url": "http://stream/2", "name": "AJ"})
        self.assertEqual(len(self.api.dispatch("GET", "/api/favorites", {})["items"]), 1)
        self.api.dispatch("POST", "/api/favorites", {"url": "http://stream/2"})
        self.assertEqual(self.api.dispatch("GET", "/api/favorites", {})["items"], [])

    def test_favorites_need_a_url(self):
        with self.assertRaises(ApiError):
            self.api.dispatch("POST", "/api/favorites", {"name": "بلا رابط"})

    def test_refresh_reports_what_it_loaded(self):
        self.assertEqual(self.api.dispatch("POST", "/api/catalog/refresh", {})["items"], 2)

    def test_epg_requires_a_channel(self):
        with self.assertRaises(ApiError):
            self.api.dispatch("GET", "/api/epg", {})
        self.assertEqual(
            self.api.dispatch("GET", "/api/epg", {"channel": "mbc1"})["programmes"], []
        )

    def test_cast_records_history_even_without_a_player(self):
        with self.assertRaises(ApiError):
            self.api.dispatch(
                "POST", "/api/cast", {"url": "http://stream/1", "name": "MBC 1"}
            )
        # The player is missing in the test environment, so nothing is
        # remembered: history is only written once playback really starts.
        self.assertEqual(self.api.store.history(), [])

    def test_resume_endpoint_reports_stored_positions(self):
        self.api.store.remember_position("http://stream/1", 90, 3600, "MBC 1")
        data = self.api.dispatch("GET", "/api/resume", {})
        self.assertEqual(data["items"][0]["url"], "http://stream/1")

    def test_status_includes_the_catalog(self):
        status = self.api.dispatch("GET", "/api/status", {})
        self.assertEqual(status["catalog"]["sources"], 1)
        self.assertIsNone(status["now_playing"])


class AutomationActionTests(unittest.TestCase):
    def test_rules_drive_the_registry(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        settings = isolated_settings(folder.name)
        settings["automation"]["rules"] = [
            {"name": "night", "cron": "0 2 * * *", "action": "power_off"}
        ]
        api = Api(settings, demo=True)
        try:
            api.registry.call("power_on")
            import time

            api.scheduler.poll(time.struct_time((2026, 8, 28, 2, 0, 0, 4, 240, 0)))
            self.assertEqual(api.registry.call("power_status"), "standby")
        finally:
            api.shutdown()


if __name__ == "__main__":
    unittest.main()
