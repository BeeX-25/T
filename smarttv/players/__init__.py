"""Players: where the video actually comes out.

Two very different machines run this project - a Linux box on HDMI, where
mpv gives full control, and an Android phone on HDMI, where playback is
handed to another app.  The factory picks the right one so the rest of the
code only ever sees the ``Player`` interface.
"""

from __future__ import annotations

from .android import AndroidPlayer, is_android
from .base import Player, PlayerError
from .enigma2 import Enigma2Player
from .mpv import MpvPlayer

PLAYER_CLASSES = {"mpv": MpvPlayer, "android": AndroidPlayer, "enigma2": Enigma2Player}

__all__ = [
    "AndroidPlayer",
    "Enigma2Player",
    "MpvPlayer",
    "Player",
    "PlayerError",
    "create_player",
    "is_android",
]


def create_player(player_config):
    """Build the player named in the config, or the one that fits the host."""
    player_config = player_config or {}
    name = str(player_config.get("backend", "auto")).lower()
    if name == "auto":
        name = "android" if is_android() else "mpv"
    factory = PLAYER_CLASSES.get(name)
    if factory is None:
        raise ValueError("unknown player backend: %r" % (name,))
    settings = dict(player_config.get(name) or {})
    settings.setdefault("enabled", player_config.get("enabled", True))
    return factory(settings)
