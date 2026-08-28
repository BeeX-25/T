"""Shared helpers: keep tests off the real home directory."""

from __future__ import annotations

import os
import tempfile

from smarttv.config import load


def isolated_settings(folder, **overrides):
    """Default config, but with all state written inside ``folder``."""
    settings = load()
    settings["state_file"] = os.path.join(folder, "state.json")
    settings["catalog"]["cache_dir"] = os.path.join(folder, "cache")
    settings["player"]["mpv"]["ipc_socket"] = os.path.join(folder, "mpv.sock")
    for key, value in overrides.items():
        settings[key] = value
    return settings


class TempHome:
    """Context manager giving a throwaway folder plus matching settings."""

    def __enter__(self):
        self._folder = tempfile.TemporaryDirectory()
        return self._folder.name

    def __exit__(self, *exc_info):
        self._folder.cleanup()
        return False
