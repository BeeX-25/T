"""HDMI-CEC backend - the zero-extra-hardware path.

Every TV with an HDMI port speaks CEC (vendors brand it Anynet+, Simplink,
Bravia Sync, Viera Link...).  We drive it through ``cec-client`` from the
``cec-utils`` package, which talks to the Raspberry Pi's built-in CEC
adapter or to any USB-CEC adapter, so the only cable needed is the HDMI
cable that is already plugged in.

Commands are issued one-shot (``echo "on 0" | cec-client -s``) rather than
through a long-lived process: it is slower by a fraction of a second but it
survives the TV being unplugged, which a persistent session does not.
"""

from __future__ import annotations

import shutil
import subprocess

from .. import keys as keymap
from .base import BackendUnavailable, Capability, TVBackend, TVError, UnsupportedCommand

POWER_STATES = ("on", "standby", "transition", "unknown")


def parse_power_status(output):
    """Extract the power state from ``cec-client`` output for ``pow 0``."""
    for line in (output or "").splitlines():
        lowered = line.strip().lower()
        if "power status:" not in lowered:
            continue
        value = lowered.split("power status:", 1)[1].strip()
        if value.startswith("in transition"):
            return "transition"
        if value.startswith("standby"):
            return "standby"
        if value.startswith("on"):
            return "on"
        return "unknown"
    return "unknown"


def parse_adapters(output):
    """Return the adapter device paths listed by ``cec-client -l``."""
    adapters = []
    for line in (output or "").splitlines():
        stripped = line.strip()
        for label in ("com port:", "port:"):
            if stripped.lower().startswith(label):
                value = stripped.split(":", 1)[1].strip()
                if value:
                    adapters.append(value)
                break
    return adapters


def build_key_frames(source_address, tv_address, code):
    """Build the press+release raw frames for a CEC user-control code."""
    header = "%X%X" % (source_address & 0xF, tv_address & 0xF)
    return ["tx %s:44:%02X" % (header, code & 0xFF), "tx %s:45" % header]


class CECBackend(TVBackend):
    name = "cec"

    def __init__(self, settings=None):
        super().__init__(settings)
        self.binary = self.settings.get("binary", "cec-client")
        self.adapter = self.settings.get("adapter", "")
        self.device_type = self.settings.get("device_type", "p")
        self.osd_name = self.settings.get("osd_name", "SmartBridge")
        self.tv_address = int(self.settings.get("tv_address", 0))
        self.source_address = int(self.settings.get("source_address", 4))
        self.timeout = float(self.settings.get("timeout", 12))

    # -- plumbing ---------------------------------------------------------
    def _argv(self, extra=None):
        argv = [self.binary, "-s", "-d", "1", "-t", self.device_type]
        if self.osd_name:
            argv += ["-o", self.osd_name[:13]]
        argv += list(extra or [])
        if self.adapter:
            argv.append(self.adapter)
        return argv

    def _run(self, commands, extra_args=None):
        if not self.available():
            raise BackendUnavailable("%s not found in PATH" % self.binary)
        stdin = "\n".join(commands) + "\nq\n"
        try:
            proc = subprocess.run(
                self._argv(extra_args),
                input=stdin,
                capture_output=True,
                text=True,
                timeout=self.timeout,
            )
        except subprocess.TimeoutExpired as exc:
            raise TVError("cec-client timed out after %ss" % self.timeout) from exc
        except OSError as exc:
            raise BackendUnavailable(str(exc)) from exc
        output = (proc.stdout or "") + (proc.stderr or "")
        if "could not open a connection" in output.lower():
            raise BackendUnavailable("no CEC adapter found (check the HDMI cable)")
        return output

    # -- introspection ----------------------------------------------------
    def available(self):
        return shutil.which(self.binary) is not None

    def capabilities(self):
        return {
            Capability.POWER,
            Capability.POWER_STATUS,
            Capability.VOLUME,
            Capability.KEYS,
            Capability.SOURCE,
            Capability.RAW,
        }

    def adapters(self):
        try:
            return parse_adapters(self._run([], extra_args=["-l"]))
        except TVError:
            return []

    # -- commands ---------------------------------------------------------
    def power_on(self):
        self._run(["on %d" % self.tv_address, "as"])
        return {"backend": self.name, "state": "on"}

    def power_off(self):
        self._run(["standby %d" % self.tv_address])
        return {"backend": self.name, "state": "standby"}

    def power_status(self):
        return parse_power_status(self._run(["pow %d" % self.tv_address]))

    def volume(self, action, value=None):
        commands = {"up": "volup", "down": "voldown", "mute": "mute"}
        if action == "set":
            # CEC has no absolute volume; the amplifier only knows steps.
            raise UnsupportedCommand("CEC volume is relative, use up/down")
        if action not in commands:
            raise TVError("unknown volume action: %r" % (action,))
        self._run([commands[action]])
        return {"backend": self.name, "action": action}

    def send_key(self, key):
        canonical = keymap.normalize(key)
        code = keymap.CEC_CODES.get(canonical)
        if code is None:
            raise TVError("unknown key: %r" % (key,))
        self._run(build_key_frames(self.source_address, self.tv_address, code))
        return {"backend": self.name, "key": canonical}

    def set_source(self, index):
        """Make our own HDMI port the active source.

        CEC cannot tell a TV "show HDMI 3"; a device can only announce that
        it is now the active source.  ``index`` therefore selects which
        physical address we claim, which is what the ``as`` command does for
        the port this adapter is plugged into.
        """
        index = int(index)
        if index < 1 or index > 15:
            raise TVError("HDMI index out of range: %d" % index)
        self._run(["tx %XF:82:%X0:00" % (self.source_address, index)])
        return {"backend": self.name, "source": index}

    def raw(self, command):
        if not isinstance(command, str) or not command.strip():
            raise TVError("empty raw command")
        return {"backend": self.name, "output": self._run([command.strip()])}
