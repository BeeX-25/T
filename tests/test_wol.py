import unittest

from smarttv import wol


class MagicPacketTests(unittest.TestCase):
    def test_layout(self):
        packet = wol.build_packet("AA:BB:CC:DD:EE:FF")
        self.assertEqual(len(packet), 102)
        self.assertEqual(packet[:6], b"\xff" * 6)
        self.assertEqual(packet[6:12], b"\xaa\xbb\xcc\xdd\xee\xff")

    def test_separator_styles(self):
        self.assertEqual(
            wol.build_packet("aabbccddeeff"), wol.build_packet("aa-bb-cc-dd-ee-ff")
        )

    def test_invalid_mac(self):
        for bad in ("", "not-a-mac", "AA:BB:CC:DD:EE"):
            with self.assertRaises(ValueError):
                wol.build_packet(bad)


if __name__ == "__main__":
    unittest.main()
