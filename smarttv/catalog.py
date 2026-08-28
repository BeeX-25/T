"""The library: live channels, films and series, from playlists you supply.

The project ships no content of its own.  It reads the open formats the
whole IPTV world already uses - M3U playlists and XMLTV guides - so you
point it at free-to-air public playlists (iptv-org publishes them), at a
subscription you pay for, or at your own media server, and it turns them
into something browsable on a phone: groups, search, favourites and a
"continue watching" row.
"""

from __future__ import annotations

import hashlib
import os
import re
import threading
import time
import urllib.request
import xml.etree.ElementTree as ElementTree

ATTRIBUTE_RE = re.compile(r'([\w-]+)="([^"]*)"')
EPISODE_RE = re.compile(
    r"(?:^|[\s._-])(?:s|season[\s._-]?)(\d{1,2})[\s._-]?(?:e|ep|x|episode[\s._-]?)(\d{1,3})",
    re.I,
)
ARABIC_EPISODE_RE = re.compile(r"(?:الحلقة|حلقة)\s*[:\-]?\s*(\d{1,3})")
USER_AGENT = "SmartTVBridge/1.0"


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


def parse_m3u(text, kind="live", source=""):
    """Parse an extended M3U playlist into catalogue items."""
    items = []
    pending = None
    group_override = ""
    for raw_line in (text or "").splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if line.upper().startswith("#EXTM3U"):
            continue
        if line.upper().startswith("#EXTGRP:"):
            group_override = line.split(":", 1)[1].strip()
            continue
        if line.upper().startswith("#EXTINF"):
            attributes = dict(ATTRIBUTE_RE.findall(line))
            name = line.split(",", 1)[1].strip() if "," in line else ""
            pending = {
                "name": name or attributes.get("tvg-name", "").strip() or "بدون اسم",
                "logo": attributes.get("tvg-logo", ""),
                "tvg_id": attributes.get("tvg-id", ""),
                "group": attributes.get("group-title", "") or group_override,
                "kind": kind,
                "source": source,
            }
            continue
        if line.startswith("#"):
            continue
        if pending is None:
            # A bare URL list is a valid playlist too.
            pending = {
                "name": line.rsplit("/", 1)[-1] or line,
                "logo": "",
                "tvg_id": "",
                "group": group_override,
                "kind": kind,
                "source": source,
            }
        pending["url"] = line
        items.append(pending)
        pending = None
    return items


def _xmltv_time(value):
    """XMLTV stamps look like 20260828120000 +0300."""
    if not value:
        return None
    text = value.strip()
    offset = 0
    if " " in text:
        text, zone = text.split(" ", 1)
        zone = zone.strip()
        if len(zone) >= 5 and zone[0] in "+-":
            sign = 1 if zone[0] == "+" else -1
            offset = sign * (int(zone[1:3]) * 3600 + int(zone[3:5]) * 60)
    text = (text + "000000")[:14]
    try:
        parsed = time.strptime(text, "%Y%m%d%H%M%S")
    except ValueError:
        return None
    return int(time.mktime(parsed) - time.timezone) - offset


def parse_xmltv(text):
    """Parse an XMLTV guide into ``{channel_id: [programmes]}``."""
    guide = {}
    try:
        root = ElementTree.fromstring(text)
    except ElementTree.ParseError:
        return guide
    for element in root.iter("programme"):
        channel = element.get("channel", "")
        if not channel:
            continue
        title = element.findtext("title") or ""
        guide.setdefault(channel, []).append(
            {
                "title": title.strip(),
                "description": (element.findtext("desc") or "").strip(),
                "start": _xmltv_time(element.get("start")),
                "stop": _xmltv_time(element.get("stop")),
            }
        )
    for programmes in guide.values():
        programmes.sort(key=lambda item: item.get("start") or 0)
    return guide


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
        path = self._cache_path(key)
        try:
            age = time.time() - os.path.getmtime(path)
            if age > max_age:
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

    def _fetch(self, source, force):
        """Return the text of one source, from cache when it is fresh."""
        path = source.get("path")
        if path:
            with open(os.path.expanduser(path), "r", encoding="utf-8", errors="replace") as handle:
                return handle.read()
        url = source.get("url")
        if not url:
            raise ValueError("source needs a url or a path")
        if not force:
            cached = self._read_cache(url, self.ttl)
            if cached is not None:
                return cached
        request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        with urllib.request.urlopen(request, timeout=self.timeout) as response:
            text = response.read().decode("utf-8", "replace")
        self._write_cache(url, text)
        return text

    def refresh(self, force=False):
        """Reload every source; a broken source never hides the others."""
        items = []
        guide = {}
        errors = []
        for source in self.sources:
            name = source.get("name") or source.get("url") or source.get("path") or "?"
            try:
                text = self._fetch(source, force)
            except Exception as exc:
                errors.append({"source": name, "error": str(exc)})
                self.logger("catalog: %s failed: %s" % (name, exc))
                # Fall back to whatever is on disk, however old it is.
                text = self._read_cache(source.get("url", ""), float("inf")) if source.get("url") else None
                if not text:
                    continue
            if str(source.get("type", "m3u")).lower() == "xmltv":
                guide.update(parse_xmltv(text))
            else:
                items.extend(
                    parse_m3u(text, kind=source.get("kind", "live"), source=name)
                )
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
            counts[item.get("group") or "غير مصنّف"] = (
                counts.get(item.get("group") or "غير مصنّف", 0) + 1
            )
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
        """Collapse series episodes into one entry per show."""
        shows = {}
        for item in self.search(query, kind="series", limit=300000).get("items", []):
            title = series_title(item.get("name", "")) or item.get("group", "")
            show = shows.setdefault(
                title,
                {"name": title, "logo": item.get("logo", ""), "kind": "series",
                 "group": item.get("group", ""), "episodes": []},
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
