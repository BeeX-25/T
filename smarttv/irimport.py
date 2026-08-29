"""Import IR code sets for remotes this project has never heard of.

Cheap satellite receivers (the Sunplus 1506 / GX6605S family sold as
Magic, Star, New World and a hundred other names) run closed firmware with
no API at all, so infrared is the only way to drive them - and their codes
are in nobody's table.  They are, however, catalogued: LIRC config files
and the irdb database cover thousands of remotes.

Both formats are parsed here into the same brand table the IR backend
already understands, so an imported remote behaves exactly like a built-in
one.
"""

from __future__ import annotations

import csv
import io
import re

from . import keys as keymap

# irdb protocol names mapped onto the encoders in ircodes.
IRDB_PROTOCOLS = {
    "nec": "nec", "nec1": "nec", "nec2": "nec", "necx1": "nec", "necx2": "nec",
    "nec1-f16": "nec", "necx": "nec",
    "rc5": "rc5", "rc5x": "rc5",
    "sony12": "sirc", "sony15": "sirc", "sony20": "sirc", "sirc": "sirc",
    "samsung20": "samsung", "samsung36": "samsung", "samsung": "samsung",
}

# LIRC (and irdb) spell buttons their own way.
NAME_ALIASES = {
    "volumeup": "volume_up", "volup": "volume_up", "vol_up": "volume_up",
    "volumedown": "volume_down", "voldown": "volume_down", "vol_down": "volume_down",
    "channelup": "channel_up", "chup": "channel_up", "programup": "channel_up",
    "channeldown": "channel_down", "chdown": "channel_down",
    "programdown": "channel_down",
    "ok": "select", "enter": "select", "okay": "select",
    "return": "back", "prev": "back", "previous": "back",
    "playpause": "play_pause", "play_pause": "play_pause",
    "fastforward": "fast_forward", "forward": "fast_forward", "ff": "fast_forward",
    "rewind": "rewind", "rew": "rewind",
    "poweron": "power_on", "poweroff": "power_off", "power2": "power",
    "input": "source", "tvav": "source", "av": "source",
    "guide": "epg", "epg": "epg", "teletext": "text",
    "0": "num0", "1": "num1", "2": "num2", "3": "num3", "4": "num4",
    "5": "num5", "6": "num6", "7": "num7", "8": "num8", "9": "num9",
}


def normalize_key(name):
    """Turn KEY_VOLUMEUP / VolumeUp / vol+ into our canonical button name."""
    text = str(name or "").strip()
    if text.upper().startswith("KEY_"):
        text = text[4:]
    text = text.lower().replace("-", "_").replace(" ", "_")
    text = NAME_ALIASES.get(text, text)
    text = NAME_ALIASES.get(text.replace("_", ""), text)
    return keymap.normalize(text)


def _to_int(value):
    text = str(value).strip()
    return int(text, 16) if text.lower().startswith("0x") else int(text)


# --- irdb CSV -------------------------------------------------------------


def parse_irdb_csv(text, name="imported"):
    """Parse an irdb CSV export into one brand table.

    irdb rows are ``functionname,protocol,device,subdevice,function``; the
    device column is the address every button shares.
    """
    reader = csv.DictReader(io.StringIO(text or ""))
    protocol = None
    address = None
    codes = {}
    skipped = []
    for row in reader:
        if not row:
            continue
        raw_name = (row.get("functionname") or "").strip()
        key = normalize_key(raw_name)
        if not key:
            skipped.append(raw_name)
            continue
        candidate = IRDB_PROTOCOLS.get((row.get("protocol") or "").strip().lower())
        if candidate is None:
            skipped.append(raw_name)
            continue
        try:
            device = _to_int(row.get("device"))
            function = _to_int(row.get("function"))
        except (TypeError, ValueError):
            skipped.append(raw_name)
            continue
        # Mixed protocols in one file would need one table each; the first
        # one wins and the rest are reported as skipped.
        if protocol is None:
            protocol, address = candidate, device
        if candidate != protocol or device != address:
            skipped.append(raw_name)
            continue
        codes[key] = function
    if not codes:
        raise ValueError("no usable rows in this irdb file")
    return {
        "name": name,
        "protocol": protocol,
        "address": address,
        "keys": codes,
        "skipped": skipped,
    }


# --- LIRC ----------------------------------------------------------------

_NUMBER_RE = re.compile(r"0x[0-9a-fA-F]+|\d+")


def _bits(value, width):
    """MSB-first bits, which is how LIRC writes its codes."""
    return [(value >> index) & 1 for index in range(width - 1, -1, -1)]


def _build_space_encoded(config, code):
    """Rebuild one button's pulse train from a LIRC SPACE_ENC remote."""
    header = config.get("header") or []
    one = config.get("one") or [560, 1690]
    zero = config.get("zero") or [560, 560]
    bit_stream = []
    if config.get("pre_data_bits"):
        bit_stream += _bits(config.get("pre_data", 0), config["pre_data_bits"])
    bit_stream += _bits(code, config.get("bits", 16))
    if config.get("post_data_bits"):
        bit_stream += _bits(config.get("post_data", 0), config["post_data_bits"])
    durations = list(header)
    for bit in bit_stream:
        durations += list(one if bit else zero)
    if config.get("ptrail"):
        durations.append(config["ptrail"])
    return [int(value) for value in durations]


def parse_lircd_conf(text, name=None):
    """Parse a lircd.conf remote into a brand table of raw pulse trains.

    Raw trains rather than protocol+address: a LIRC file already encodes
    the exact timing of the original remote, and reproducing it verbatim
    is more faithful than guessing which named protocol it is.
    """
    config = {"frequency": 38000}
    codes = {}
    in_codes = False
    in_raw = False
    raw_name = None
    raw_values = []
    found_remote = False

    def flush_raw():
        if raw_name and raw_values:
            key = normalize_key(raw_name)
            if key:
                codes[key] = [int(value) for value in raw_values]

    for raw_line in (text or "").splitlines():
        line = raw_line.split("#", 1)[0].strip()
        if not line:
            continue
        lowered = line.lower()
        if lowered.startswith("begin remote"):
            found_remote = True
            continue
        if lowered.startswith("begin raw_codes"):
            in_raw, raw_name, raw_values = True, None, []
            continue
        if lowered.startswith("end raw_codes"):
            flush_raw()
            in_raw, raw_name, raw_values = False, None, []
            continue
        if lowered.startswith("begin codes"):
            in_codes = True
            continue
        if lowered.startswith("end codes"):
            in_codes = False
            continue
        if lowered.startswith("end remote"):
            break

        if in_raw:
            if lowered.startswith("name "):
                flush_raw()
                raw_name = line.split(None, 1)[1].strip()
                raw_values = []
            else:
                raw_values += [int(value) for value in _NUMBER_RE.findall(line)]
            continue

        if in_codes:
            parts = line.split()
            if len(parts) >= 2:
                key = normalize_key(parts[0])
                if key:
                    try:
                        codes[key] = _to_int(parts[1])
                    except ValueError:
                        continue
            continue

        parts = line.split()
        field = parts[0].lower()
        values = []
        for part in parts[1:]:
            try:
                values.append(_to_int(part))
            except ValueError:
                pass
        if field in ("header", "one", "zero", "three", "two"):
            config[field] = values
        elif field in (
            "bits", "pre_data_bits", "pre_data", "post_data_bits", "post_data",
            "ptrail", "frequency", "gap", "toggle_bit_mask",
        ):
            if values:
                config[field] = values[0]
        elif field == "name" and len(parts) > 1 and name is None:
            name = parts[1]
        elif field == "flags":
            config["flags"] = parts[1] if len(parts) > 1 else ""

    if not found_remote:
        raise ValueError("this does not look like a lircd.conf file")
    if not codes:
        raise ValueError("no buttons found in this lircd.conf")

    is_raw = "RAW_CODES" in str(config.get("flags", "")).upper()
    table = {
        "name": name or "imported",
        "protocol": "raw",
        "frequency": int(config.get("frequency", 38000)),
        "keys": {},
    }
    for key, code in codes.items():
        table["keys"][key] = (
            list(code) if is_raw or isinstance(code, list)
            else _build_space_encoded(config, code)
        )
    return table


def load(text, name=None):
    """Import either format - whichever the file turns out to be."""
    if "begin remote" in (text or "").lower():
        return parse_lircd_conf(text, name)
    return parse_irdb_csv(text, name or "imported")
