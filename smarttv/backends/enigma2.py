"""Enigma2 receiver control over OpenWebif.

A receiver is already wired to the TV and already knows every channel, so
this backend gives the phone remote the whole box: standby, volume, every
button of the original remote, and on-screen messages - over HTTP, with no
IR line of sight and nothing plugged in anywhere.
"""

from __future__ import annotations

from .. import keys as keymap
from ..openwebif import OpenWebif, OpenWebifError
from .base import BackendUnavailable, Capability, TVBackend, TVError


class Enigma2Backend(TVBackend):
    name = "enigma2"

    def __init__(self, settings=None, client=None):
        super().__init__(settings)
        self.client = client or OpenWebif(self.settings)
        # Deep standby really powers the box down, but then only its own
        # power button (or WOL) brings it back - not this API.
        self.deep_standby = bool(self.settings.get("deep_standby", False))

    def _call(self, action, *args, **kwargs):
        try:
            return action(*args, **kwargs)
        except OpenWebifError as exc:
            message = str(exc)
            if "not configured" in message or "cannot reach" in message:
                raise BackendUnavailable(message) from exc
            raise TVError(message) from exc

    # -- introspection ----------------------------------------------------
    def available(self):
        return bool(self.client.host)

    def capabilities(self):
        return {
            Capability.POWER,
            Capability.POWER_STATUS,
            Capability.VOLUME,
            Capability.KEYS,
            Capability.NOTIFY,
            Capability.RAW,
        }

    # -- commands ---------------------------------------------------------
    def power_on(self):
        self._call(self.client.power, "wakeup")
        return {"backend": self.name, "state": "on"}

    def power_off(self):
        self._call(self.client.power, "deep_standby" if self.deep_standby else "standby")
        return {"backend": self.name, "state": "standby"}

    def power_status(self):
        return "standby" if self._call(self.client.in_standby) else "on"

    def volume(self, action, value=None):
        self._call(self.client.set_volume, action, value)
        return {"backend": self.name, "action": action, "value": value}

    def send_key(self, key):
        canonical = keymap.normalize(key)
        code = keymap.ENIGMA2_KEYS.get(canonical)
        if code is None:
            raise TVError("the receiver has no button for %r" % (key,))
        self._call(self.client.remote_key, code)
        return {"backend": self.name, "key": canonical}

    def notify(self, message):
        self._call(self.client.message, str(message))
        return {"backend": self.name, "message": message}

    def raw(self, command):
        """Call any OpenWebif endpoint, e.g. ``api/zap?sRef=1:0:19:...``."""
        if not isinstance(command, str) or not command.strip():
            raise TVError("empty raw command")
        path, _, query = command.strip().partition("?")
        params = None
        if query:
            from urllib.parse import parse_qsl

            params = dict(parse_qsl(query))
        return {"backend": self.name, "response": self._call(self.client.call, path, params)}
