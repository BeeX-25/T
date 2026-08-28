"""What every player must offer the API layer."""

from __future__ import annotations


class PlayerError(Exception):
    pass


class Player:
    name = "base"

    def __init__(self, settings=None):
        self.settings = settings or {}

    def available(self):
        return False

    def running(self):
        return False

    def capabilities(self):
        """Subset of: play, pause, seek, volume, stop, position."""
        return set()

    def play(self, url, append=False, start=None):
        """Play ``url``; ``start`` is a resume position in seconds."""
        raise PlayerError("%s cannot play" % self.name)

    def pause(self, state=True):
        raise PlayerError("%s cannot pause" % self.name)

    def toggle(self):
        raise PlayerError("%s cannot pause" % self.name)

    def seek(self, seconds):
        raise PlayerError("%s cannot seek" % self.name)

    def set_volume(self, level):
        raise PlayerError("%s cannot set volume" % self.name)

    def stop(self):
        raise PlayerError("%s cannot stop" % self.name)

    def status(self):
        return {"available": self.available(), "running": False, "player": self.name}
