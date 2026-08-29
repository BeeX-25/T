"""The library: live channels, films and series, from sources you supply.

The project ships no content of its own.  It reads the open formats the
whole IPTV world already uses - M3U playlists, XMLTV guides, the Xtream
Codes API, and an Enigma2 receiver's own bouquets - and turns them into
something browsable on a phone: groups, search, favourites and a
"continue watching" row.

Fetching (with its on-disk cache) lives here; the per-protocol parsing
lives in ``sources``.
"""

from __future__ import annotations

import hashlib
import os
import re
import threading
import time
import urllib.request

from .sources import (  # re-exported: the library's public parsing surface
    load_source,
    load_xtream_episodes,
    parse_m3u,
    parse_xmltv,
)

EPISODE_RE = re.compile(
    r"(?:^|[\s._-])(?:s|season[\s._-]?)(\d{1,2})[\s._-]?(?:e|ep|x|episode[\s._-]?)(\d{1,3})",
    re.I,
)
ARABIC_EPISODE_RE = re.compile(r"(?:الحلقة|حلقة)\s*[:\-]?\s*(\d{1,3})")
USER_AGENT = "SmartTVBridge/1.0"

__all__ = [
    "Catalog",
    "load_source",
    "parse_episode",
    "parse_m3u",
    "parse_xmltv",
    "series_title",
]


def parse_episode(title):
    """Pull (season, episode) out of a title, Arabic or English."""
    match = EPISODE_RE.search(title or "")
    if match:
        return int(match.group(1)), int(match.group(2))
    arabic = ARABIC_EPISODE_RE.search(title or "")
    if arabic:
        return 1, int(arabic.group(1))
    return None


def series_title(title):
    """The show name with the episode marker stripped off."""
    if not title:
        return ""
    cleaned = EPISODE_RE.split(title, maxsplit=1)[0]
    cleaned = ARABIC_EPISODE_RE.split(cleaned, maxsplit=1)[0]
    return cleaned.strip(" -_.|") or title.strip()


class Catalog:
    """Loads the configured sources and answers browse/search queries."""

    def __init__(self, settings=None, cache_dir=None, logger=None):
        settings = settings or {}
        self.sources = list(settings.get("sources", []))
        self.ttl = int(settings.get("cache_hours", 6)) * 3600
        self.timeout = float(settings.get("timeout", 20))
        self.cache_dir = os.path.expanduser(
            cache_dir or settings.get("cache_dir", "~/.smarttv/cache")
        )
        self.logger = logger or (lambda message: None)
        self.items = []
        self.guide = {}
        self.loaded_at = None
        self.errors = []
        self._lock = threading.Lock()

    # -- fetching ---------------------------------------------------------
    def _cache_path(self, key):
        digest = hashlib.sha1(key.encode("utf-8")).hexdigest()[:16]
        return os.path.join(self.cache_dir, digest + ".cache")

    def _read_cache(self, key, max_age):
        try:
            path = self._cache_path(key)
            if time.time() - os.path.getmtime(path) > max_age:
                return None
            with open(path, "r", encoding="utf-8") as handle:
                return handle.read()
        except OSError:
            return None

    def _write_cache(self, key, text):
        try:
            os.makedirs(self.cache_dir, exist_ok=True)
            with open(self._cache_path(key), "w", encoding="utf-8") as handle:
                handle.write(text)
        except OSError:
            pass

    def _download(self, url):
        request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        with urllib.request.urlopen(request, timeout=self.timeout) as response:
            return response.read().decode("utf-8", "replace")

    def fetcher(self, force=False):
        """A ``fetch(target)`` for the source loaders: file or URL, cached.

        A provider that is down must not empty the library, so a failed
        download falls back to the last copy on disk however old it is.
        """

        def fetch(target):
            if not target:
                raise ValueError("source has no url or path")
            if "://" not in target:
                with open(
                    os.path.expanduser(target), "r", encoding="utf-8", errors="replace"
                ) as handle:
                    return handle.read()
            if not force:
                cached = self._read_cache(target, self.ttl)
                if cached is not None:
                    return cached
            try:
                text = self._download(target)
            except Exception:
                stale = self._read_cache(target, float("inf"))
                if stale is None:
                    raise
                self.logger("catalog: using the cached copy of %s" % target)
                return stale
            self._write_cache(target, text)
            return text

        return fetch

    # -- loading ----------------------------------------------------------
    def refresh(self, force=False):
        """Reload every source; a broken source never hides the others."""
        items = []
        guide = {}
        errors = []
        fetch = self.fetcher(force=force)
        for source in self.sources:
            name = source.get("name") or source.get("url") or source.get("path") or "?"
            try:
                loaded = load_source(source, fetch)
            except Exception as exc:
                errors.append({"source": name, "error": str(exc)})
                self.logger("catalog: %s failed: %s" % (name, exc))
                continue
            items.extend(loaded.get("items") or [])
            guide.update(loaded.get("guide") or {})
        with self._lock:
            self.items = items
            self.guide = guide
            self.errors = errors
            self.loaded_at = time.time()
        return {"items": len(items), "channels_with_guide": len(guide), "errors": errors}

    def ensure_loaded(self):
        if self.loaded_at is None or (time.time() - self.loaded_at) > self.ttl:
            if self.sources:
                self.refresh()
        return self.items

    # -- browsing ---------------------------------------------------------
    def groups(self, kind=None):
        counts = {}
        for item in self.ensure_loaded():
            if kind and item.get("kind") != kind:
                continue
            label = item.get("group") or "غير مصنّف"
            counts[label] = counts.get(label, 0) + 1
        return [
            {"name": name, "count": count}
            for name, count in sorted(counts.items(), key=lambda pair: -pair[1])
        ]

    def search(self, query="", kind=None, group=None, limit=60, offset=0):
        query = (query or "").strip().lower()
        matches = []
        for item in self.ensure_loaded():
            if kind and item.get("kind") != kind:
                continue
            if group and item.get("group") != group:
                continue
            if query and query not in item.get("name", "").lower():
                continue
            matches.append(item)
        limit = max(1, min(int(limit), 300))
        offset = max(0, int(offset))
        return {
            "total": len(matches),
            "offset": offset,
            "items": matches[offset : offset + limit],
        }

    def series(self, query="", limit=60, offset=0):
        """One entry per show, whether its episodes are listed or remote."""
        shows = {}
        for item in self.search(query, kind="series", limit=300000).get("items", []):
            if item.get("series_id"):
                # An Xtream series: the provider lists episodes on demand.
                shows[item.get("name", "")] = {
                    "name": item.get("name", ""),
                    "logo": item.get("logo", ""),
                    "kind": "series",
                    "group": item.get("group", ""),
                    "series_id": item["series_id"],
                    "source": item.get("source", ""),
                    "episodes": [],
                    "episode_count": None,
                }
                continue
            title = series_title(item.get("name", "")) or item.get("group", "")
            show = shows.setdefault(
                title,
                {
                    "name": title,
                    "logo": item.get("logo", ""),
                    "kind": "series",
                    "group": item.get("group", ""),
                    "episodes": [],
                },
            )
            marker = parse_episode(item.get("name", ""))
            show["episodes"].append(
                {
                    "name": item.get("name"),
                    "url": item.get("url"),
                    "season": marker[0] if marker else None,
                    "episode": marker[1] if marker else None,
                }
            )
        for show in shows.values():
            if show.get("series_id"):
                continue
            show["episodes"].sort(
                key=lambda entry: (entry["season"] or 0, entry["episode"] or 0)
            )
            show["episode_count"] = len(show["episodes"])
        ordered = sorted(shows.values(), key=lambda show: show["name"])
        limit = max(1, min(int(limit), 300))
        offset = max(0, int(offset))
        return {
            "total": len(ordered),
            "offset": offset,
            "items": ordered[offset : offset + limit],
        }

    def episodes(self, series_id, source=None):
        """Fetch one Xtream series' episodes when the user opens the show."""
        for settings in self.sources:
            if str(settings.get("type", "")).lower() != "xtream":
                continue
            if source and settings.get("name") != source:
                continue
            return load_xtream_episodes(settings, self.fetcher(), series_id)
        raise ValueError("no Xtream source is configured for this series")

    def now_and_next(self, channel_id, count=3):
        """What is on this channel now, and what follows."""
        programmes = self.guide.get(channel_id) or []
        now = time.time()
        upcoming = [p for p in programmes if (p.get("stop") or 0) >= now]
        return upcoming[:count]

    def status(self):
        kinds = {}
        for item in self.items:
            kinds[item.get("kind", "live")] = kinds.get(item.get("kind", "live"), 0) + 1
        return {
            "sources": len(self.sources),
            "items": len(self.items),
            "kinds": kinds,
            "guide_channels": len(self.guide),
            "loaded_at": self.loaded_at,
            "errors": self.errors,
        }
