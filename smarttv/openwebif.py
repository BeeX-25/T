"""OpenWebif client - the API every Enigma2 receiver already exposes.

Enigma2 boxes (Vu+, Zgemma, Octagon, Gigablue, Dreambox and the images
built on OpenATV/OpenPLi) run Linux and ship a web interface with a JSON
API on port 80.  That makes a receiver the best target this project has:
it is already attached to the TV, already tuned, and already programmable
- no cable, no adapter, nothing to buy.

Both the control backend and the player driver sit on this one client.
"""

from __future__ import annotations

import base64
import json
import urllib.error
import urllib.parse
import urllib.request

# Enigma2 wraps a plain URL in a service reference; 4097 is the GStreamer
# player, 5002 the ExtEplayer3 one that some images prefer.
STREAM_SERVICE_TYPES = (4097, 5001, 5002, 5003)
DEFAULT_STREAM_PORT = 8001

POWER_STATES = {
    "toggle_standby": 0,
    "deep_standby": 1,
    "reboot": 2,
    "restart_gui": 3,
    "wakeup": 4,
    "standby": 5,
}


class OpenWebifError(Exception):
    pass


def url_service_reference(url, service_type=4097):
    """Wrap a stream URL in the service reference Enigma2 can zap to."""
    quoted = urllib.parse.quote(str(url), safe="")
    return "%d:0:1:0:0:0:0:0:0:0:%s" % (service_type, quoted)


def is_service_reference(value):
    """True for '1:0:19:...' style references rather than a URL."""
    text = str(value or "")
    if "://" in text:
        return False
    parts = text.split(":")
    return len(parts) >= 10 and parts[0].isdigit()


class OpenWebif:
    def __init__(self, settings=None, fetch=None):
        settings = settings or {}
        self.host = settings.get("host", "")
        self.port = int(settings.get("port", 80))
        self.scheme = "https" if settings.get("https") else "http"
        self.username = settings.get("username", "")
        self.password = settings.get("password", "")
        self.timeout = float(settings.get("timeout", 10))
        self.stream_port = int(settings.get("stream_port", DEFAULT_STREAM_PORT))
        self.service_type = int(settings.get("service_type", 4097))
        # Injected in tests; production uses urllib.
        self._fetch = fetch

    # -- plumbing ---------------------------------------------------------
    @property
    def base(self):
        return "%s://%s:%d" % (self.scheme, self.host, self.port)

    def build_url(self, path, params=None):
        query = ("?" + urllib.parse.urlencode(params)) if params else ""
        return "%s/%s%s" % (self.base, str(path).lstrip("/"), query)

    def stream_url(self, service_reference):
        return "%s://%s:%d/%s" % (
            self.scheme,
            self.host,
            self.stream_port,
            service_reference,
        )

    def fetch(self, url):
        if self._fetch is not None:
            return self._fetch(url)
        request = urllib.request.Request(url)
        if self.username or self.password:
            token = base64.b64encode(
                ("%s:%s" % (self.username, self.password)).encode("utf-8")
            ).decode("ascii")
            request.add_header("Authorization", "Basic " + token)
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                return response.read().decode("utf-8", "replace")
        except urllib.error.HTTPError as exc:
            if exc.code in (401, 403):
                raise OpenWebifError(
                    "receiver refused the login (set enigma2.username/password)"
                ) from exc
            raise OpenWebifError("receiver returned HTTP %s" % exc.code) from exc
        except OSError as exc:
            raise OpenWebifError("cannot reach the receiver: %s" % exc) from exc

    def call(self, path, params=None):
        """GET an OpenWebif endpoint and decode its JSON reply."""
        if not self.host:
            raise OpenWebifError("enigma2 host is not configured")
        text = self.fetch(self.build_url(path, params))
        try:
            payload = json.loads(text)
        except ValueError as exc:
            raise OpenWebifError("receiver did not answer with JSON") from exc
        if isinstance(payload, dict) and payload.get("result") is False:
            raise OpenWebifError(payload.get("message") or "receiver rejected the command")
        return payload

    # -- endpoints --------------------------------------------------------
    def status(self):
        return self.call("api/statusinfo")

    def power(self, state):
        if state not in POWER_STATES:
            raise OpenWebifError("unknown power state: %r" % (state,))
        return self.call("api/powerstate", {"newstate": POWER_STATES[state]})

    def in_standby(self):
        value = self.status().get("inStandby")
        if isinstance(value, str):
            return value.strip().lower() in ("true", "1", "yes")
        return bool(value)

    def remote_key(self, code, long_press=False):
        params = {"command": int(code)}
        if long_press:
            params["type"] = "long"
        return self.call("api/remotecontrol", params)

    def set_volume(self, action, value=None):
        commands = {"up": "up", "down": "down", "mute": "mute"}
        if action == "set":
            setting = "set%d" % max(0, min(100, int(value)))
        elif action in commands:
            setting = commands[action]
        else:
            raise OpenWebifError("unknown volume action: %r" % (action,))
        return self.call("api/vol", {"set": setting})

    def zap(self, service_reference):
        return self.call("api/zap", {"sRef": service_reference})

    def play_url(self, url):
        return self.zap(url_service_reference(url, self.service_type))

    def message(self, text, timeout=10, kind=1):
        return self.call(
            "api/message", {"text": text, "type": int(kind), "timeout": int(timeout)}
        )

    def services(self):
        """Every bouquet with its channels, as OpenWebif reports them."""
        return self.call("api/getallservices")

    def epg_now(self, service_reference):
        return self.call("api/epgservicenow", {"sRef": service_reference})
