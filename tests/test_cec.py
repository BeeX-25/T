import unittest

from smarttv.backends import cec


class ParsePowerStatusTests(unittest.TestCase):
    def test_states(self):
        self.assertEqual(cec.parse_power_status("power status: on"), "on")
        self.assertEqual(cec.parse_power_status("power status: standby"), "standby")
        self.assertEqual(
            cec.parse_power_status("power status: in transition from standby to on"),
            "transition",
        )

    def test_ignores_surrounding_noise(self):
        output = "DEBUG: [123] opening\nTRAFFIC: [456] >> 10:8f\npower status: standby\n"
        self.assertEqual(cec.parse_power_status(output), "standby")

    def test_missing_or_odd_output(self):
        self.assertEqual(cec.parse_power_status(""), "unknown")
        self.assertEqual(cec.parse_power_status(None), "unknown")
        self.assertEqual(cec.parse_power_status("power status: banana"), "unknown")


class ParseAdaptersTests(unittest.TestCase):
    def test_reads_com_port_lines(self):
        output = "Found devices: 1\n\ndevice:  1\ncom port:  /dev/ttyACM0\nvendor id: 2708\n"
        self.assertEqual(cec.parse_adapters(output), ["/dev/ttyACM0"])

    def test_no_adapters(self):
        self.assertEqual(cec.parse_adapters("Found devices: NONE"), [])


class FrameTests(unittest.TestCase):
    def test_press_and_release_frames(self):
        self.assertEqual(
            cec.build_key_frames(4, 0, 0x01), ["tx 40:44:01", "tx 40:45"]
        )

    def test_addresses_are_single_nibbles(self):
        frames = cec.build_key_frames(0xB, 0, 0x0D)
        self.assertEqual(frames[0], "tx B0:44:0D")


class ArgvTests(unittest.TestCase):
    def test_osd_name_is_truncated_to_the_cec_limit(self):
        backend = cec.CECBackend({"osd_name": "a-very-long-osd-name"})
        argv = backend._argv()
        self.assertEqual(len(argv[argv.index("-o") + 1]), 13)

    def test_adapter_is_passed_last(self):
        backend = cec.CECBackend({"adapter": "/dev/ttyACM0"})
        self.assertEqual(backend._argv()[-1], "/dev/ttyACM0")

    def test_extra_args_precede_the_adapter(self):
        backend = cec.CECBackend({"adapter": "/dev/ttyACM0"})
        argv = backend._argv(["-l"])
        self.assertLess(argv.index("-l"), argv.index("/dev/ttyACM0"))


if __name__ == "__main__":
    unittest.main()
