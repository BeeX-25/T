"""The service layer: one dispatch table shared by HTTP and the CLI."""

from __future__ import annotations

import time

from . import discovery, keys as keymap
from .automation import Scheduler
from .backends.base import TVError
from .catalog import Catalog
from .players import PlayerError, create_player
from .registry import Registry
from .store import Store


class ApiError(Exception):
    def __init__(self, message, status=400):
        super().__init__(message)
        self.status = status


class Api:
    def __init__(self, config, demo=False, logger=None):
        self.config = config
        self.logger = logger or (lambda message: None)
        self.registry = Registry.from_config(config["tv"], demo=demo)
        self.player = create_player(self._player_config(config))
        self.store = Store(config.get("state_file", "~/.smarttv/state.json"))
        self.catalog = Catalog(config.get("catalog", {}), logger=self.logger)
        self.current = None
        self._last_resume_write = 0
        self.scheduler = Scheduler(
            actions=self._actions(),
            rules=config["automation"].get("rules", []),
            logger=self.logger,
        )
        self.routes = {
            ("GET", "/api/status"): self.status,
            ("GET", "/api/config"): self.describe_config,
            ("GET", "/api/discover"): self.discover,
            ("POST", "/api/power"): self.power,
            ("POST", "/api/volume"): self.volume,
            ("POST", "/api/key"): self.key,
            ("POST", "/api/source"): self.source,
            ("POST", "/api/app"): self.launch_app,
            ("POST", "/api/raw"): self.raw,
            ("POST", "/api/cast"): self.cast,
            ("POST", "/api/player"): self.player_control,
            ("POST", "/api/sleep"): self.sleep_timer,
            ("DELETE", "/api/sleep"): self.cancel_sleep_timer,
            ("GET", "/api/catalog"): self.browse,
            ("POST", "/api/catalog/refresh"): self.refresh_catalog,
            ("GET", "/api/series"): self.browse_series,
            ("GET", "/api/epg"): self.epg,
            ("GET", "/api/favorites"): self.list_favorites,
            ("POST", "/api/favorites"): self.toggle_favorite,
            ("GET", "/api/resume"): self.list_resume,
            ("GET", "/api/episodes"): self.list_episodes,
        }

    @staticmethod
    def _player_config(config):
        """Let the Enigma2 player inherit the receiver's address.

        The receiver is one box: repeating its host and password under
        ``player`` would only be a way to get them out of sync.
        """
        player = dict(config.get("player") or {})
        receiver = (config.get("tv") or {}).get("enigma2") or {}
        settings = dict(player.get("enigma2") or {})
        if not settings.get("host"):
            for key in ("host", "port", "username", "password", "stream_port", "service_type"):
                if receiver.get(key) not in (None, ""):
                    settings[key] = receiver[key]
        player["enigma2"] = settings
        return player

    # -- lifecycle --------------------------------------------------------
    def start(self):
        self.scheduler.start()

    def shutdown(self):
        self._save_position(force=True)
        self.scheduler.shutdown()
        try:
            self.player.stop()
        except PlayerError:
            pass

    def _actions(self):
        """Names usable in automation rules and by the sleep timer."""
        return {
            "power_on": lambda: self.registry.call("power_on"),
            "power_off": lambda: self.registry.call("power_off"),
            "volume": lambda action="up": self.registry.call("volume", action),
            "key": lambda name="home": self.registry.call("send_key", name),
            "source": lambda index="1": self.registry.call("set_source", int(index)),
            "cast": lambda url: self.player.play(url),
            "stop": lambda: self.player.stop(),
            "notify": lambda message="": self.registry.call("notify", message),
        }

    # -- dispatch ---------------------------------------------------------
    def dispatch(self, method, path, payload=None):
        handler = self.routes.get((method.upper(), path.rstrip("/") or "/"))
        if handler is None:
            raise ApiError("no such endpoint: %s %s" % (method, path), status=404)
        try:
            return handler(payload or {})
        except ApiError:
            raise
        except (TVError, PlayerError) as exc:
            raise ApiError(str(exc), status=502) from exc
        except (ValueError, KeyError, TypeError) as exc:
            raise ApiError(str(exc), status=400) from exc

    # -- handlers ---------------------------------------------------------
    def _save_position(self, force=False):
        """Store the playback position, at most once every 30 seconds."""
        if not self.current:
            return
        if not force and time.time() - self._last_resume_write < 30:
            return
        try:
            state = self.player.status()
        except PlayerError:
            return
        if not state.get("running") or not state.get("position"):
            return
        self._last_resume_write = time.time()
        self.store.remember_position(
            self.current["url"],
            state.get("position"),
            state.get("duration"),
            self.current.get("name"),
        )

    def status(self, payload):
        active = self.registry.active()
        power = None
        power_error = None
        if active is not None:
            try:
                power = self.registry.call("power_status")
            except TVError as exc:
                power_error = str(exc)
        player_state = self.player.status()
        self._save_position()
        return {
            "backend": active.name if active else None,
            "backends": self.registry.info(),
            "power": power,
            "power_error": power_error,
            "player": player_state,
            "now_playing": self.current,
            "catalog": self.catalog.status(),
            "scheduler": self.scheduler.describe(),
        }

    def describe_config(self, payload):
        """Everything the web remote needs, minus the secrets."""
        return {
            "shortcuts": self.config.get("shortcuts", []),
            "backends": self.registry.info(),
            "keys": sorted(keymap.CEC_CODES),
            "sleep_timer_minutes": self.config["automation"].get(
                "sleep_timer_minutes", 45
            ),
            "player": {
                "name": self.player.name,
                "available": self.player.available(),
                "capabilities": sorted(self.player.capabilities()),
            },
            "catalog": self.catalog.status(),
        }

    def discover(self, payload):
        timeout = float(payload.get("timeout", 3))
        return {"devices": discovery.scan(timeout=min(timeout, 10))}

    def power(self, payload):
        state = str(payload.get("state", "toggle")).lower()
        if state == "toggle":
            try:
                current = self.registry.call("power_status")
            except TVError:
                current = "unknown"
            state = "off" if current == "on" else "on"
        if state in ("on", "1", "true"):
            return self.registry.call("power_on", backend=payload.get("backend"))
        if state in ("off", "0", "false", "standby"):
            return self.registry.call("power_off", backend=payload.get("backend"))
        raise ApiError("state must be on, off or toggle")

    def volume(self, payload):
        action = str(payload.get("action", "up")).lower()
        if action not in ("up", "down", "mute", "set"):
            raise ApiError("action must be up, down, mute or set")
        repeat = max(1, min(int(payload.get("repeat", 1)), 20))
        result = None
        for _ in range(repeat):
            result = self.registry.call(
                "volume", action, payload.get("value"), backend=payload.get("backend")
            )
        return result

    def key(self, payload):
        name = payload.get("key")
        if not keymap.normalize(name):
            raise ApiError("unknown key: %r" % (name,))
        repeat = max(1, min(int(payload.get("repeat", 1)), 20))
        result = None
        for _ in range(repeat):
            result = self.registry.call("send_key", name, backend=payload.get("backend"))
        return result

    def source(self, payload):
        return self.registry.call(
            "set_source", int(payload.get("index", 1)), backend=payload.get("backend")
        )

    def launch_app(self, payload):
        app = payload.get("app")
        if not app:
            raise ApiError("app is required")
        return self.registry.call("launch_app", app, backend=payload.get("backend"))

    def raw(self, payload):
        command = payload.get("command")
        if not command:
            raise ApiError("command is required")
        return self.registry.call("raw", command, backend=payload.get("backend"))

    def cast(self, payload):
        url = payload.get("url")
        if not url:
            raise ApiError("url is required")
        if payload.get("power_on", True):
            # Nothing to watch on a TV in standby; best-effort wake first.
            try:
                self.registry.call("power_on")
            except TVError as exc:
                self.logger("cast: could not power on the TV: %s" % exc)
        self._save_position()
        start = None
        if payload.get("resume", True):
            start = self.store.resume_position(url)
        item = {
            "url": url,
            "name": payload.get("name") or url,
            "kind": payload.get("kind", "live"),
            "logo": payload.get("logo", ""),
            "group": payload.get("group", ""),
        }
        result = self.player.play(url, append=bool(payload.get("append")), start=start)
        self.current = item
        self.store.add_history(item)
        if start:
            result["resumed_at"] = start
        return result

    # -- library ----------------------------------------------------------
    def browse(self, payload):
        kind = payload.get("kind") or None
        found = self.catalog.search(
            query=payload.get("q", ""),
            kind=kind,
            group=payload.get("group") or None,
            limit=payload.get("limit", 60),
            offset=payload.get("offset", 0),
        )
        favorites = {item["url"] for item in self.store.favorites()}
        for item in found["items"]:
            item["favorite"] = item.get("url") in favorites
        found["groups"] = self.catalog.groups(kind)
        found["status"] = self.catalog.status()
        return found

    def browse_series(self, payload):
        return self.catalog.series(
            query=payload.get("q", ""),
            limit=payload.get("limit", 60),
            offset=payload.get("offset", 0),
        )

    def list_episodes(self, payload):
        """Episodes of one show; Xtream lists them only when asked."""
        series_id = payload.get("series_id")
        if not series_id:
            raise ApiError("series_id is required")
        try:
            episodes = self.catalog.episodes(series_id, payload.get("source"))
        except ValueError as exc:
            raise ApiError(str(exc), status=404) from exc
        except OSError as exc:
            raise ApiError("could not reach the provider: %s" % exc, status=502) from exc
        return {"series_id": series_id, "episodes": episodes}

    def refresh_catalog(self, payload):
        return self.catalog.refresh(force=True)

    def epg(self, payload):
        channel = payload.get("channel")
        if not channel:
            raise ApiError("channel is required")
        return {
            "channel": channel,
            "programmes": self.catalog.now_and_next(
                channel, count=int(payload.get("count", 3))
            ),
        }

    def list_favorites(self, payload):
        return {"items": self.store.favorites()}

    def toggle_favorite(self, payload):
        if not payload.get("url"):
            raise ApiError("url is required")
        return self.store.toggle_favorite(payload)

    def list_resume(self, payload):
        return {
            "items": self.store.resume_list(int(payload.get("limit", 20))),
            "history": self.store.history(int(payload.get("limit", 20))),
        }

    def player_control(self, payload):
        action = str(payload.get("action", "toggle")).lower()
        if action == "toggle":
            return self.player.toggle()
        if action == "pause":
            return self.player.pause(True)
        if action == "resume":
            return self.player.pause(False)
        if action == "stop":
            self._save_position(force=True)
            result = self.player.stop()
            self.current = None
            return result
        if action == "seek":
            return self.player.seek(payload.get("value", 30))
        if action == "volume":
            return self.player.set_volume(payload.get("value", 100))
        if action == "status":
            return self.player.status()
        raise ApiError("unknown player action: %r" % (action,))

    def sleep_timer(self, payload):
        minutes = payload.get(
            "minutes", self.config["automation"].get("sleep_timer_minutes", 45)
        )
        return self.scheduler.set_sleep_timer(minutes, payload.get("action", "power_off"))

    def cancel_sleep_timer(self, payload):
        return self.scheduler.cancel_sleep_timer()
