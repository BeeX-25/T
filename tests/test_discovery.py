import unittest

from smarttv import discovery


class MSearchTests(unittest.TestCase):
    def test_packet_shape(self):
        packet = discovery.build_msearch("upnp:rootdevice", mx=2)
        self.assertTrue(packet.startswith("M-SEARCH * HTTP/1.1\r\n"))
        self.assertIn('MAN: "ssdp:discover"', packet)
        self.assertIn("ST: upnp:rootdevice", packet)
        self.assertTrue(packet.endswith("\r\n\r\n"))


class ParseResponseTests(unittest.TestCase):
    RESPONSE = (
        "HTTP/1.1 200 OK\r\n"
        "CACHE-CONTROL: max-age=1800\r\n"
        "LOCATION: http://192.168.1.42:7676/smp_15_\r\n"
        "SERVER: Linux/4.1 UPnP/1.0 Samsung/1.0\r\n"
        "ST: urn:dial-multiscreen-org:service:dial:1\r\n\r\n"
    )

    def test_headers_are_lowercased(self):
        headers = discovery.parse_response(self.RESPONSE)
        self.assertEqual(headers["location"], "http://192.168.1.42:7676/smp_15_")
        self.assertEqual(headers["st"], "urn:dial-multiscreen-org:service:dial:1")
        self.assertIn("Samsung", headers["server"])

    def test_values_with_colons_survive(self):
        headers = discovery.parse_response(self.RESPONSE)
        self.assertTrue(headers["location"].startswith("http://"))

    def test_garbage_is_not_fatal(self):
        self.assertEqual(discovery.parse_response("HTTP/1.1 200 OK\r\nnonsense\r\n"), {})


if __name__ == "__main__":
    unittest.main()
