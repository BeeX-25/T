"""Normalised remote keys mapped onto every backend's own vocabulary.

The web UI and the HTTP API only ever speak the names in ``CEC_CODES``;
each backend translates them.  That is what lets one remote drive a dumb
TV over HDMI-CEC and a networked Samsung/LG with the same button.
"""

from __future__ import annotations

# CEC "user control code" values (HDMI-CEC spec, opcode 0x44).
CEC_CODES = {
    "select": 0x00,
    "up": 0x01,
    "down": 0x02,
    "left": 0x03,
    "right": 0x04,
    "menu": 0x09,
    "back": 0x0D,
    "num0": 0x20,
    "num1": 0x21,
    "num2": 0x22,
    "num3": 0x23,
    "num4": 0x24,
    "num5": 0x25,
    "num6": 0x26,
    "num7": 0x27,
    "num8": 0x28,
    "num9": 0x29,
    "channel_up": 0x30,
    "channel_down": 0x31,
    "power": 0x40,
    "volume_up": 0x41,
    "volume_down": 0x42,
    "mute": 0x43,
    "play": 0x44,
    "stop": 0x45,
    "pause": 0x46,
    "rewind": 0x48,
    "fast_forward": 0x49,
    "forward": 0x4B,
    "backward": 0x4C,
    "info": 0x35,
    "home": 0x09,
    "exit": 0x0D,
}

SAMSUNG_KEYS = {
    "select": "KEY_ENTER",
    "up": "KEY_UP",
    "down": "KEY_DOWN",
    "left": "KEY_LEFT",
    "right": "KEY_RIGHT",
    "menu": "KEY_MENU",
    "back": "KEY_RETURN",
    "exit": "KEY_EXIT",
    "home": "KEY_HOME",
    "info": "KEY_INFO",
    "power": "KEY_POWER",
    "volume_up": "KEY_VOLUP",
    "volume_down": "KEY_VOLDOWN",
    "mute": "KEY_MUTE",
    "channel_up": "KEY_CHUP",
    "channel_down": "KEY_CHDOWN",
    "play": "KEY_PLAY",
    "pause": "KEY_PAUSE",
    "stop": "KEY_STOP",
    "rewind": "KEY_REWIND",
    "fast_forward": "KEY_FF",
    "source": "KEY_SOURCE",
    **{"num%d" % n: "KEY_%d" % n for n in range(10)},
}

WEBOS_KEYS = {
    "select": "ENTER",
    "up": "UP",
    "down": "DOWN",
    "left": "LEFT",
    "right": "RIGHT",
    "back": "BACK",
    "exit": "EXIT",
    "home": "HOME",
    "menu": "MENU",
    "info": "INFO",
    "channel_up": "CHANNELUP",
    "channel_down": "CHANNELDOWN",
    **{"num%d" % n: str(n) for n in range(10)},
}

# Aliases so callers can send whatever the remote on their desk says.
ALIASES = {
    "ok": "select",
    "enter": "select",
    "return": "back",
    "vol_up": "volume_up",
    "vol+": "volume_up",
    "vol_down": "volume_down",
    "vol-": "volume_down",
    "ch+": "channel_up",
    "ch-": "channel_down",
    "ff": "fast_forward",
    "rew": "rewind",
}


def normalize(name):
    """Return the canonical key name, or None when it is unknown."""
    if not name:
        return None
    key = str(name).strip().lower().replace("-", "_").replace(" ", "_")
    key = ALIASES.get(key, key)
    return key if key in CEC_CODES or key in SAMSUNG_KEYS or key in WEBOS_KEYS else None
