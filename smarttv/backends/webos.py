"""LG webOS backend over the local SSAP websocket.

Optional: it needs ``pip install pywebostv``.  Imported lazily for the same
reason as the Samsung driver.  The first connection asks the TV for a
pairing key (a prompt shows up on screen); the key is cached on disk so it
only happens once.
"""

from __future__ import annotations

import json
import os

from .. import keys as keymap
from .. import wol
from .base import BackendUnavailable, Capability, TVBackend, TVError


class WebOSBackend(TVBackend):
    name = "webos"

    def __init__(self, settings=None):
        super().__init__(settings)
        self.host = self.settings.get("host", "")
        self.key_file = self.settings.get("key_file", "")
        self.mac = self.settings.get("mac", "")
        self._client = None
        self._controls = {}

    # -- plumbing ---------------------------------------------------------
    def _load_store(self):
        if self.key_file and os.path.exists(self.key_file):
            try:
                with open(self.key_file, "r", encoding="utf-8") as handle:
                    return json.load(handle)
            except (OSError, ValueError):
                return {}
        return {}

    def _save_store(self, store):
        if not self.key_file:
            return
        os.makedirs(os.path.dirname(self.key_file) or ".", exist_ok=True)
        with open(self.key_file, "w", encoding="utf-8") as handle:
            json.dump(store, handle)

    def _connect(self):
        if self._client is not None:
            return self._client
        if not self.host:
            raise BackendUnavailable("webos.host is not configured")
        try:
            from pywebostv.connection import WebOSClient
        except ImportError as exc:  # pragma: no cover - depends on env
            raise BackendUnavailable(
                "pywebostv is not installed (pip install pywebostv)"
            ) from exc
        store = self._load_store()
        client = WebOSClient(self.host)
        try:
            client.connect()
            for _status in client.register(store):
                pass
        except Exception as exc:
            raise TVError("webos: %s" % exc) from exc
        self._save_store(store)
        self._client = client
        self._controls = {}
        return client

    def _control(self, kind):
        if kind in self._controls:
            return self._controls[kind]
        client = self._connect()
        from pywebostv import controls

        factory = {
            "system": controls.SystemControl,
            "media": controls.MediaControl,
            "app": controls.ApplicationControl,
            "input": controls.InputControl,
        }[kind]
        control = factory(client)
        if kind == "input":
            control.connect_input()
        self._controls[kind] = control
        return control

    # -- introspection ----------------------------------------------------
    def available(self):
        if not self.host:
            return False
        try:
            import pywebostv  # noqa: F401
        except ImportError:
            return False
        return True

    def capabilities(self):
        return {
            Capability.POWER,
            Capability.VOLUME,
            Capability.KEYS,
            Capability.APPS,
            Capability.NOTIFY,
        }

    # -- commands ---------------------------------------------------------
    def power_on(self):
        if self.mac:
            wol.send(self.mac)
            return {"backend": self.name, "state": "on", "via": "wol"}
        raise TVError("webos needs a configured mac to power on")

    def power_off(self):
        try:
            self._control("system").power_off()
        except TVError:
            raise
        except Exception as exc:
            self._client = None
            raise TVError("webos: %s" % exc) from exc
        return {"backend": self.name, "state": "standby"}

    def volume(self, action, value=None):
        media = self._control("media")
        try:
            if action == "up":
                media.volume_up()
            elif action == "down":
                media.volume_down()
            elif action == "mute":
                media.mute(True)
            elif action == "set":
                media.set_volume(int(value))
            else:
                raise TVError("unknown volume action: %r" % (action,))
        except TVError:
            raise
        except Exception as exc:
            self._client = None
            raise TVError("webos: %s" % exc) from exc
        return {"backend": self.name, "action": action, "value": value}

    def send_key(self, key):
        canonical = keymap.normalize(key)
        button = keymap.WEBOS_KEYS.get(canonical)
        if not button:
            raise TVError("unknown key: %r" % (key,))
        control = self._control("input")
        try:
            getattr(control, button.lower())()
        except AttributeError:
            raise TVError("webos cannot send %r" % canonical)
        except Exception as exc:
            self._client = None
            raise TVError("webos: %s" % exc) from exc
        return {"backend": self.name, "key": canonical}

    def launch_app(self, app):
        control = self._control("app")
        try:
            if str(app).startswith("http"):
                control.launch({"id": "com.webos.app.browser"}, {"target": app})
            else:
                matches = [a for a in control.list_apps() if app in (a["id"], a["title"])]
                if not matches:
                    raise TVError("app not found on TV: %r" % (app,))
                control.launch(matches[0])
        except TVError:
            raise
        except Exception as exc:
            self._client = None
            raise TVError("webos: %s" % exc) from exc
        return {"backend": self.name, "app": app}

    def notify(self, message):
        try:
            self._control("system").notify(str(message))
        except TVError:
            raise
        except Exception as exc:
            self._client = None
            raise TVError("webos: %s" % exc) from exc
        return {"backend": self.name, "message": message}
