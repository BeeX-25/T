import json
import unittest

from smarttv.openwebif import (
    OpenWebif,
    OpenWebifError,
    is_service_reference,
    url_service_reference,
)


class FakeReceiver:
    """Stands in for a box: records requests, replies with canned JSON."""

    def __init__(self, replies=None):
        self.replies = replies or {}
        self.requests = []

    def __call__(self, url):
        self.requests.append(url)
        for fragment, reply in self.replies.items():
            if fragment in url:
                return reply if isinstance(reply, str) else json.dumps(reply)
        return json.dumps({"result": True})


class ServiceReferenceTests(unittest.TestCase):
    def test_url_is_wrapped_and_escaped(self):
        reference = url_service_reference("http://host/a b.m3u8")
        self.assertTrue(reference.startswith("4097:0:1:0:0:0:0:0:0:0:"))
        self.assertIn("%3A%2F%2F", reference)
        self.assertNotIn(" ", reference)

    def test_service_type_is_configurable(self):
        self.assertTrue(url_service_reference("http://x", 5002).startswith("5002:"))

    def test_detecting_references_versus_urls(self):
        self.assertTrue(is_service_reference("1:0:19:283D:3FB:1:C00000:0:0:0:"))
        self.assertFalse(is_service_reference("http://host:8001/x"))
        self.assertFalse(is_service_reference(""))


class ClientTests(unittest.TestCase):
    def setUp(self):
        self.receiver = FakeReceiver()
        self.client = OpenWebif(
            {"host": "10.0.0.5", "port": 81, "stream_port": 8002}, fetch=self.receiver
        )

    def test_urls_include_host_port_and_query(self):
        self.client.zap("1:0:19:x")
        self.assertIn("http://10.0.0.5:81/api/zap?sRef=", self.receiver.requests[0])

    def test_power_states_map_to_numbers(self):
        self.client.power("standby")
        self.assertIn("newstate=5", self.receiver.requests[0])
        self.client.power("wakeup")
        self.assertIn("newstate=4", self.receiver.requests[1])

    def test_unknown_power_state(self):
        with self.assertRaises(OpenWebifError):
            self.client.power("explode")

    def test_volume_actions(self):
        self.client.set_volume("up")
        self.client.set_volume("set", 42)
        self.assertIn("set=up", self.receiver.requests[0])
        self.assertIn("set=set42", self.receiver.requests[1])

    def test_volume_is_clamped(self):
        self.client.set_volume("set", 300)
        self.assertIn("set=set100", self.receiver.requests[0])

    def test_unknown_volume_action(self):
        with self.assertRaises(OpenWebifError):
            self.client.set_volume("louder")

    def test_standby_flag_accepts_strings_and_booleans(self):
        client = OpenWebif({"host": "h"}, fetch=FakeReceiver({"statusinfo": {"inStandby": "true"}}))
        self.assertTrue(client.in_standby())
        client = OpenWebif({"host": "h"}, fetch=FakeReceiver({"statusinfo": {"inStandby": False}}))
        self.assertFalse(client.in_standby())

    def test_play_url_wraps_the_stream(self):
        self.client.play_url("http://provider/live.ts")
        self.assertIn("4097%3A0%3A1", self.receiver.requests[0])

    def test_stream_url_uses_the_streaming_port(self):
        self.assertEqual(
            self.client.stream_url("1:0:19:x"), "http://10.0.0.5:8002/1:0:19:x"
        )

    def test_non_json_reply_is_an_error(self):
        client = OpenWebif({"host": "h"}, fetch=lambda url: "<html>login</html>")
        with self.assertRaises(OpenWebifError):
            client.status()

    def test_receiver_rejection_is_an_error(self):
        client = OpenWebif(
            {"host": "h"}, fetch=lambda url: json.dumps({"result": False, "message": "no"})
        )
        with self.assertRaises(OpenWebifError) as caught:
            client.zap("1:0:1:x")
        self.assertIn("no", str(caught.exception))

    def test_missing_host_is_an_error(self):
        with self.assertRaises(OpenWebifError):
            OpenWebif({}, fetch=self.receiver).status()


if __name__ == "__main__":
    unittest.main()
