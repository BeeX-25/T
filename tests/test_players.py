import unittest

from smarttv.players import create_player
from smarttv.players.android import APP_COMPONENTS, AndroidPlayer, build_view_intent
from smarttv.players.base import PlayerError
from smarttv.players.mpv import MpvPlayer


class FactoryTests(unittest.TestCase):
    def test_explicit_backends(self):
        self.assertIsInstance(create_player({"backend": "mpv"}), MpvPlayer)
        self.assertIsInstance(create_player({"backend": "android"}), AndroidPlayer)

    def test_auto_picks_by_host(self):
        player = create_player({"backend": "auto"})
        self.assertIn(player.name, ("mpv", "android"))

    def test_per_backend_settings_are_passed_through(self):
        player = create_player({"backend": "mpv", "mpv": {"binary": "/usr/bin/mpv2"}})
        self.assertEqual(player.binary, "/usr/bin/mpv2")

    def test_enabled_flag_is_inherited(self):
        player = create_player({"backend": "mpv", "enabled": False})
        self.assertFalse(player.available())

    def test_unknown_backend(self):
        with self.assertRaises(ValueError):
            create_player({"backend": "chromecast"})


class AndroidIntentTests(unittest.TestCase):
    def test_stream_url_gets_a_component_and_a_mime_type(self):
        argv = build_view_intent("http://host/live.m3u8", APP_COMPONENTS["vlc"])
        self.assertIn("-t", argv)
        self.assertEqual(argv[-1], APP_COMPONENTS["vlc"])
        self.assertIn("http://host/live.m3u8", argv)

    def test_web_pages_are_left_untyped_so_their_app_can_claim_them(self):
        for url in ("https://youtu.be/abc", "https://www.youtube.com/watch?v=abc"):
            self.assertNotIn("-t", build_view_intent(url))

    def test_video_files_are_typed(self):
        self.assertIn("-t", build_view_intent("http://host/movie.mp4"))

    def test_capabilities_depend_on_key_injection(self):
        plain = AndroidPlayer({})
        rooted = AndroidPlayer({"use_input_keyevents": True})
        self.assertNotIn("pause", plain.capabilities())
        self.assertIn("pause", rooted.capabilities())
        self.assertIn("seek", rooted.capabilities())

    def test_pause_without_permission_explains_itself(self):
        with self.assertRaises(PlayerError) as caught:
            AndroidPlayer({}).pause()
        self.assertIn("shell", str(caught.exception))

    def test_status_lists_what_is_controllable(self):
        status = AndroidPlayer({}).status()
        self.assertEqual(status["player"], "android")
        self.assertIn("play", status["controllable"])


class MpvTests(unittest.TestCase):
    def test_capabilities(self):
        self.assertEqual(
            MpvPlayer({}).capabilities(),
            {"play", "pause", "seek", "volume", "stop", "position"},
        )

    def test_play_without_url(self):
        with self.assertRaises(PlayerError):
            MpvPlayer({}).play("")

    def test_missing_binary_is_reported_not_crashed(self):
        player = MpvPlayer({"binary": "definitely-not-installed"})
        self.assertFalse(player.available())
        self.assertEqual(player.status()["running"], False)
        with self.assertRaises(PlayerError):
            player.play("http://host/movie.mp4")


if __name__ == "__main__":
    unittest.main()
