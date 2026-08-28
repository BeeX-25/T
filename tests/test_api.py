import unittest

from smarttv.api import Api, ApiError
from smarttv.config import load


def demo_api():
    return Api(load(), demo=True)


class DispatchTests(unittest.TestCase):
    def setUp(self):
        self.api = demo_api()
        self.tv = self.api.registry.get("dummy")

    def tearDown(self):
        self.api.shutdown()

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


class AutomationActionTests(unittest.TestCase):
    def test_rules_drive_the_registry(self):
        settings = load()
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
