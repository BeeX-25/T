"""Key-sequence macros: how you program a device that cannot talk back.

A closed receiver has no API, so "programmable" means one thing only:
reproducing what a human does with the remote - press 1, 0, 5, OK - from
software, reliably and with the right pauses.  That turns an unscriptable
box into something a phone button, a cron rule or another program can
drive.

There is no feedback channel, so this module is honest about being
open-loop: it reports what it sent, never what happened.
"""

from __future__ import annotations

import time

DEFAULT_DELAY = 0.35

# Bare words that mean an action rather than a button, so a macro can read
# as ``["power_on", "wait:2", "digits:105"]``.
BARE_ACTIONS = ("power_on", "power_off", "stop", "toggle")


class MacroError(Exception):
    pass


def digits(number, confirm=None):
    """Turn a channel number into the key presses that dial it."""
    text = str(number).strip()
    if not text.isdigit():
        raise MacroError("channel number must be digits: %r" % (number,))
    steps = ["key:num%s" % character for character in text]
    if confirm:
        steps.append("key:%s" % confirm)
    return steps


def parse_steps(spec):
    """Normalise a macro definition into ``(action, argument)`` pairs.

    Steps are strings so a macro stays readable in a JSON config:
    ``["power_on", "wait:2", "digits:105", "key:select"]``.
    """
    if isinstance(spec, str):
        spec = [part.strip() for part in spec.split(",") if part.strip()]
    if not isinstance(spec, (list, tuple)):
        raise MacroError("a macro is a list of steps")
    steps = []
    for entry in spec:
        if not isinstance(entry, str) or not entry.strip():
            raise MacroError("bad macro step: %r" % (entry,))
        action, _, argument = entry.strip().partition(":")
        action = action.lower()
        if action == "digits":
            steps.extend(parse_steps(digits(argument)))
            continue
        if action == "wait":
            try:
                steps.append(("wait", float(argument)))
            except ValueError:
                raise MacroError("bad wait: %r" % (entry,)) from None
            continue
        if not argument:
            # A bare word is a button ("up" means "key:up") unless it is
            # one of the few named actions.
            steps.append((action, "") if action in BARE_ACTIONS else ("key", action))
            continue
        steps.append((action, argument))
    if not steps:
        raise MacroError("macro has no steps")
    return steps


class MacroRunner:
    """Runs macros against the same action table the scheduler uses."""

    def __init__(self, actions, default_delay=DEFAULT_DELAY, sleeper=None):
        self.actions = actions
        self.default_delay = float(default_delay)
        self.sleep = sleeper or time.sleep

    def run(self, spec, delay=None):
        steps = parse_steps(spec)
        delay = self.default_delay if delay is None else float(delay)
        sent = []
        for index, (action, argument) in enumerate(steps):
            if action == "wait":
                self.sleep(argument)
                sent.append("wait:%s" % argument)
                continue
            handler = self.actions.get(action)
            if handler is None:
                raise MacroError("unknown macro action: %r" % (action,))
            handler(argument) if argument else handler()
            sent.append("%s:%s" % (action, argument) if argument else action)
            # Cheap receivers drop presses that arrive back to back.
            if delay and index < len(steps) - 1:
                self.sleep(delay)
        return {"sent": sent, "steps": len(steps), "confirmed": False}
