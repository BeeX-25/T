"""Playback on an Enigma2 receiver.

The receiver is the media box: zapping it to a wrapped service reference
makes it play any stream URL on its own HDMI output, so no phone needs to
be plugged into the TV at all.  Channels coming from the receiver's own
bouquets are recognised by their stream URL and zapped as live services
instead, which keeps the tuner (and the EPG) doing the work.
"""

from __future__ import annotations

from ..keys import ENIGMA2_KEYS
from ..openwebif import OpenWebif, OpenWebifError, is_service_reference
from .base import Player, PlayerError


class Enigma2Player(Player):
    name = "enigma2"

    def __init__(self, settings=None, client=None):
        settings = settings or {}
        super().__init__(settings)
        self.enabled = bool(settings.get("enabled", True))
        self.client = client or OpenWebif(settings)
        self._current = None

    # -- plumbing ---------------------------------------------------------
    def _call(self, action, *args, **kwargs):
        try:
            return action(*args, **kwargs)
        except OpenWebifError as exc:
            raise PlayerError(str(exc)) from exc

    def _as_service_reference(self, url):
        """Turn our own stream URLs back into the reference they came from."""
        prefix = "%s://%s:%d/" % (self.client.scheme, self.client.host, self.client.stream_port)
        if str(url).startswith(prefix):
            candidate = str(url)[len(prefix):]
            if is_service_reference(candidate):
                return candidate
        if is_service_reference(url):
            return url
        return None

    # -- introspection ----------------------------------------------------
    def available(self):
        return self.enabled and bool(self.client.host)

    def running(self):
        return self._current is not None

    def capabilities(self):
        return {"play", "pause", "stop", "volume", "seek"}

    # -- playback ---------------------------------------------------------
    def play(self, url, append=False, start=None):
        if not url:
            raise PlayerError("no url given")
        reference = self._as_service_reference(url)
        if reference:
            self._call(self.client.zap, reference)
        else:
            # ``start`` is ignored: Enigma2 zaps to the head of a stream.
            self._call(self.client.play_url, url)
        self._current = url
        return {"playing": True, "url": url, "player": self.name, "live": bool(reference)}

    def _key(self, name):
        self._call(self.client.remote_key, ENIGMA2_KEYS[name])

    def pause(self, state=True):
        self._key("pause" if state else "play")
        return {"paused": bool(state)}

    def toggle(self):
        self._key("play_pause")
        return {"paused": None}

    def seek(self, seconds):
        seconds = float(seconds)
        presses = max(1, min(10, int(abs(seconds) // 30) or 1))
        for _ in range(presses):
            self._key("fast_forward" if seconds > 0 else "rewind")
        return {"seek_presses": presses, "approximate": True}

    def set_volume(self, level):
        self._call(self.client.set_volume, "set", level)
        return {"volume": max(0, min(100, int(level)))}

    def stop(self):
        self._key("stop")
        self._current = None
        return {"playing": False}

    def status(self):
        if not self.available():
            return {"available": False, "running": False, "player": self.name}
        try:
            info = self.client.status()
        except OpenWebifError as exc:
            return {
                "available": True,
                "running": False,
                "player": self.name,
                "error": str(exc),
            }
        name = info.get("currservice_name") or ""
        return {
            "available": True,
            "running": bool(name),
            "player": self.name,
            "title": name,
            "programme": info.get("currservice_station") or "",
            "volume": info.get("volume"),
            # A receiver reports EPG timings, not a playback position.
            "position": None,
            "duration": None,
        }
