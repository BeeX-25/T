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

# Enigma2 receivers take Linux input event codes over OpenWebif.
ENIGMA2_KEYS = {
    "power": 116,
    "up": 103, "down": 108, "left": 105, "right": 106,
    "select": 352, "back": 174, "exit": 174, "menu": 139,
    "home": 102, "info": 358,
    "volume_up": 115, "volume_down": 114, "mute": 113,
    "channel_up": 402, "channel_down": 403,
    "play": 207, "pause": 119, "play_pause": 164, "stop": 128,
    "fast_forward": 208, "rewind": 168, "record": 167,
    "red": 398, "green": 399, "yellow": 400, "blue": 401,
    "tv": 377, "radio": 385, "epg": 365, "text": 388,
    "audio": 392, "subtitle": 370,
    "num0": 11, "num1": 2, "num2": 3, "num3": 4, "num4": 5,
    "num5": 6, "num6": 7, "num7": 8, "num8": 9, "num9": 10,
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
    "guide": "epg",
    "teletext": "text",
    "playpause": "play_pause",
}


def normalize(name):
    """Return the canonical key name, or None when it is unknown."""
    if not name:
        return None
    key = str(name).strip().lower().replace("-", "_").replace(" ", "_")
    key = ALIASES.get(key, key)
    known = (CEC_CODES, SAMSUNG_KEYS, WEBOS_KEYS, ENIGMA2_KEYS)
    return key if any(key in mapping for mapping in known) else None
