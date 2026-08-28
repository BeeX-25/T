"""Samsung Tizen backend (2016+ sets) over the local websocket API.

Optional: it needs ``pip install samsungtvws``.  The import is lazy so a
machine that only uses HDMI-CEC never pays for it, and so the rest of the
service keeps running when the library is missing.
"""

from __future__ import annotations

import os

from .. import keys as keymap
from .. import wol
from .base import BackendUnavailable, Capability, TVBackend, TVError


class SamsungBackend(TVBackend):
    name = "samsung"

    def __init__(self, settings=None):
        super().__init__(settings)
        self.host = self.settings.get("host", "")
        self.port = int(self.settings.get("port", 8002))
        self.client_name = self.settings.get("name", "SmartBridge")
        self.token_file = self.settings.get("token_file", "")
        self.mac = self.settings.get("mac", "")
        self._remote = None

    # -- plumbing ---------------------------------------------------------
    def _connect(self):
        if self._remote is not None:
            return self._remote
        if not self.host:
            raise BackendUnavailable("samsung.host is not configured")
        try:
            from samsungtvws import SamsungTVWS
        except ImportError as exc:  # pragma: no cover - depends on env
            raise BackendUnavailable(
                "samsungtvws is not installed (pip install samsungtvws)"
            ) from exc
        if self.token_file:
            os.makedirs(os.path.dirname(self.token_file) or ".", exist_ok=True)
        self._remote = SamsungTVWS(
            host=self.host,
            port=self.port,
            name=self.client_name,
            token_file=self.token_file or None,
        )
        return self._remote

    def _send(self, samsung_key):
        try:
            self._connect().send_key(samsung_key)
        except BackendUnavailable:
            raise
        except Exception as exc:  # the library raises a wide range of errors
            self._remote = None
            raise TVError("samsung: %s" % exc) from exc
        return {"backend": self.name, "key": samsung_key}

    # -- introspection ----------------------------------------------------
    def available(self):
        if not self.host:
            return False
        try:
            import samsungtvws  # noqa: F401
        except ImportError:
            return False
        return True

    def capabilities(self):
        caps = {Capability.POWER, Capability.VOLUME, Capability.KEYS, Capability.APPS}
        return caps

    # -- commands ---------------------------------------------------------
    def power_on(self):
        # A Tizen TV in deep standby drops off the network; only the NIC
        # stays awake, so the way back in is a magic packet.
        if self.mac:
            wol.send(self.mac)
            return {"backend": self.name, "state": "on", "via": "wol"}
        return self._send(keymap.SAMSUNG_KEYS["power"])

    def power_off(self):
        return self._send(keymap.SAMSUNG_KEYS["power"])

    def volume(self, action, value=None):
        mapping = {
            "up": keymap.SAMSUNG_KEYS["volume_up"],
            "down": keymap.SAMSUNG_KEYS["volume_down"],
            "mute": keymap.SAMSUNG_KEYS["mute"],
        }
        if action not in mapping:
            raise TVError("unknown volume action: %r" % (action,))
        return self._send(mapping[action])

    def send_key(self, key):
        canonical = keymap.normalize(key)
        samsung_key = keymap.SAMSUNG_KEYS.get(canonical)
        if not samsung_key:
            raise TVError("unknown key: %r" % (key,))
        return self._send(samsung_key)

    def set_source(self, index):
        return self._send(keymap.SAMSUNG_KEYS["source"])

    def launch_app(self, app):
        remote = self._connect()
        try:
            if str(app).startswith("http"):
                remote.open_browser(app)
            else:
                remote.run_app(app)
        except Exception as exc:
            self._remote = None
            raise TVError("samsung: %s" % exc) from exc
        return {"backend": self.name, "app": app}
