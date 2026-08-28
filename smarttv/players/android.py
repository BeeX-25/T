"""Playback on Android, driven from Termux - the no-laptop path.

An old phone plugged into the TV (USB-C to HDMI) is the cheapest media box
there is, but Termux runs as an ordinary app, not as shell.  That limits
what is possible without root, and this driver is deliberate about the
line:

  * launching playback works - ``am start`` hands a URL to VLC, MX Player,
    the YouTube app or the browser;
  * volume works - ``termux-volume`` sets the music stream;
  * "stop" is best effort - an app cannot force-stop another app, so we go
    back to the home screen, which pauses every player worth using;
  * pause and seek need key injection, which Android only grants to shell.
    Enable ``use_input_keyevents`` when running under root or ADB and they
    light up; otherwise the API reports them as unsupported instead of
    pretending.
"""

from __future__ import annotations

import os
import shutil
import subprocess

from .base import Player, PlayerError

# Apps worth handing a stream to.  Naming the activity is what makes the
# stream open straight in the player instead of in a chooser dialog; an
# empty component means "let Android decide", which is right for YouTube
# links and for whatever the user has set as default.
APP_COMPONENTS = {
    "auto": "",
    "browser": "",
    "youtube": "",
    "vlc": "org.videolan.vlc/org.videolan.vlc.gui.video.VideoPlayerActivity",
    "mx": "com.mxtech.videoplayer.ad/.ActivityScreen",
    "mxpro": "com.mxtech.videoplayer.pro/.ActivityScreen",
}

KEYCODES = {
    "play_pause": 85,
    "stop": 86,
    "next": 87,
    "previous": 88,
    "rewind": 89,
    "fast_forward": 90,
    "volume_up": 24,
    "volume_down": 25,
}


def is_android():
    """True when we are running on Android (Termux included)."""
    if os.environ.get("ANDROID_ROOT") or os.environ.get("ANDROID_DATA"):
        return True
    return os.path.isdir("/system/app") and os.path.isdir("/system/priv-app")


def build_view_intent(url, component="", mime="video/*"):
    """Build the ``am start`` argv that hands ``url`` to a player app."""
    argv = ["am", "start", "-a", "android.intent.action.VIEW", "-d", str(url)]
    # A web page must not be typed as a raw video file, or the app that
    # knows the site (YouTube, say) never gets offered the intent.
    if mime and not _is_web_page(url):
        argv += ["-t", mime]
    if component:
        argv += ["-n", component]
    return argv


def _is_web_page(url):
    lowered = str(url).lower()
    if any(host in lowered for host in ("youtube.com", "youtu.be")):
        return True
    return lowered.startswith("http") and not lowered.rsplit(".", 1)[-1][:4] in (
        "mp4",
        "mkv",
        "m3u8",
        "ts",
        "avi",
        "webm",
        "mov",
        "mp3",
    )


class AndroidPlayer(Player):
    name = "android"

    def __init__(self, settings=None):
        settings = settings or {}
        super().__init__(settings)
        self.enabled = bool(settings.get("enabled", True))
        self.app = settings.get("app", "vlc")
        self.use_input_keyevents = bool(settings.get("use_input_keyevents", False))
        self.timeout = float(settings.get("timeout", 15))
        self._last_url = None
        self._launched = False

    # -- plumbing ---------------------------------------------------------
    def _am(self):
        """Termux ships its own ``am``; fall back to the system one."""
        return shutil.which("termux-am") or shutil.which("am")

    def _run(self, argv):
        try:
            proc = subprocess.run(
                argv, capture_output=True, text=True, timeout=self.timeout
            )
        except subprocess.TimeoutExpired as exc:
            raise PlayerError("%s timed out" % argv[0]) from exc
        except OSError as exc:
            raise PlayerError("%s: %s" % (argv[0], exc)) from exc
        output = (proc.stdout or "") + (proc.stderr or "")
        if proc.returncode != 0 or "Error" in output or "Exception" in output:
            raise PlayerError(output.strip().splitlines()[-1] if output.strip() else "failed")
        return output

    def _keyevent(self, name):
        if not self.use_input_keyevents:
            raise PlayerError(
                "Android only allows key injection from shell; "
                "set player.android.use_input_keyevents when running rooted or over ADB"
            )
        binary = shutil.which("input") or "/system/bin/input"
        return self._run([binary, "keyevent", str(KEYCODES[name])])

    # -- introspection ----------------------------------------------------
    def available(self):
        return self.enabled and is_android() and self._am() is not None

    def running(self):
        return self._launched

    def capabilities(self):
        caps = {"play", "stop", "volume"}
        if self.use_input_keyevents:
            caps |= {"pause", "seek"}
        return caps

    # -- playback ---------------------------------------------------------
    def play(self, url, append=False, start=None):
        # ``start`` is ignored: once the intent is handed over, the player
        # app owns the position (VLC resumes on its own anyway).
        if not url:
            raise PlayerError("no url given")
        component = APP_COMPONENTS.get(self.app, self.app if "/" in self.app else "")
        try:
            self._run([self._am()] + build_view_intent(url, component)[1:])
        except PlayerError:
            if not component:
                raise
            # The preferred app is not installed - let Android choose.
            self._run([self._am()] + build_view_intent(url, "")[1:])
        self._last_url = url
        self._launched = True
        return {"playing": True, "url": url, "player": self.name}

    def pause(self, state=True):
        self._keyevent("play_pause")
        return {"paused": bool(state)}

    def toggle(self):
        self._keyevent("play_pause")
        return {"paused": None}

    def seek(self, seconds):
        # Android exposes no absolute seek; each press jumps by whatever the
        # player app uses (usually 10 seconds).
        seconds = float(seconds)
        presses = max(1, min(12, int(abs(seconds) // 10) or 1))
        for _ in range(presses):
            self._keyevent("fast_forward" if seconds > 0 else "rewind")
        return {"seek_presses": presses, "approximate": True}

    def set_volume(self, level):
        level = max(0, min(100, int(level)))
        binary = shutil.which("termux-volume")
        if binary:
            # termux-volume works in Android steps (usually 0-15).
            steps = max(0, min(15, round(level * 15 / 100)))
            self._run([binary, "music", str(steps)])
            return {"volume": level, "steps": steps}
        raise PlayerError("install Termux:API for volume control (pkg install termux-api)")

    def stop(self):
        # No app may force-stop another, so send the launcher to the front;
        # every sane player pauses when it loses the screen.
        if self._am():
            self._run(
                [
                    self._am(),
                    "start",
                    "-a",
                    "android.intent.action.MAIN",
                    "-c",
                    "android.intent.category.HOME",
                ]
            )
        self._launched = False
        return {"playing": False, "note": "returned to the home screen"}

    def status(self):
        return {
            "available": self.available(),
            "running": self._launched,
            "player": self.name,
            "url": self._last_url,
            "controllable": sorted(self.capabilities()),
        }
