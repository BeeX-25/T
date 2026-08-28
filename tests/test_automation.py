import datetime
import time
import unittest

from smarttv.automation import CronError, Scheduler, cron_matches, parse_cron


class ParseCronTests(unittest.TestCase):
    def test_wildcards(self):
        minutes, hours, days, months, weekdays = parse_cron("* * * * *")
        self.assertEqual(len(minutes), 60)
        self.assertEqual(len(hours), 24)
        self.assertEqual(len(days), 31)
        self.assertEqual(len(months), 12)
        self.assertEqual(len(weekdays), 7)

    def test_steps_lists_and_ranges(self):
        minutes = parse_cron("0,30 */6 1-3 * *")[0]
        self.assertEqual(minutes, {0, 30})
        self.assertEqual(parse_cron("0 */6 * * *")[1], {0, 6, 12, 18})
        self.assertEqual(parse_cron("0 0 1-3 * *")[2], {1, 2, 3})

    def test_bad_expressions(self):
        for bad in ("* * * *", "60 * * * *", "* 25 * * *", "*/0 * * * *", "a * * * *"):
            with self.assertRaises((CronError, ValueError), msg=bad):
                parse_cron(bad)


class CronMatchTests(unittest.TestCase):
    def test_exact_time(self):
        parsed = parse_cron("30 2 * * *")
        self.assertTrue(cron_matches(parsed, datetime.datetime(2026, 8, 28, 2, 30)))
        self.assertFalse(cron_matches(parsed, datetime.datetime(2026, 8, 28, 2, 31)))

    def test_weekday_sunday_is_zero(self):
        parsed = parse_cron("0 8 * * 0")
        self.assertTrue(cron_matches(parsed, datetime.datetime(2026, 8, 30, 8, 0)))
        self.assertFalse(cron_matches(parsed, datetime.datetime(2026, 8, 31, 8, 0)))

    def test_day_and_weekday_are_or_ed(self):
        parsed = parse_cron("0 0 1 * 5")
        self.assertTrue(cron_matches(parsed, datetime.datetime(2026, 9, 1, 0, 0)))
        self.assertTrue(cron_matches(parsed, datetime.datetime(2026, 9, 4, 0, 0)))
        self.assertFalse(cron_matches(parsed, datetime.datetime(2026, 9, 2, 0, 0)))

    def test_accepts_struct_time(self):
        parsed = parse_cron("0 3 * * *")
        moment = time.struct_time((2026, 8, 28, 3, 0, 0, 4, 240, 0))
        self.assertTrue(cron_matches(parsed, moment))


class SchedulerTests(unittest.TestCase):
    def setUp(self):
        self.fired = []
        self.scheduler = Scheduler(
            actions={
                "power_off": lambda: self.fired.append("power_off"),
                "key": lambda name="home": self.fired.append("key:%s" % name),
                "boom": lambda: (_ for _ in ()).throw(RuntimeError("bad rule")),
            }
        )

    def _at(self, hour, minute, day=28):
        return time.struct_time((2026, 8, day, hour, minute, 0, 4, 240, 0))

    def test_rule_fires_once_per_minute(self):
        self.scheduler.add_rule({"cron": "0 2 * * *", "action": "power_off"})
        self.assertEqual(self.scheduler.poll(self._at(2, 0)), ["power_off"])
        self.assertEqual(self.scheduler.poll(self._at(2, 0)), [])
        self.assertEqual(self.fired, ["power_off"])

    def test_rule_with_argument(self):
        self.scheduler.add_rule({"cron": "0 7 * * *", "action": "key:home"})
        self.scheduler.poll(self._at(7, 0))
        self.assertEqual(self.fired, ["key:home"])

    def test_non_matching_minute_does_nothing(self):
        self.scheduler.add_rule({"cron": "0 2 * * *", "action": "power_off"})
        self.assertEqual(self.scheduler.poll(self._at(3, 0)), [])

    def test_broken_rule_does_not_kill_the_loop(self):
        self.scheduler.add_rule({"cron": "* * * * *", "action": "boom"})
        self.scheduler.add_rule({"cron": "* * * * *", "action": "power_off"})
        self.scheduler.poll(self._at(1, 1))
        self.assertEqual(self.fired, ["power_off"])

    def test_unknown_action_is_ignored(self):
        self.scheduler.add_rule({"cron": "* * * * *", "action": "explode"})
        self.scheduler.poll(self._at(1, 1))
        self.assertEqual(self.fired, [])

    def test_sleep_timer_fires_after_the_deadline(self):
        self.scheduler.set_sleep_timer(1.0 / 6000)  # 10 milliseconds
        self.assertEqual(self.scheduler.poll(self._at(1, 1)), [])
        time.sleep(0.02)
        self.assertEqual(self.scheduler.poll(self._at(1, 2)), ["power_off"])
        self.assertIsNone(self.scheduler.describe()["sleep_timer_seconds"])

    def test_sleep_timer_can_be_cancelled(self):
        self.scheduler.set_sleep_timer(1.0 / 6000)
        self.scheduler.cancel_sleep_timer()
        time.sleep(0.02)
        self.assertEqual(self.scheduler.poll(self._at(1, 3)), [])

    def test_sleep_timer_rejects_zero(self):
        with self.assertRaises(ValueError):
            self.scheduler.set_sleep_timer(0)

    def test_describe_reports_remaining_time(self):
        self.scheduler.set_sleep_timer(45)
        remaining = self.scheduler.describe()["sleep_timer_seconds"]
        self.assertTrue(2600 < remaining <= 2700)


if __name__ == "__main__":
    unittest.main()
