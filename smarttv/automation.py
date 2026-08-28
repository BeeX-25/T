"""Scheduling: a tiny cron plus a sleep timer.

Rules live in the config file ("turn the TV off at 2am", "wake it at 7am"),
and the sleep timer is the button everyone actually uses - start a film,
tap 45 minutes, the TV goes to standby when you fall asleep.
"""

from __future__ import annotations

import threading
import time


class CronError(ValueError):
    pass


FIELD_RANGES = ((0, 59), (0, 23), (1, 31), (1, 12), (0, 6))


def _parse_field(spec, low, high):
    """Expand one cron field ("*/15", "1-5", "0,30") into a set of ints."""
    values = set()
    for part in str(spec).split(","):
        part = part.strip()
        if not part:
            raise CronError("empty cron field")
        step = 1
        if "/" in part:
            part, _, step_text = part.partition("/")
            if not step_text.isdigit() or int(step_text) == 0:
                raise CronError("bad step: %r" % (step_text,))
            step = int(step_text)
        if part in ("*", ""):
            start, end = low, high
        elif "-" in part:
            start_text, _, end_text = part.partition("-")
            start, end = int(start_text), int(end_text)
        else:
            start = end = int(part)
        if start < low or end > high or start > end:
            raise CronError("value out of range: %r" % (part,))
        values.update(range(start, end + 1, step))
    return values


def parse_cron(expression):
    """Parse "m h dom mon dow" into five sets of allowed values."""
    fields = str(expression).split()
    if len(fields) != 5:
        raise CronError("cron needs 5 fields, got %d" % len(fields))
    return [
        _parse_field(field, low, high)
        for field, (low, high) in zip(fields, FIELD_RANGES)
    ]


def cron_matches(parsed, when):
    """True when ``when`` (a struct_time or datetime) fits the schedule."""
    minute = when.minute if hasattr(when, "minute") else when.tm_min
    hour = when.hour if hasattr(when, "hour") else when.tm_hour
    day = when.day if hasattr(when, "day") else when.tm_mday
    month = when.month if hasattr(when, "month") else when.tm_mon
    # Python weekday(): Monday=0.  Cron: Sunday=0.
    if hasattr(when, "weekday"):
        weekday = (when.weekday() + 1) % 7
    else:
        weekday = (when.tm_wday + 1) % 7
    minutes, hours, days, months, weekdays = parsed
    if minute not in minutes or hour not in hours or month not in months:
        return False
    # cron's day-of-month / day-of-week are OR'ed unless both are wildcards.
    day_restricted = days != set(range(1, 32))
    weekday_restricted = weekdays != set(range(0, 7))
    if day_restricted and weekday_restricted:
        return day in days or weekday in weekdays
    if day_restricted:
        return day in days
    if weekday_restricted:
        return weekday in weekdays
    return True


class Scheduler:
    """Background thread running cron rules and the sleep timer."""

    def __init__(self, actions, rules=None, tick=10, logger=None):
        self.actions = actions
        self.tick = tick
        self.logger = logger
        self.rules = []
        self._sleep_deadline = None
        self._sleep_action = "power_off"
        self._stop = threading.Event()
        self._thread = None
        self._last_minute = None
        self._lock = threading.Lock()
        for rule in rules or []:
            self.add_rule(rule)

    # -- rules ------------------------------------------------------------
    def add_rule(self, rule):
        parsed = parse_cron(rule["cron"])
        self.rules.append(
            {
                "name": rule.get("name") or rule["cron"],
                "cron": rule["cron"],
                "action": rule["action"],
                "parsed": parsed,
            }
        )

    def describe(self):
        with self._lock:
            remaining = None
            if self._sleep_deadline is not None:
                remaining = max(0, int(self._sleep_deadline - time.time()))
        return {
            "rules": [
                {"name": r["name"], "cron": r["cron"], "action": r["action"]}
                for r in self.rules
            ],
            "sleep_timer_seconds": remaining,
        }

    # -- sleep timer ------------------------------------------------------
    def set_sleep_timer(self, minutes, action="power_off"):
        minutes = float(minutes)
        if minutes <= 0:
            raise ValueError("sleep timer must be positive")
        with self._lock:
            self._sleep_deadline = time.time() + minutes * 60
            self._sleep_action = action
        return {"sleep_timer_seconds": int(minutes * 60)}

    def cancel_sleep_timer(self):
        with self._lock:
            self._sleep_deadline = None
        return {"sleep_timer_seconds": None}

    # -- loop -------------------------------------------------------------
    def _log(self, message):
        if self.logger:
            self.logger(message)

    def _run_action(self, name):
        action, _, argument = str(name).partition(":")
        handler = self.actions.get(action)
        if handler is None:
            self._log("scheduler: unknown action %r" % (name,))
            return
        try:
            handler(argument) if argument else handler()
        except Exception as exc:  # a broken rule must not kill the thread
            self._log("scheduler: action %r failed: %s" % (name, exc))

    def poll(self, now=None):
        """One scheduler tick.  Exposed so tests can drive it directly."""
        now = now or time.localtime()
        fired = []
        stamp = (now.tm_year, now.tm_yday, now.tm_hour, now.tm_min)
        if stamp != self._last_minute:
            self._last_minute = stamp
            for rule in self.rules:
                if cron_matches(rule["parsed"], now):
                    fired.append(rule["action"])
        with self._lock:
            if self._sleep_deadline is not None and time.time() >= self._sleep_deadline:
                self._sleep_deadline = None
                fired.append(self._sleep_action)
        for action in fired:
            self._log("scheduler: running %s" % action)
            self._run_action(action)
        return fired

    def start(self):
        if self._thread is not None:
            return
        self._last_minute = None
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def _loop(self):
        while not self._stop.wait(self.tick):
            try:
                self.poll()
            except Exception as exc:  # pragma: no cover - defensive
                self._log("scheduler loop error: %s" % exc)

    def shutdown(self):
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=2)
            self._thread = None
