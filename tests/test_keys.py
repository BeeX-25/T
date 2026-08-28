import unittest

from smarttv import keys


class NormalizeTests(unittest.TestCase):
    def test_aliases_and_case(self):
        self.assertEqual(keys.normalize("OK"), "select")
        self.assertEqual(keys.normalize(" vol+ "), "volume_up")
        self.assertEqual(keys.normalize("Fast-Forward"), "fast_forward")

    def test_unknown_key_returns_none(self):
        self.assertIsNone(keys.normalize("eject"))
        self.assertIsNone(keys.normalize(""))
        self.assertIsNone(keys.normalize(None))

    def test_every_cec_code_is_a_byte(self):
        for name, code in keys.CEC_CODES.items():
            self.assertTrue(0 <= code <= 0xFF, name)

    def test_backend_maps_use_canonical_names(self):
        for mapping in (keys.SAMSUNG_KEYS, keys.WEBOS_KEYS):
            for name in mapping:
                self.assertEqual(keys.normalize(name), name)


if __name__ == "__main__":
    unittest.main()
