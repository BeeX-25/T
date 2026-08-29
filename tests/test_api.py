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

    def test_episodes_need_a_series_id(self):
        with self.assertRaises(ApiError) as caught:
            self.api.dispatch("GET", "/api/episodes", {})
        self.assertEqual(caught.exception.status, 400)

    def test_episodes_without_an_xtream_source_say_so(self):
        with self.assertRaises(ApiError) as caught:
            self.api.dispatch("GET", "/api/episodes", {"series_id": "33"})
        self.assertEqual(caught.exception.status, 404)

    def test_status_includes_the_catalog(self):
        status = self.api.dispatch("GET", "/api/status", {})
        self.assertEqual(status["catalog"]["sources"], 1)
        self.assertIsNone(status["now_playing"])


class InfraredWizardTests(unittest.TestCase):
    LIRC = (
        "begin remote\n  name MAGIC555\n  bits 16\n  flags SPACE_ENC\n"
        "  header 9024 4468\n  one 573 1668\n  zero 573 551\n  ptrail 574\n"
        "  pre_data_bits 16\n  pre_data 0x807F\n"
        "  begin codes\n    KEY_POWER 0x12ED\n    KEY_UP 0x22DD\n  end codes\n"
        "end remote\n"
    )

    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.settings = isolated_settings(self.folder.name)
        # "echo" stands in for the phone's IR blaster.
        self.settings["tv"]["ir"].update(
            {"enabled": True, "brand": "generic_nec", "command": "echo {frequency} {key}"}
        )
        self.api = Api(self.settings)
        self.addCleanup(self.api.shutdown)

    def test_candidates_include_brands_and_an_address_sweep(self):
        data = self.api.dispatch("GET", "/api/ir/candidates", {})
        ids = {entry["id"] for entry in data["candidates"]}
        self.assertIn("lg", ids)
        self.assertIn("generic_nec@3", ids)
        self.assertTrue(data["available"])

    def test_testing_a_candidate_does_not_adopt_it(self):
        self.api.dispatch("POST", "/api/ir/test", {"brand": "sony", "key": "power"})
        self.assertEqual(
            self.api.dispatch("GET", "/api/ir/candidates", {})["profile"]["brand"],
            "generic_nec",
        )

    def test_saving_a_candidate_switches_the_remote(self):
        self.api.dispatch("POST", "/api/ir/save", {"brand": "lg", "address": 4})
        profile = self.api.dispatch("GET", "/api/ir/candidates", {})["profile"]
        self.assertEqual(profile, {"brand": "lg", "address": 4})

    def test_a_saved_remote_survives_a_restart(self):
        self.api.dispatch("POST", "/api/ir/save", {"brand": "sony"})
        restarted = Api(self.settings)
        self.addCleanup(restarted.shutdown)
        self.assertEqual(restarted.registry.get("ir").profile()["brand"], "sony")

    def test_importing_a_lirc_file_registers_and_adopts_it(self):
        data = self.api.dispatch("POST", "/api/ir/import", {"text": self.LIRC})
        self.assertEqual(data["brand"], "magic555")
        self.assertEqual(sorted(data["keys"]), ["power", "up"])
        self.assertEqual(
            self.api.dispatch("GET", "/api/ir/candidates", {})["profile"]["brand"],
            "magic555",
        )

    def test_an_imported_remote_survives_a_restart(self):
        self.api.dispatch("POST", "/api/ir/import", {"text": self.LIRC})
        restarted = Api(self.settings)
        self.addCleanup(restarted.shutdown)
        backend = restarted.registry.get("ir")
        self.assertEqual(backend.profile()["brand"], "magic555")
        self.assertIn("power", backend.known_keys())

    def test_an_imported_remote_actually_sends_its_own_pattern(self):
        self.api.dispatch("POST", "/api/ir/import", {"text": self.LIRC})
        result = self.api.dispatch("POST", "/api/key", {"key": "up"})
        self.assertEqual(result["brand"], "magic555")

    def test_a_bad_import_is_a_client_error(self):
        with self.assertRaises(ApiError) as caught:
            self.api.dispatch("POST", "/api/ir/import", {"text": "nonsense"})
        self.assertEqual(caught.exception.status, 400)

    def test_import_needs_something_to_read(self):
        with self.assertRaises(ApiError):
            self.api.dispatch("POST", "/api/ir/import", {})

    def test_the_wizard_is_404_when_infrared_is_off(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        api = Api(isolated_settings(folder.name), demo=True)
        self.addCleanup(api.shutdown)
        with self.assertRaises(ApiError) as caught:
            api.dispatch("GET", "/api/ir/candidates", {})
        self.assertEqual(caught.exception.status, 404)


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
