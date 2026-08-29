"""Small JSON state file: favourites, resume points, watch history.

Written atomically, because the most likely moment for the phone to lose
power is the moment the TV is being switched off.
"""

from __future__ import annotations

import json
import os
import tempfile
import threading
import time

MAX_HISTORY = 100


class Store:
    def __init__(self, path):
        self.path = os.path.expanduser(path)
        self._lock = threading.Lock()
        self.data = {"favorites": [], "resume": {}, "history": [], "ir_profile": {}}
        self.load()

    # -- persistence ------------------------------------------------------
    def load(self):
        try:
            with open(self.path, "r", encoding="utf-8") as handle:
                loaded = json.load(handle)
        except (OSError, ValueError):
            return self.data
        if isinstance(loaded, dict):
            for key in self.data:
                if key in loaded and isinstance(loaded[key], type(self.data[key])):
                    self.data[key] = loaded[key]
        return self.data

    def save(self):
        folder = os.path.dirname(self.path) or "."
        try:
            os.makedirs(folder, exist_ok=True)
            handle = tempfile.NamedTemporaryFile(
                "w", encoding="utf-8", dir=folder, delete=False
            )
            try:
                json.dump(self.data, handle, ensure_ascii=False)
                handle.flush()
                os.fsync(handle.fileno())
            finally:
                handle.close()
            os.replace(handle.name, self.path)
        except OSError:
            # A read-only home directory must not break playback.
            return False
        return True

    # -- favourites -------------------------------------------------------
    def favorites(self):
        return list(self.data["favorites"])

    def is_favorite(self, url):
        return any(item.get("url") == url for item in self.data["favorites"])

    def toggle_favorite(self, item):
        url = item.get("url")
        if not url:
            raise ValueError("a favourite needs a url")
        with self._lock:
            existing = [f for f in self.data["favorites"] if f.get("url") == url]
            if existing:
                self.data["favorites"] = [
                    f for f in self.data["favorites"] if f.get("url") != url
                ]
                added = False
            else:
                self.data["favorites"].append(
                    {
                        "url": url,
                        "name": item.get("name") or url,
                        "logo": item.get("logo", ""),
                        "kind": item.get("kind", "live"),
                        "group": item.get("group", ""),
                    }
                )
                added = True
            self.save()
        return {"favorite": added, "url": url}

    # -- learned IR remote --------------------------------------------------
    def ir_profile(self):
        return dict(self.data.get("ir_profile") or {})

    def save_ir_profile(self, profile):
        with self._lock:
            self.data["ir_profile"] = dict(profile or {})
            self.save()
        return self.ir_profile()

    # -- resume and history -----------------------------------------------
    def remember_position(self, url, position, duration=None, name=None):
        if not url or position is None:
            return None
        with self._lock:
            # Near the end there is nothing left to resume.
            if duration and position >= duration - 60:
                self.data["resume"].pop(url, None)
            else:
                self.data["resume"][url] = {
                    "position": round(float(position), 1),
                    "duration": duration,
                    "name": name,
                    "at": int(time.time()),
                }
            self.save()
        return self.data["resume"].get(url)

    def resume_position(self, url):
        entry = self.data["resume"].get(url) or {}
        return entry.get("position")

    def resume_list(self, limit=20):
        entries = [dict(value, url=url) for url, value in self.data["resume"].items()]
        entries.sort(key=lambda item: item.get("at", 0), reverse=True)
        return entries[:limit]

    def add_history(self, item):
        if not item.get("url"):
            return
        with self._lock:
            self.data["history"] = [
                entry for entry in self.data["history"] if entry.get("url") != item["url"]
            ]
            self.data["history"].insert(0, dict(item, at=int(time.time())))
            del self.data["history"][MAX_HISTORY:]
            self.save()

    def history(self, limit=20):
        return self.data["history"][:limit]
