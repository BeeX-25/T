"""Infrared backend - a phone with an IR blaster *is* the remote.

This is the only backend that needs nothing plugged into the TV at all: if
the phone has an IR LED, Termux can fire the same pulses the original
remote does.  The trade-off is that infrared is one-way, so this backend
can command the TV but can never report its state - which is why it
declares no POWER_STATUS capability and the registry keeps asking CEC for
that when both are configured.
"""

from __future__ import annotations

import shutil
import subprocess

from .. import ircodes, keys as keymap
from .base import BackendUnavailable, Capability, TVBackend, TVError

TERMUX_BINARY = "termux-infrared-transmit"


class IRBackend(TVBackend):
    name = "ir"

    def __init__(self, settings=None):
        super().__init__(settings)
        self.brand = str(self.settings.get("brand", "")).lower()
        self.address = self.settings.get("address")
        self.repeat = int(self.settings.get("repeat", 1))
        self.timeout = float(self.settings.get("timeout", 10))
        # Anything not in the built-in tables: a brand of your own, read off
        # a real remote with an IR receiver or copied from an LIRC config.
        self.brands = dict(ircodes.BRANDS)
        for name, table in (self.settings.get("brands") or {}).items():
            self.brands[str(name).lower()] = table
        # LIRC users (irsend) and anyone with their own transmitter can
        # substitute the command; {frequency}, {pattern} and {key} are filled in.
        self.command_template = self.settings.get("command", "")

    # -- plumbing ---------------------------------------------------------
    def _argv(self, frequency, pattern, key):
        joined = ",".join(str(int(value)) for value in pattern)
        if self.command_template:
            return [
                part.format(frequency=frequency, pattern=joined, key=key)
                for part in self.command_template.split()
            ]
        return [TERMUX_BINARY, "-f", str(int(frequency)), joined]

    def _transmit(self, key):
        frequency, pattern = ircodes.pattern_for(
            self.brand, key, brands=self.brands, address=self.address
        )
        argv = self._argv(frequency, pattern, key)
        if not self.command_template and shutil.which(TERMUX_BINARY) is None:
            raise BackendUnavailable(
                "%s not found (install Termux:API, then: pkg install termux-api)"
                % TERMUX_BINARY
            )
        for _ in range(max(1, self.repeat)):
            try:
                proc = subprocess.run(
                    argv, capture_output=True, text=True, timeout=self.timeout
                )
            except subprocess.TimeoutExpired as exc:
                raise TVError("IR transmit timed out") from exc
            except OSError as exc:
                raise BackendUnavailable(str(exc)) from exc
            if proc.returncode != 0:
                message = (proc.stderr or proc.stdout or "").strip()
                if "no infrared" in message.lower() or "not available" in message.lower():
                    raise BackendUnavailable("this phone has no IR blaster")
                raise TVError("IR transmit failed: %s" % (message or proc.returncode))
        return {"backend": self.name, "key": key, "brand": self.brand}

    # -- introspection ----------------------------------------------------
    def available(self):
        if self.brand not in self.brands:
            return False
        if self.command_template:
            return True
        return shutil.which(TERMUX_BINARY) is not None

    def capabilities(self):
        # No POWER_STATUS on purpose: infrared cannot read anything back.
        return {Capability.POWER, Capability.VOLUME, Capability.KEYS, Capability.SOURCE}

    def known_keys(self):
        table = self.brands.get(self.brand) or {}
        return sorted(table.get("keys", {}))

    # -- commands ---------------------------------------------------------
    def _power(self, discrete):
        table = self.brands.get(self.brand) or {}
        keys = table.get("keys", {})
        # Most remotes only have a toggle; discrete on/off exists on some
        # brands and is worth using because it cannot desynchronise.
        return self._transmit(discrete if discrete in keys else "power")

    def power_on(self):
        return self._power("power_on")

    def power_off(self):
        return self._power("power_off")

    def volume(self, action, value=None):
        mapping = {"up": "volume_up", "down": "volume_down", "mute": "mute"}
        if action not in mapping:
            raise TVError("IR volume takes up, down or mute")
        return self._transmit(mapping[action])

    def send_key(self, key):
        canonical = keymap.normalize(key)
        if not canonical:
            raise TVError("unknown key: %r" % (key,))
        try:
            return self._transmit(canonical)
        except KeyError as exc:
            raise TVError(str(exc)) from exc

    def set_source(self, index):
        # IR has no "go to HDMI 3": the source button cycles inputs.
        return self._transmit("source")
