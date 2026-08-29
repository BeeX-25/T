import unittest

from smarttv import ircodes, irimport

IRDB = (
    "functionname,protocol,device,subdevice,function\n"
    "KEY_POWER,NEC1,7,-1,2\n"
    "KEY_VOLUMEUP,NEC1,7,-1,7\n"
    "KEY_1,NEC1,7,-1,4\n"
)

LIRC = """
# captured from the original remote
begin remote
  name  MAGIC555
  bits           16
  flags SPACE_ENC|CONST_LENGTH
  header       9024  4468
  one           573  1668
  zero          573   551
  ptrail        574
  pre_data_bits   16
  pre_data       0x807F
  gap          108000
  frequency    38000
      begin codes
          KEY_POWER    0x12ED
          KEY_VOLUMEUP 0xA857
          KEY_OK       0xC23D
      end codes
end remote
"""

LIRC_RAW = """
begin remote
  name RAWBOX
  flags RAW_CODES
  frequency 36000
    begin raw_codes
      name KEY_POWER
        9000 4500 560 1690
        560 560
      name KEY_MENU
        9000 4500 560 560
    end raw_codes
end remote
"""


class NameTests(unittest.TestCase):
    def test_lirc_names_map_to_canonical_buttons(self):
        self.assertEqual(irimport.normalize_key("KEY_VOLUMEUP"), "volume_up")
        self.assertEqual(irimport.normalize_key("KEY_OK"), "select")
        self.assertEqual(irimport.normalize_key("KEY_CHANNELDOWN"), "channel_down")
        self.assertEqual(irimport.normalize_key("KEY_1"), "num1")

    def test_unknown_buttons_are_dropped_not_guessed(self):
        self.assertIsNone(irimport.normalize_key("KEY_ZOOM"))
        self.assertIsNone(irimport.normalize_key(""))


class IrdbTests(unittest.TestCase):
    def test_protocol_and_address_are_shared_by_the_file(self):
        table = irimport.parse_irdb_csv(IRDB, "magic")
        self.assertEqual(table["protocol"], "nec")
        self.assertEqual(table["address"], 7)
        self.assertEqual(table["keys"], {"power": 2, "volume_up": 7, "num1": 4})

    def test_hex_values_are_accepted(self):
        table = irimport.parse_irdb_csv(
            "functionname,protocol,device,subdevice,function\nKEY_POWER,NEC1,0x07,-1,0x02\n"
        )
        self.assertEqual(table["keys"]["power"], 2)

    def test_rows_with_another_address_are_skipped_not_mixed(self):
        table = irimport.parse_irdb_csv(IRDB + "KEY_MENU,NEC1,9,-1,3\n")
        self.assertNotIn("menu", table["keys"])
        self.assertIn("KEY_MENU", table["skipped"])

    def test_unsupported_protocol_is_rejected(self):
        with self.assertRaises(ValueError):
            irimport.parse_irdb_csv(
                "functionname,protocol,device,subdevice,function\nKEY_POWER,Blaupunkt,1,-1,2\n"
            )

    def test_imported_table_drives_the_encoders(self):
        table = irimport.parse_irdb_csv(IRDB, "magic")
        frequency, pattern = ircodes.pattern_for(
            "magic", "power", brands={"magic": table}
        )
        self.assertEqual(frequency, 38000)
        self.assertEqual(pattern, ircodes.encode_nec(7, 2))


class LircTests(unittest.TestCase):
    def test_space_encoded_remote_becomes_raw_patterns(self):
        table = irimport.parse_lircd_conf(LIRC)
        self.assertEqual(table["protocol"], "raw")
        self.assertEqual(table["name"], "MAGIC555")
        self.assertEqual(sorted(table["keys"]), ["power", "select", "volume_up"])

    def test_pattern_matches_the_declared_timing(self):
        pattern = irimport.parse_lircd_conf(LIRC)["keys"]["power"]
        # header + (pre_data 16 + code 16) bits as pairs + trailer
        self.assertEqual(len(pattern), 2 + 32 * 2 + 1)
        self.assertEqual(pattern[:2], [9024, 4468])
        self.assertEqual(pattern[-1], 574)
        # pre_data 0x807F is MSB first: 1, then six zeros.
        self.assertEqual(pattern[2:4], [573, 1668])
        self.assertEqual(pattern[4:6], [573, 551])

    def test_raw_code_sections_are_read_verbatim(self):
        table = irimport.parse_lircd_conf(LIRC_RAW)
        self.assertEqual(table["frequency"], 36000)
        self.assertEqual(table["keys"]["power"], [9000, 4500, 560, 1690, 560, 560])
        self.assertEqual(table["keys"]["menu"], [9000, 4500, 560, 560])

    def test_a_file_that_is_not_lirc_is_rejected(self):
        with self.assertRaises(ValueError):
            irimport.parse_lircd_conf("just some text")

    def test_a_remote_with_no_buttons_is_rejected(self):
        with self.assertRaises(ValueError):
            irimport.parse_lircd_conf("begin remote\n  name X\nend remote\n")

    def test_imported_patterns_reach_the_transmitter(self):
        table = irimport.parse_lircd_conf(LIRC)
        frequency, pattern = ircodes.pattern_for(
            "magic555", "select", brands={"magic555": table}
        )
        self.assertEqual(frequency, 38000)
        self.assertEqual(pattern, table["keys"]["select"])


class DispatchTests(unittest.TestCase):
    def test_format_is_detected(self):
        self.assertEqual(irimport.load(LIRC)["protocol"], "raw")
        self.assertEqual(irimport.load(IRDB)["protocol"], "nec")


class CandidateTests(unittest.TestCase):
    def test_candidates_cover_the_named_brands_and_an_address_sweep(self):
        found = ircodes.candidates()
        labels = {entry["id"] for entry in found}
        self.assertIn("samsung", labels)
        self.assertIn("generic_nec@5", labels)

    def test_every_candidate_can_produce_a_power_pattern(self):
        for candidate in ircodes.candidates():
            frequency, pattern = ircodes.pattern_for(
                candidate["brand"], "power", address=candidate["address"]
            )
            self.assertTrue(pattern, candidate["id"])
            self.assertGreater(frequency, 30000)


if __name__ == "__main__":
    unittest.main()
