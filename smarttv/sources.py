"""Where the library's items come from.

Four source protocols, all of them open and all of them supplied by you:

  * ``m3u``     - the playlist format everything speaks
  * ``xmltv``   - the matching programme guide
  * ``xtream``  - the Xtream Codes API most IPTV subscriptions are sold as
  * ``enigma2`` - a satellite receiver's own bouquets, read over OpenWebif

Every loader takes a ``fetch(target) -> text`` callable so the caller owns
caching, timeouts and credentials - and so all of this is testable without
a network.
"""

from __future__ import annotations

import json
import re
import time
import urllib.parse
import xml.etree.ElementTree as ElementTree

ATTRIBUTE_RE = re.compile(r'([\w-]+)="([^"]*)"')

# Enigma2 uses fake services as separators inside bouquets.
MARKER_PREFIXES = ("1:64:", "1:832:", "1:320:")


# --- M3U ------------------------------------------------------------------


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


# --- XMLTV ----------------------------------------------------------------


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
        guide.setdefault(channel, []).append(
            {
                "title": (element.findtext("title") or "").strip(),
                "description": (element.findtext("desc") or "").strip(),
                "start": _xmltv_time(element.get("start")),
                "stop": _xmltv_time(element.get("stop")),
            }
        )
    for programmes in guide.values():
        programmes.sort(key=lambda item: item.get("start") or 0)
    return guide


# --- Xtream Codes ---------------------------------------------------------


def xtream_api_url(source, action, **params):
    base = str(source.get("url", "")).rstrip("/")
    query = {
        "username": source.get("username", ""),
        "password": source.get("password", ""),
        "action": action,
    }
    query.update({key: value for key, value in params.items() if value is not None})
    return "%s/player_api.php?%s" % (base, urllib.parse.urlencode(query))


def xtream_stream_url(source, section, stream_id, extension=None):
    base = str(source.get("url", "")).rstrip("/")
    if extension is None:
        extension = "ts" if section == "live" else "mp4"
    return "%s/%s/%s/%s/%s.%s" % (
        base,
        section,
        source.get("username", ""),
        source.get("password", ""),
        stream_id,
        extension,
    )


def _load_json(fetch, url):
    text = fetch(url)
    try:
        payload = json.loads(text)
    except ValueError as exc:
        raise ValueError("the provider did not answer with JSON") from exc
    if isinstance(payload, dict) and payload.get("user_info", {}).get("auth") == 0:
        raise ValueError("the provider rejected these credentials")
    return payload


def _category_names(fetch, source, action):
    try:
        categories = _load_json(fetch, xtream_api_url(source, action))
    except (ValueError, OSError):
        return {}
    return {
        str(entry.get("category_id")): entry.get("category_name", "")
        for entry in categories or []
        if isinstance(entry, dict)
    }


def load_xtream(source, fetch):
    """Live channels, films and series from an Xtream Codes subscription."""
    name = source.get("name") or "xtream"
    wanted = [str(kind) for kind in source.get("kinds", ["live", "movies", "series"])]
    live_extension = source.get("live_extension", "ts")
    items = []

    if "live" in wanted:
        groups = _category_names(fetch, source, "get_live_categories")
        for entry in _load_json(fetch, xtream_api_url(source, "get_live_streams")) or []:
            items.append(
                {
                    "name": entry.get("name", ""),
                    "logo": entry.get("stream_icon", ""),
                    "tvg_id": entry.get("epg_channel_id", "") or "",
                    "group": groups.get(str(entry.get("category_id")), ""),
                    "kind": "live",
                    "source": name,
                    "url": xtream_stream_url(
                        source, "live", entry.get("stream_id"), live_extension
                    ),
                }
            )

    if "movies" in wanted:
        groups = _category_names(fetch, source, "get_vod_categories")
        for entry in _load_json(fetch, xtream_api_url(source, "get_vod_streams")) or []:
            items.append(
                {
                    "name": entry.get("name", ""),
                    "logo": entry.get("stream_icon", "") or entry.get("cover", ""),
                    "tvg_id": "",
                    "group": groups.get(str(entry.get("category_id")), ""),
                    "kind": "movies",
                    "source": name,
                    "url": xtream_stream_url(
                        source,
                        "movie",
                        entry.get("stream_id"),
                        entry.get("container_extension"),
                    ),
                }
            )

    if "series" in wanted:
        groups = _category_names(fetch, source, "get_series_categories")
        for entry in _load_json(fetch, xtream_api_url(source, "get_series")) or []:
            items.append(
                {
                    "name": entry.get("name", ""),
                    "logo": entry.get("cover", ""),
                    "tvg_id": "",
                    "group": groups.get(str(entry.get("category_id")), ""),
                    "kind": "series",
                    "source": name,
                    # A series has no stream of its own; episodes are
                    # fetched on demand, because a big subscription would
                    # otherwise mean hundreds of requests up front.
                    "url": "",
                    "series_id": entry.get("series_id"),
                }
            )
    return items


def load_xtream_episodes(source, fetch, series_id):
    """The episodes of one series, newest API shape first."""
    payload = _load_json(
        fetch, xtream_api_url(source, "get_series_info", series_id=series_id)
    )
    if not isinstance(payload, dict):
        # Some panels answer with an empty list for an unknown series.
        return []
    seasons = payload.get("episodes") or {}
    episodes = []
    if isinstance(seasons, list):
        seasons = {"1": seasons}
    for season, entries in sorted(seasons.items(), key=lambda pair: str(pair[0])):
        for entry in entries or []:
            episodes.append(
                {
                    "name": entry.get("title") or "الحلقة %s" % entry.get("episode_num"),
                    "url": xtream_stream_url(
                        source, "series", entry.get("id"), entry.get("container_extension")
                    ),
                    "season": int(entry.get("season") or season or 1),
                    "episode": int(entry.get("episode_num") or 0),
                }
            )
    episodes.sort(key=lambda entry: (entry["season"], entry["episode"]))
    return episodes


# --- numbered channel lists (devices driven by their remote) --------------


def load_channels(source, fetch):
    """A channel list for a box that only understands its own remote.

    Each item plays by dialling its number on the remote, so a receiver
    with no API still gets a searchable channel grid on the phone.
    """
    from .macros import digits

    name = source.get("name") or "channels"
    confirm = source.get("confirm", "select")
    entries = source.get("items")
    if not entries:
        text = fetch(source_target(source))
        stripped = (text or "").lstrip()
        if stripped.startswith("["):
            entries = json.loads(text)
        else:
            entries = []
            for line in (text or "").splitlines():
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                parts = [part.strip() for part in line.split(",")]
                if len(parts) < 2:
                    continue
                entries.append(
                    {
                        "name": parts[0],
                        "number": parts[1],
                        "group": parts[2] if len(parts) > 2 else "",
                    }
                )
    items = []
    for entry in entries or []:
        number = str(entry.get("number", "")).strip()
        if not number.isdigit():
            continue
        steps = digits(number, confirm)
        items.append(
            {
                "name": entry.get("name") or ("قناة %s" % number),
                "logo": entry.get("logo", ""),
                "tvg_id": entry.get("tvg_id", ""),
                "group": entry.get("group", "") or source.get("group", ""),
                "kind": source.get("kind", "live"),
                "source": name,
                "number": number,
                # Played by pressing buttons, not by streaming anything.
                "url": "macro:" + ",".join(steps),
            }
        )
    return items


# --- Enigma2 receiver -----------------------------------------------------


def load_enigma2(source, fetch, client=None):
    """The receiver's own bouquets, as items the phone can zap or stream."""
    from .openwebif import OpenWebif

    client = client or OpenWebif(source)
    name = source.get("name") or "enigma2"
    payload = json.loads(fetch(client.build_url("api/getallservices")))
    items = []
    for bouquet in (payload or {}).get("services") or []:
        group = bouquet.get("servicename", "")
        for service in bouquet.get("subservices") or []:
            reference = service.get("servicereference", "")
            if not reference or reference.startswith(MARKER_PREFIXES):
                continue
            items.append(
                {
                    "name": service.get("servicename", ""),
                    "logo": "",
                    "tvg_id": reference,
                    "group": group,
                    "kind": "live",
                    "source": name,
                    # Streamable by any player, and recognised by the
                    # Enigma2 player as "zap the tuner to this instead".
                    "url": client.stream_url(reference),
                    "sref": reference,
                }
            )
    return items


# --- dispatch -------------------------------------------------------------


def source_target(source):
    return source.get("url") or source.get("path") or ""


def load_source(source, fetch):
    """Load one configured source into ``{"items": [...], "guide": {...}}``."""
    kind = str(source.get("type", "m3u")).lower()
    if kind in ("m3u", "m3u8", "playlist", "xmltv") and not source_target(source):
        raise ValueError("source needs a url or a path")
    if kind in ("channels", "numbers") and not source.get("items") and not source_target(source):
        raise ValueError("a channel list needs items, a url or a path")
    if kind == "xmltv":
        return {"items": [], "guide": parse_xmltv(fetch(source_target(source)))}
    if kind == "xtream":
        return {"items": load_xtream(source, fetch), "guide": {}}
    if kind == "enigma2":
        return {"items": load_enigma2(source, fetch), "guide": {}}
    if kind in ("channels", "numbers"):
        return {"items": load_channels(source, fetch), "guide": {}}
    if kind in ("m3u", "m3u8", "playlist"):
        return {
            "items": parse_m3u(
                fetch(source_target(source)),
                kind=source.get("kind", "live"),
                source=source.get("name") or source_target(source),
            ),
            "guide": {},
        }
    raise ValueError("unknown source type: %r" % (kind,))
