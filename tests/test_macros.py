import unittest

from smarttv.macros import MacroError, MacroRunner, digits, parse_steps


class DigitTests(unittest.TestCase):
    def test_number_becomes_key_presses(self):
        self.assertEqual(digits(105), ["key:num1", "key:num0", "key:num5"])

    def test_confirm_key_is_appended(self):
        self.assertEqual(digits(7, "select")[-1], "key:select")

    def test_non_numeric_channel(self):
        for bad in ("", "12a", "-3"):
            with self.assertRaises(MacroError, msg=bad):
                digits(bad)


class ParseTests(unittest.TestCase):
    def test_bare_words_are_buttons(self):
        self.assertEqual(parse_steps(["up", "select"]), [("key", "up"), ("key", "select")])

    def test_named_actions_stay_actions(self):
        self.assertEqual(parse_steps(["power_on"]), [("power_on", "")])

    def test_waits_are_seconds(self):
        self.assertEqual(parse_steps(["wait:1.5"]), [("wait", 1.5)])

    def test_digits_expand_in_place(self):
        self.assertEqual(
            parse_steps(["digits:12", "select"]),
            [("key", "num1"), ("key", "num2"), ("key", "select")],
        )

    def test_a_comma_string_is_a_macro_too(self):
        self.assertEqual(parse_steps("up,down"), [("key", "up"), ("key", "down")])

    def test_bad_input(self):
        for bad in ([], "", ["wait:soon"], [42], {"a": 1}):
            with self.assertRaises(MacroError, msg=repr(bad)):
                parse_steps(bad)


class RunnerTests(unittest.TestCase):
    def setUp(self):
        self.log = []
        self.slept = []
        self.runner = MacroRunner(
            {
                "key": lambda name: self.log.append("key:%s" % name),
                "power_on": lambda: self.log.append("power_on"),
                "cast": lambda url: self.log.append("cast:%s" % url),
            },
            default_delay=0.2,
            sleeper=self.slept.append,
        )

    def test_steps_run_in_order(self):
        self.runner.run(["power_on", "digits:15"])
        self.assertEqual(self.log, ["power_on", "key:num1", "key:num5"])

    def test_a_pause_separates_presses_but_not_the_last_one(self):
        self.runner.run(["up", "down", "select"])
        self.assertEqual(self.slept, [0.2, 0.2])

    def test_explicit_waits_are_honoured(self):
        self.runner.run(["power_on", "wait:2", "up"], delay=0)
        self.assertEqual(self.slept, [2.0])

    def test_delay_can_be_overridden_per_run(self):
        self.runner.run(["up", "down"], delay=1)
        self.assertEqual(self.slept, [1.0])

    def test_result_never_claims_confirmation(self):
        result = self.runner.run(["up"])
        self.assertFalse(result["confirmed"])
        self.assertEqual(result["sent"], ["key:up"])

    def test_unknown_action_is_reported(self):
        with self.assertRaises(MacroError):
            self.runner.run(["record_to_disk:x"])

    def test_a_failing_action_stops_the_macro(self):
        def explode(_name):
            raise RuntimeError("no signal")

        runner = MacroRunner({"key": explode}, sleeper=self.slept.append)
        with self.assertRaises(RuntimeError):
            runner.run(["up", "down"])


if __name__ == "__main__":
    unittest.main()
