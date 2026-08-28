"""Wake-on-LAN magic packets.

Network backends can only talk to a TV that is awake enough to answer;
a magic packet is how a fully powered-off Samsung/LG comes back.
"""

from __future__ import annotations

import re
import socket

_MAC_RE = re.compile(r"^[0-9a-fA-F]{2}([:-]?)(?:[0-9a-fA-F]{2}\1){4}[0-9a-fA-F]{2}$")


def build_packet(mac):
    """Build the 102-byte magic packet for ``mac``."""
    if not _MAC_RE.match(mac or ""):
        raise ValueError("invalid MAC address: %r" % (mac,))
    raw = bytes.fromhex(re.sub(r"[:-]", "", mac))
    return b"\xff" * 6 + raw * 16


def send(mac, broadcast="255.255.255.255", port=9):
    """Send a magic packet; returns the number of bytes written."""
    packet = build_packet(mac)
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        return sock.sendto(packet, (broadcast, port))
