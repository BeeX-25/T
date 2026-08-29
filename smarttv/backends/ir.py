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
import urllib.error
import urllib.parse
import urllib.request

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
        # Three ways to actually emit the pulses:
        #   termux  - the phone's own IR blaster (default)
        #   command - any shell command, e.g. LIRC's irsend
        #   http    - a Wi-Fi IR bridge (an ESP8266 for a couple of dollars),
        #             which is the answer when the phone has no blaster
        # {frequency}, {pattern} and {key} are filled into whichever is used.
        self.command_template = self.settings.get("command", "")
        self.url_template = self.settings.get("url", "")
        self.http_method = str(self.settings.get("method", "GET")).upper()
        self.body_template = self.settings.get("body", "")
        self.transport = str(
            self.settings.get(
                "transport",
                "http" if self.url_template else "command" if self.command_template else "termux",
            )
        ).lower()

    # -- plumbing ---------------------------------------------------------
    def _argv(self, frequency, pattern, key):
        joined = ",".join(str(int(value)) for value in pattern)
        if self.command_template:
            return [
                part.format(frequency=frequency, pattern=joined, key=key)
                for part in self.command_template.split()
            ]
        return [TERMUX_BINARY, "-f", str(int(frequency)), joined]

    def _fill(self, template, frequency, pattern, key):
        return template.format(
            frequency=int(frequency),
            pattern=",".join(str(int(value)) for value in pattern),
            key=key,
        )

    def _send_http(self, frequency, pattern, key):
        url = self._fill(self.url_template, frequency, pattern, key)
        data = None
        if self.body_template:
            data = self._fill(self.body_template, frequency, pattern, key).encode("utf-8")
        request = urllib.request.Request(url, data=data, method=self.http_method)
        if data:
            request.add_header("Content-Type", "application/json")
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                response.read(4096)
        except urllib.error.HTTPError as exc:
            raise TVError("IR bridge returned HTTP %s" % exc.code) from exc
        except OSError as exc:
            raise BackendUnavailable("cannot reach the IR bridge: %s" % exc) from exc
        return {"backend": self.name, "key": key, "brand": self.brand, "via": "http"}

    def _transmit(self, key):
        frequency, pattern = ircodes.pattern_for(
            self.brand, key, brands=self.brands, address=self.address
        )
        return self._send(frequency, pattern, key)

    def _send(self, frequency, pattern, key):
        if self.transport == "http":
            for _ in range(max(1, self.repeat)):
                result = self._send_http(frequency, pattern, key)
            return result
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
        if self.transport == "http":
            return bool(self.url_template)
        if self.transport == "command" or self.command_template:
            return bool(self.command_template)
        return shutil.which(TERMUX_BINARY) is not None

    def capabilities(self):
        # No POWER_STATUS on purpose: infrared cannot read anything back.
        return {Capability.POWER, Capability.VOLUME, Capability.KEYS, Capability.SOURCE}

    def known_keys(self):
        table = self.brands.get(self.brand) or {}
        return sorted(table.get("keys", {}))

    def candidates(self):
        """What to try when the remote's codes are unknown."""
        return ircodes.candidates(self.brands)

    def profile(self):
        return {"brand": self.brand, "address": self.address}

    def register(self, table, name=None):
        """Add an imported code set (from irdb or lircd.conf)."""
        label = str(name or table.get("name") or "imported").lower()
        self.brands[label] = {
            key: value for key, value in table.items() if key != "name"
        }
        return label

    def apply_profile(self, profile):
        """Point this backend at a brand, an address, or an imported table.

        This is what the setup wizard saves: a receiver whose codes were
        found by trial keeps working across restarts without editing the
        config by hand.
        """
        profile = dict(profile or {})
        if profile.get("keys"):
            brand = self.register(profile, profile.get("brand") or profile.get("name"))
        else:
            brand = str(profile.get("brand") or self.brand).lower()
        if brand not in self.brands:
            raise TVError("unknown IR brand: %r" % (brand,))
        self.brand = brand
        if "address" in profile and profile["address"] is not None:
            self.address = int(profile["address"])
        elif profile.get("keys"):
            self.address = None
        return self.profile()

    def test(self, profile, key="power"):
        """Fire one button from a candidate profile without adopting it."""
        canonical = keymap.normalize(key) or key
        brand = str((profile or {}).get("brand") or self.brand).lower()
        address = (profile or {}).get("address")
        table = self.brands.get(brand)
        if table is None:
            raise TVError("unknown IR brand: %r" % (brand,))
        try:
            frequency, pattern = ircodes.pattern_for(
                brand, canonical, brands=self.brands, address=address
            )
        except KeyError as exc:
            raise TVError(str(exc)) from exc
        self._send(frequency, pattern, canonical)
        return {"backend": self.name, "brand": brand, "address": address, "key": canonical}

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
