"""Media playback through mpv's JSON IPC socket.

This is the half that actually makes the TV "smart": mpv plus yt-dlp plays
YouTube, direct video URLs, IPTV playlists and local files full-screen on
the HDMI output, and the IPC socket lets the phone remote pause and seek
it.  mpv is free and runs on a Raspberry Pi.
"""

from __future__ import annotations

import json
import os
import shutil
import socket
import subprocess
import threading


class PlayerError(Exception):
    pass


class Player:
    def __init__(self, settings=None):
        settings = settings or {}
        self.enabled = bool(settings.get("enabled", True))
        self.binary = settings.get("binary", "mpv")
        self.socket_path = settings.get("ipc_socket", "/tmp/smarttv-mpv.sock")
        self.extra_args = list(settings.get("args", []))
        self._process = None
        self._lock = threading.Lock()
        self._request_id = 0

    # -- process ----------------------------------------------------------
    def available(self):
        return self.enabled and shutil.which(self.binary) is not None

    def running(self):
        return self._process is not None and self._process.poll() is None

    def _start(self):
        if self.running():
            return
        if not self.available():
            raise PlayerError("%s not found in PATH" % self.binary)
        if os.path.exists(self.socket_path):
            try:
                os.unlink(self.socket_path)
            except OSError:
                pass
        argv = [
            self.binary,
            "--idle=yes",
            "--input-ipc-server=%s" % self.socket_path,
        ] + self.extra_args
        self._process = subprocess.Popen(
            argv, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
        )
        self._wait_for_socket()

    def _wait_for_socket(self, attempts=50, delay=0.1):
        import time

        for _ in range(attempts):
            if os.path.exists(self.socket_path):
                return
            if self._process is not None and self._process.poll() is not None:
                raise PlayerError("mpv exited before opening its IPC socket")
            time.sleep(delay)
        raise PlayerError("mpv did not open %s in time" % self.socket_path)

    def stop(self):
        """Quit mpv entirely (the TV goes back to whatever was on screen)."""
        with self._lock:
            if self.running():
                try:
                    self._raw_command(["quit"])
                except PlayerError:
                    self._process.terminate()
                try:
                    self._process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    self._process.kill()
            self._process = None
        return {"playing": False}

    # -- ipc --------------------------------------------------------------
    def _raw_command(self, command):
        self._request_id += 1
        payload = json.dumps({"command": command, "request_id": self._request_id})
        try:
            with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as sock:
                sock.settimeout(5)
                sock.connect(self.socket_path)
                sock.sendall(payload.encode("utf-8") + b"\n")
                buffer = b""
                while b"\n" not in buffer:
                    chunk = sock.recv(4096)
                    if not chunk:
                        break
                    buffer += chunk
        except (OSError, socket.timeout) as exc:
            raise PlayerError("mpv IPC failed: %s" % exc) from exc
        for line in buffer.split(b"\n"):
            if not line.strip():
                continue
            try:
                message = json.loads(line.decode("utf-8"))
            except ValueError:
                continue
            # mpv interleaves async events with replies; only replies carry
            # an "error" field.
            if "error" in message:
                if message["error"] != "success":
                    raise PlayerError("mpv: %s" % message["error"])
                return message.get("data")
        return None

    def command(self, *command):
        with self._lock:
            self._start()
            return self._raw_command(list(command))

    def _get(self, prop, default=None):
        try:
            return self.command("get_property", prop)
        except PlayerError:
            return default

    # -- playback ---------------------------------------------------------
    def play(self, url, append=False):
        if not url:
            raise PlayerError("no url given")
        self.command("loadfile", url, "append-play" if append else "replace")
        return {"playing": True, "url": url}

    def pause(self, state=True):
        self.command("set_property", "pause", bool(state))
        return {"paused": bool(state)}

    def toggle(self):
        self.command("cycle", "pause")
        return {"paused": bool(self._get("pause", False))}

    def seek(self, seconds):
        self.command("seek", float(seconds), "relative")
        return {"position": self._get("time-pos")}

    def set_volume(self, level):
        level = max(0, min(130, int(level)))
        self.command("set_property", "volume", level)
        return {"volume": level}

    def status(self):
        if not self.running():
            return {"available": self.available(), "running": False}
        return {
            "available": True,
            "running": True,
            "paused": bool(self._get("pause", False)),
            "position": self._get("time-pos"),
            "duration": self._get("duration"),
            "title": self._get("media-title"),
            "volume": self._get("volume"),
        }
