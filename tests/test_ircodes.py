import unittest

from smarttv import ircodes


class NecTests(unittest.TestCase):
    def test_frame_shape(self):
        pattern = ircodes.encode_nec(0x04, 0x08)
        # header + 32 bits as mark/space pairs + trailing mark
        self.assertEqual(len(pattern), 2 + 64 + 1)
        self.assertEqual(pattern[:2], [9000, 4500])
        self.assertEqual(pattern[-1], 560)

    def test_bits_are_lsb_first_with_inverted_bytes(self):
        pattern = ircodes.encode_nec(0x00, 0x00)
        spaces = pattern[3:-1:2]
        # address 0x00 then its inverse 0xFF: eight zeros, then eight ones.
        self.assertEqual(spaces[:8], [560] * 8)
        self.assertEqual(spaces[8:16], [1690] * 8)

    def test_only_the_low_byte_is_used(self):
        self.assertEqual(ircodes.encode_nec(0x104, 0x08), ircodes.encode_nec(0x04, 0x08))


class SamsungTests(unittest.TestCase):
    def test_header_and_repeated_address(self):
        pattern = ircodes.encode_samsung(0x07, 0x02)
        self.assertEqual(pattern[:2], [4500, 4500])
        spaces = pattern[3:-1:2]
        self.assertEqual(spaces[:8], spaces[8:16])


class SircTests(unittest.TestCase):
    def test_twelve_bit_frame(self):
        pattern = ircodes.encode_sirc(0x01, 0x15)
        self.assertEqual(pattern[:2], [2400, 600])
        self.assertEqual(len(pattern), 2 + 12 * 2)

    def test_marks_carry_the_bits(self):
        pattern = ircodes.encode_sirc(0x00, 0x01)
        marks = pattern[2::2]
        self.assertEqual(marks[0], 1200)  # first command bit is 1
        self.assertEqual(marks[1], 600)


class Rc5Tests(unittest.TestCase):
    def test_durations_are_multiples_of_the_half_bit(self):
        pattern = ircodes.encode_rc5(0x00, 0x0C)
        for duration in pattern:
            self.assertEqual(duration % 889, 0)

    def test_total_length_is_fourteen_bits_minus_the_dropped_half(self):
        pattern = ircodes.encode_rc5(0x00, 0x0C)
        self.assertEqual(sum(pattern), 14 * 2 * 889 - 889)


class BrandTableTests(unittest.TestCase):
    def test_every_brand_resolves_the_core_buttons(self):
        for brand in ircodes.BRANDS:
            for key in ("power", "volume_up", "volume_down", "up", "down", "select"):
                frequency, pattern = ircodes.pattern_for(brand, key)
                self.assertGreater(frequency, 30000, brand)
                self.assertTrue(pattern, brand)

    def test_unknown_brand_and_key(self):
        with self.assertRaises(KeyError):
            ircodes.pattern_for("nokia", "power")
        with self.assertRaises(KeyError):
            ircodes.pattern_for("lg", "eject")

    def test_custom_brand_from_config(self):
        brands = {"mine": {"protocol": "nec", "address": 0x20, "keys": {"power": 0x01}}}
        frequency, pattern = ircodes.pattern_for("mine", "power", brands=brands)
        self.assertEqual(frequency, 38000)
        self.assertEqual(pattern, ircodes.encode_nec(0x20, 0x01))

    def test_address_override(self):
        _, pattern = ircodes.pattern_for("lg", "power", address=0x06)
        self.assertEqual(pattern, ircodes.encode_nec(0x06, 0x08))


class IRBackendTests(unittest.TestCase):
    def setUp(self):
        from smarttv.backends.ir import IRBackend

        self.backend = IRBackend({"brand": "samsung", "command": "irsend SEND_ONCE tv {key}"})

    def test_command_template_is_filled_in(self):
        argv = self.backend._argv(38000, [9000, 4500], "power")
        self.assertEqual(argv, ["irsend", "SEND_ONCE", "tv", "power"])

    def test_termux_argv_is_a_comma_list(self):
        from smarttv.backends.ir import IRBackend

        backend = IRBackend({"brand": "lg"})
        argv = backend._argv(38000, [9000, 4500, 560], "power")
        self.assertEqual(argv[0], "termux-infrared-transmit")
        self.assertEqual(argv[-1], "9000,4500,560")

    def test_a_template_makes_the_backend_available(self):
        self.assertTrue(self.backend.available())

    def test_unknown_brand_is_never_available(self):
        from smarttv.backends.ir import IRBackend

        self.assertFalse(IRBackend({"brand": "nokia", "command": "x {key}"}).available())

    def test_http_transport_posts_the_pattern_to_a_bridge(self):
        import threading
        from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
        from smarttv.backends.ir import IRBackend

        seen = []

        class Bridge(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def do_GET(self):
                seen.append(self.path)
                self.send_response(200)
                self.send_header("Content-Length", "2")
                self.end_headers()
                self.wfile.write(b"ok")

        server = ThreadingHTTPServer(("127.0.0.1", 0), Bridge)
        thread = threading.Thread(
            target=server.serve_forever, kwargs={"poll_interval": 0.05}, daemon=True
        )
        thread.start()
        self.addCleanup(thread.join, 3)
        self.addCleanup(server.server_close)
        self.addCleanup(server.shutdown)

        host, port = server.server_address
        backend = IRBackend(
            {
                "brand": "lg",
                "url": "http://%s:%d/ir?freq={frequency}&pattern={pattern}" % (host, port),
            }
        )
        self.assertTrue(backend.available())
        result = backend.send_key("power")
        self.assertEqual(result["via"], "http")
        self.assertIn("freq=38000", seen[0])
        self.assertIn("pattern=9000,4500", seen[0])

    def test_an_unreachable_bridge_is_unavailable_not_broken(self):
        from smarttv.backends.base import BackendUnavailable
        from smarttv.backends.ir import IRBackend

        backend = IRBackend(
            {"brand": "lg", "url": "http://127.0.0.1:1/ir?p={pattern}", "timeout": 1}
        )
        with self.assertRaises(BackendUnavailable):
            backend.send_key("power")

    def test_infrared_reports_no_power_status(self):
        from smarttv.backends.base import Capability

        self.assertNotIn(Capability.POWER_STATUS, self.backend.capabilities())


if __name__ == "__main__":
    unittest.main()
