import json
import unittest

from smarttv.backends.base import BackendUnavailable, TVError
from smarttv.backends.enigma2 import Enigma2Backend
from smarttv.openwebif import OpenWebif, OpenWebifError
from smarttv.players.base import PlayerError
from smarttv.players.enigma2 import Enigma2Player

from tests.test_openwebif import FakeReceiver


def client(replies=None, **settings):
    receiver = FakeReceiver(replies)
    settings.setdefault("host", "10.0.0.5")
    return OpenWebif(settings, fetch=receiver), receiver


class BackendTests(unittest.TestCase):
    def setUp(self):
        self.client, self.receiver = client({"statusinfo": {"inStandby": "false"}})
        self.backend = Enigma2Backend({"host": "10.0.0.5"}, client=self.client)

    def test_capabilities_include_reading_the_power_state(self):
        self.assertTrue(self.backend.available())
        self.assertIn("power_status", self.backend.capabilities())

    def test_power_off_uses_standby_by_default(self):
        self.backend.power_off()
        self.assertIn("newstate=5", self.receiver.requests[0])

    def test_deep_standby_is_opt_in(self):
        backend = Enigma2Backend(
            {"host": "10.0.0.5", "deep_standby": True}, client=self.client
        )
        backend.power_off()
        self.assertIn("newstate=1", self.receiver.requests[0])

    def test_power_status_reads_the_box(self):
        self.assertEqual(self.backend.power_status(), "on")

    def test_keys_are_translated_to_input_codes(self):
        self.backend.send_key("ok")
        self.assertIn("command=352", self.receiver.requests[0])
        self.backend.send_key("red")
        self.assertIn("command=398", self.receiver.requests[1])

    def test_a_key_the_receiver_lacks_is_rejected(self):
        with self.assertRaises(TVError):
            self.backend.send_key("source")

    def test_notify_shows_a_message_on_screen(self):
        self.backend.notify("العشاء جاهز")
        self.assertIn("api/message", self.receiver.requests[0])

    def test_raw_passes_a_query_through(self):
        self.backend.raw("api/zap?sRef=1:0:19:x")
        self.assertIn("sRef=1%3A0%3A19%3Ax", self.receiver.requests[0])

    def test_raw_needs_a_command(self):
        with self.assertRaises(TVError):
            self.backend.raw("  ")

    def test_an_unreachable_box_is_unavailable_not_broken(self):
        def refuse(url):
            raise OpenWebifError("cannot reach the receiver: timed out")

        backend = Enigma2Backend(
            {"host": "10.0.0.5"}, client=OpenWebif({"host": "10.0.0.5"}, fetch=refuse)
        )
        with self.assertRaises(BackendUnavailable):
            backend.power_on()

    def test_a_rejected_command_is_a_real_error(self):
        def reject(url):
            raise OpenWebifError("receiver returned HTTP 500")

        backend = Enigma2Backend(
            {"host": "10.0.0.5"}, client=OpenWebif({"host": "10.0.0.5"}, fetch=reject)
        )
        with self.assertRaises(TVError):
            backend.power_on()


class PlayerTests(unittest.TestCase):
    def setUp(self):
        self.client, self.receiver = client(
            {"statusinfo": {"currservice_name": "MBC 1", "volume": 40}}
        )
        self.player = Enigma2Player({"host": "10.0.0.5"}, client=self.client)

    def test_a_plain_url_is_wrapped_in_a_service_reference(self):
        result = self.player.play("http://provider/live.ts")
        self.assertFalse(result["live"])
        self.assertIn("4097%3A0%3A1", self.receiver.requests[0])

    def test_a_channel_from_the_receiver_zaps_the_tuner(self):
        # Items loaded from the box carry its own streaming URL; playing
        # one should tune the receiver, not stream from it.
        result = self.player.play("http://10.0.0.5:8001/1:0:19:283D:3FB:1:C00000:0:0:0:")
        self.assertTrue(result["live"])
        self.assertIn("sRef=1%3A0%3A19", self.receiver.requests[0])
        self.assertNotIn("4097", self.receiver.requests[0])

    def test_a_bare_service_reference_is_zapped_too(self):
        self.player.play("1:0:19:283D:3FB:1:C00000:0:0:0:")
        self.assertIn("sRef=1%3A0%3A19", self.receiver.requests[0])

    def test_playing_nothing_is_an_error(self):
        with self.assertRaises(PlayerError):
            self.player.play("")

    def test_transport_controls_use_remote_keys(self):
        self.player.toggle()
        self.player.stop()
        self.assertIn("command=164", self.receiver.requests[0])
        self.assertIn("command=128", self.receiver.requests[1])

    def test_seek_presses_scale_with_the_request(self):
        result = self.player.seek(90)
        self.assertEqual(result["seek_presses"], 3)
        self.assertTrue(all("command=208" in url for url in self.receiver.requests))

    def test_volume_is_absolute_on_a_receiver(self):
        self.player.set_volume(55)
        self.assertIn("set=set55", self.receiver.requests[0])

    def test_status_reports_the_current_channel(self):
        status = self.player.status()
        self.assertTrue(status["running"])
        self.assertEqual(status["title"], "MBC 1")
        self.assertIsNone(status["position"])

    def test_status_survives_an_unreachable_box(self):
        def refuse(url):
            raise OpenWebifError("cannot reach the receiver")

        player = Enigma2Player(
            {"host": "10.0.0.5"}, client=OpenWebif({"host": "10.0.0.5"}, fetch=refuse)
        )
        status = player.status()
        self.assertFalse(status["running"])
        self.assertIn("error", status)

    def test_no_host_means_unavailable(self):
        self.assertFalse(Enigma2Player({}).available())


if __name__ == "__main__":
    unittest.main()
