"""In-memory backend used by ``--demo`` and by the tests.

It makes the whole service runnable (and the UI clickable) on a laptop with
no TV attached, which is how you develop this without standing in front of
the television.
"""

from __future__ import annotations

from .. import keys as keymap
from .base import Capability, TVBackend, TVError


class DummyBackend(TVBackend):
    name = "dummy"

    def __init__(self, settings=None):
        super().__init__(settings)
        self.state = "standby"
        self.volume_level = 15
        self.muted = False
        self.source = 1
        self.log = []

    def available(self):
        return True

    def capabilities(self):
        return {
            Capability.POWER,
            Capability.POWER_STATUS,
            Capability.VOLUME,
            Capability.KEYS,
            Capability.SOURCE,
            Capability.NOTIFY,
        }

    def power_on(self):
        self.state = "on"
        self.log.append("power_on")
        return {"backend": self.name, "state": self.state}

    def power_off(self):
        self.state = "standby"
        self.log.append("power_off")
        return {"backend": self.name, "state": self.state}

    def power_status(self):
        return self.state

    def volume(self, action, value=None):
        if action == "up":
            self.volume_level = min(100, self.volume_level + 1)
        elif action == "down":
            self.volume_level = max(0, self.volume_level - 1)
        elif action == "mute":
            self.muted = not self.muted
        elif action == "set":
            self.volume_level = max(0, min(100, int(value)))
        else:
            raise TVError("unknown volume action: %r" % (action,))
        self.log.append("volume:%s" % action)
        return {"backend": self.name, "level": self.volume_level, "muted": self.muted}

    def send_key(self, key):
        canonical = keymap.normalize(key)
        if not canonical:
            raise TVError("unknown key: %r" % (key,))
        self.log.append("key:%s" % canonical)
        return {"backend": self.name, "key": canonical}

    def set_source(self, index):
        self.source = int(index)
        self.log.append("source:%d" % self.source)
        return {"backend": self.name, "source": self.source}

    def notify(self, message):
        self.log.append("notify:%s" % message)
        return {"backend": self.name, "message": message}
