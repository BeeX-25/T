"""Backend contract shared by the CEC, Samsung and webOS drivers."""

from __future__ import annotations


class TVError(Exception):
    """Any failure while talking to the TV."""


class BackendUnavailable(TVError):
    """The backend cannot be used right now (missing tool, no adapter...)."""


class UnsupportedCommand(TVError):
    """The backend is fine, it just cannot do this particular thing."""


class Capability:
    POWER = "power"
    POWER_STATUS = "power_status"
    VOLUME = "volume"
    KEYS = "keys"
    SOURCE = "source"
    APPS = "apps"
    NOTIFY = "notify"
    RAW = "raw"


class TVBackend:
    """Base class: every command is unsupported until a driver implements it."""

    name = "base"

    def __init__(self, settings=None):
        self.settings = settings or {}

    # -- introspection ----------------------------------------------------
    def available(self):
        """True when this backend can be used on this machine right now."""
        return False

    def capabilities(self):
        return set()

    def supports(self, capability):
        return capability in self.capabilities()

    def info(self):
        return {
            "name": self.name,
            "available": self.available(),
            "capabilities": sorted(self.capabilities()),
        }

    # -- commands ---------------------------------------------------------
    def power_on(self):
        raise UnsupportedCommand("%s cannot power on" % self.name)

    def power_off(self):
        raise UnsupportedCommand("%s cannot power off" % self.name)

    def power_status(self):
        """Return 'on', 'standby', 'transition' or 'unknown'."""
        raise UnsupportedCommand("%s cannot read power status" % self.name)

    def volume(self, action, value=None):
        """action is one of up / down / mute / set."""
        raise UnsupportedCommand("%s cannot change volume" % self.name)

    def send_key(self, key):
        raise UnsupportedCommand("%s cannot send keys" % self.name)

    def set_source(self, index):
        """Switch the TV to HDMI input ``index`` (1-based)."""
        raise UnsupportedCommand("%s cannot switch source" % self.name)

    def launch_app(self, app):
        raise UnsupportedCommand("%s cannot launch apps" % self.name)

    def notify(self, message):
        raise UnsupportedCommand("%s cannot show notifications" % self.name)

    def raw(self, command):
        raise UnsupportedCommand("%s has no raw channel" % self.name)
