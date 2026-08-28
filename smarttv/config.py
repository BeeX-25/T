"""Configuration loading and defaults.

The config file is plain JSON so the project keeps working on old Python
builds (and on distros where PyYAML is not installed).  Every key has a
default, so a missing or partial file is fine.
"""

from __future__ import annotations

import copy
import json
import os

DEFAULTS = {
    "server": {
        "host": "0.0.0.0",
        "port": 8099,
        # When set, /api/* requires this token (Bearer header, X-Auth-Token
        # header, or ?token= query param).  Empty means the LAN is trusted.
        "auth_token": "",
    },
    "tv": {
        # Backends are tried in this order; the first available one that
        # supports the requested command wins.
        "order": ["cec", "samsung", "webos"],
        "cec": {
            "enabled": True,
            "binary": "cec-client",
            "adapter": "",
            "device_type": "p",
            "osd_name": "SmartBridge",
            "tv_address": 0,
            "source_address": 4,
            "timeout": 12,
        },
        "samsung": {
            "enabled": False,
            "host": "",
            "port": 8002,
            "name": "SmartBridge",
            "token_file": "~/.smarttv/samsung_token.txt",
            "mac": "",
        },
        "webos": {
            "enabled": False,
            "host": "",
            "key_file": "~/.smarttv/webos_key.json",
            "mac": "",
        },
    },
    "player": {
        "enabled": True,
        "binary": "mpv",
        "ipc_socket": "/tmp/smarttv-mpv.sock",
        "args": [
            "--fullscreen",
            "--force-window=yes",
            "--ytdl-format=bestvideo[height<=?1080]+bestaudio/best",
        ],
    },
    "shortcuts": [
        {"name": "YouTube", "url": "https://www.youtube.com"},
    ],
    "automation": {
        "sleep_timer_minutes": 45,
        # {"name": ..., "cron": "m h dom mon dow", "action": "power_off"}
        "rules": [],
    },
}

# Values that are file-system paths and should get ~ expanded.
_PATH_KEYS = {"token_file", "key_file", "ipc_socket"}


def deep_merge(base, override):
    """Recursively merge ``override`` into a copy of ``base``."""
    result = copy.deepcopy(base)
    for key, value in (override or {}).items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = deep_merge(result[key], value)
        else:
            result[key] = copy.deepcopy(value)
    return result


def _expand_paths(node):
    if isinstance(node, dict):
        return {
            key: os.path.expanduser(value)
            if key in _PATH_KEYS and isinstance(value, str)
            else _expand_paths(value)
            for key, value in node.items()
        }
    if isinstance(node, list):
        return [_expand_paths(item) for item in node]
    return node


def load(path=None):
    """Load a config file, falling back to defaults for anything missing."""
    user = {}
    if path:
        with open(path, "r", encoding="utf-8") as handle:
            user = json.load(handle)
        if not isinstance(user, dict):
            raise ValueError("config root must be a JSON object")
    return _expand_paths(deep_merge(DEFAULTS, user))
