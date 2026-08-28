"""SSDP discovery, to find TVs and casting targets already on the LAN.

Useful before you know your TV's IP: run ``--discover`` and it lists the
DIAL/UPnP devices that answer, with their friendly names.
"""

from __future__ import annotations

import re
import socket
import urllib.request

SSDP_ADDR = "239.255.255.250"
SSDP_PORT = 1900
DEFAULT_TARGETS = (
    "urn:dial-multiscreen-org:service:dial:1",
    "urn:schemas-upnp-org:device:MediaRenderer:1",
    "upnp:rootdevice",
)


def build_msearch(target, mx=2):
    return (
        "M-SEARCH * HTTP/1.1\r\n"
        "HOST: %s:%d\r\n"
        'MAN: "ssdp:discover"\r\n'
        "MX: %d\r\n"
        "ST: %s\r\n\r\n" % (SSDP_ADDR, SSDP_PORT, mx, target)
    )


def parse_response(payload):
    """Parse an SSDP reply into a lowercase-keyed header dict."""
    headers = {}
    lines = payload.replace("\r\n", "\n").split("\n")
    for line in lines[1:]:
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        key = key.strip().lower()
        if key:
            headers[key] = value.strip()
    return headers


def friendly_name(location, timeout=2):
    """Fetch a device description XML and pull out its friendlyName."""
    try:
        with urllib.request.urlopen(location, timeout=timeout) as response:
            body = response.read(65536).decode("utf-8", "replace")
    except Exception:
        return None
    match = re.search(r"<friendlyName>(.*?)</friendlyName>", body, re.S | re.I)
    return match.group(1).strip() if match else None


def scan(timeout=3, targets=DEFAULT_TARGETS, resolve_names=True):
    """Broadcast M-SEARCH probes and collect the answers, keyed by host."""
    devices = {}
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
    sock.settimeout(timeout)
    try:
        for target in targets:
            try:
                sock.sendto(build_msearch(target).encode("utf-8"), (SSDP_ADDR, SSDP_PORT))
            except OSError:
                continue
        import time

        deadline = time.time() + timeout
        while time.time() < deadline:
            sock.settimeout(max(0.2, deadline - time.time()))
            try:
                payload, addr = sock.recvfrom(8192)
            except socket.timeout:
                break
            except OSError:
                break
            headers = parse_response(payload.decode("utf-8", "replace"))
            host = addr[0]
            entry = devices.setdefault(
                host,
                {"host": host, "services": [], "server": "", "location": "", "name": None},
            )
            entry["server"] = entry["server"] or headers.get("server", "")
            entry["location"] = entry["location"] or headers.get("location", "")
            service = headers.get("st") or headers.get("nt")
            if service and service not in entry["services"]:
                entry["services"].append(service)
    finally:
        sock.close()
    if resolve_names:
        for entry in devices.values():
            if entry["location"]:
                entry["name"] = friendly_name(entry["location"])
    return sorted(devices.values(), key=lambda item: item["host"])
