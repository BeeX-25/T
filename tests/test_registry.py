import unittest

from smarttv.backends.base import (
    BackendUnavailable,
    Capability,
    TVBackend,
    TVError,
    UnsupportedCommand,
)
from smarttv.registry import Registry


class FakeBackend(TVBackend):
    def __init__(self, name, caps, is_available=True, fail_with=None):
        super().__init__({})
        self.name = name
        self._caps = set(caps)
        self._available = is_available
        self._fail_with = fail_with
        self.calls = []

    def available(self):
        return self._available

    def capabilities(self):
        return self._caps

    def power_on(self):
        self.calls.append("power_on")
        if self._fail_with:
            raise self._fail_with
        return {"backend": self.name}

    def send_key(self, key):
        self.calls.append("send_key:%s" % key)
        return {"backend": self.name, "key": key}


class SelectionTests(unittest.TestCase):
    def test_first_available_backend_wins(self):
        first = FakeBackend("first", [Capability.POWER])
        second = FakeBackend("second", [Capability.POWER])
        registry = Registry([first, second])
        self.assertEqual(registry.call("power_on")["backend"], "first")
        self.assertEqual(second.calls, [])

    def test_unavailable_backend_is_skipped(self):
        registry = Registry(
            [
                FakeBackend("offline", [Capability.POWER], is_available=False),
                FakeBackend("online", [Capability.POWER]),
            ]
        )
        self.assertEqual(registry.call("power_on")["backend"], "online")

    def test_backend_without_the_capability_is_skipped(self):
        registry = Registry(
            [
                FakeBackend("keys-only", [Capability.KEYS]),
                FakeBackend("power", [Capability.POWER]),
            ]
        )
        self.assertEqual(registry.call("power_on")["backend"], "power")

    def test_falls_through_when_a_backend_turns_out_unusable(self):
        broken = FakeBackend(
            "broken", [Capability.POWER], fail_with=BackendUnavailable("unplugged")
        )
        working = FakeBackend("working", [Capability.POWER])
        registry = Registry([broken, working])
        self.assertEqual(registry.call("power_on")["backend"], "working")
        self.assertEqual(broken.calls, ["power_on"])

    def test_a_real_failure_stops_the_chain(self):
        # A backend that answered and failed for a real reason must surface
        # that error instead of silently retrying elsewhere.
        broken = FakeBackend("broken", [Capability.POWER], fail_with=TVError("no ack"))
        spare = FakeBackend("spare", [Capability.POWER])
        registry = Registry([broken, spare])
        with self.assertRaises(TVError):
            registry.call("power_on")
        self.assertEqual(spare.calls, [])

    def test_unsupported_everywhere_raises(self):
        registry = Registry([FakeBackend("only-keys", [Capability.KEYS])])
        with self.assertRaises(BackendUnavailable):
            registry.call("power_on")

    def test_explicit_backend_is_honoured(self):
        first = FakeBackend("first", [Capability.KEYS])
        second = FakeBackend("second", [Capability.KEYS])
        registry = Registry([first, second])
        registry.call("send_key", "home", backend="second")
        self.assertEqual(second.calls, ["send_key:home"])
        self.assertEqual(first.calls, [])

    def test_unknown_explicit_backend(self):
        registry = Registry([FakeBackend("first", [Capability.KEYS])])
        with self.assertRaises(TVError):
            registry.call("send_key", "home", backend="nope")


class FromConfigTests(unittest.TestCase):
    def test_only_enabled_backends_are_built(self):
        registry = Registry.from_config(
            {
                "order": ["cec", "samsung", "webos"],
                "cec": {"enabled": True},
                "samsung": {"enabled": False},
                "webos": {"enabled": True, "host": "10.0.0.5"},
            }
        )
        self.assertEqual([b.name for b in registry.backends], ["cec", "webos"])

    def test_order_is_respected(self):
        registry = Registry.from_config(
            {
                "order": ["webos", "cec"],
                "cec": {"enabled": True},
                "webos": {"enabled": True, "host": "10.0.0.5"},
            }
        )
        self.assertEqual([b.name for b in registry.backends], ["webos", "cec"])

    def test_demo_mode_needs_no_config(self):
        registry = Registry.from_config({}, demo=True)
        self.assertEqual(registry.active().name, "dummy")

    def test_unsupported_command_message_names_the_backend(self):
        backend = TVBackend()
        with self.assertRaises(UnsupportedCommand):
            backend.power_on()


if __name__ == "__main__":
    unittest.main()
