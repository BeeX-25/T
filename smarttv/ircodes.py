"""Infrared code generation - control a TV from a phone's IR blaster.

Many phones (most Xiaomi/Redmi/Poco, plenty of Huawei and older Samsung
models) have an IR LED, which makes them a complete TV remote with no
hardware at all.  Termux exposes it as ``termux-infrared-transmit``, which
wants a carrier frequency and a list of on/off durations in microseconds -
exactly what the encoders here produce.

Each protocol is implemented from its published timing, so a brand that is
missing from ``BRANDS`` can still be driven by giving its protocol,
address and command bytes in the config.
"""

from __future__ import annotations

# --- protocol encoders ----------------------------------------------------


def _lsb_bits(value, width=8):
    return [(value >> index) & 1 for index in range(width)]


def _pulse_bits(bits, mark, zero_space, one_space):
    durations = []
    for bit in bits:
        durations.append(mark)
        durations.append(one_space if bit else zero_space)
    return durations


def encode_nec(address, command):
    """NEC: 9ms header, address + inverse, command + inverse, LSB first.

    Used by LG, Hisense, TCL, Toshiba and most no-name sets.
    """
    bits = (
        _lsb_bits(address & 0xFF)
        + _lsb_bits(~address & 0xFF)
        + _lsb_bits(command & 0xFF)
        + _lsb_bits(~command & 0xFF)
    )
    return [9000, 4500] + _pulse_bits(bits, 560, 560, 1690) + [560]


def encode_samsung(address, command):
    """Samsung32: NEC timings, but a 4.5ms header and a repeated address."""
    bits = (
        _lsb_bits(address & 0xFF)
        + _lsb_bits(address & 0xFF)
        + _lsb_bits(command & 0xFF)
        + _lsb_bits(~command & 0xFF)
    )
    return [4500, 4500] + _pulse_bits(bits, 560, 560, 1690) + [560]


def encode_sirc(address, command, bits=12):
    """Sony SIRC: 2.4ms header, command first, then address. 40kHz carrier."""
    command_width = 7
    address_width = bits - command_width
    payload = _lsb_bits(command, command_width) + _lsb_bits(address, address_width)
    durations = [2400, 600]
    for bit in payload:
        durations.append(1200 if bit else 600)
        durations.append(600)
    return durations


def encode_rc5(address, command, toggle=0):
    """Philips RC5: Manchester coded, 36kHz, 889us half-bits.

    Manchester means level changes mid-bit, so adjacent halves of the same
    level have to be merged into one duration before transmitting.
    """
    payload = [1, 1 if command < 0x40 else 0, toggle & 1]
    payload += [(address >> index) & 1 for index in range(4, -1, -1)]
    payload += [(command >> index) & 1 for index in range(5, -1, -1)]
    levels = []
    for bit in payload:
        # 1 is space-then-mark, 0 is mark-then-space.
        levels += [0, 1] if bit else [1, 0]
    # Transmission has to start on a mark: drop the leading idle half-bit.
    while levels and levels[0] == 0:
        levels.pop(0)
    durations = []
    current = 1
    run = 0
    for level in levels:
        if level == current:
            run += 1
        else:
            durations.append(run * 889)
            current = level
            run = 1
    durations.append(run * 889)
    return durations


PROTOCOLS = {
    "nec": (encode_nec, 38000),
    "samsung": (encode_samsung, 38000),
    "sirc": (encode_sirc, 40000),
    "rc5": (encode_rc5, 36000),
}


# --- brand tables ---------------------------------------------------------
# Published codes for the buttons a remote actually needs.  Sets vary
# between model years; when a button does nothing, read the real code with
# an IR receiver (or LIRC) and drop it into config as a custom brand.

BRANDS = {
    "samsung": {
        "protocol": "samsung",
        "address": 0x07,
        "keys": {
            "power": 0x02, "power_on": 0x99, "power_off": 0x98,
            "volume_up": 0x07, "volume_down": 0x0B, "mute": 0x0F,
            "channel_up": 0x12, "channel_down": 0x10,
            "up": 0x60, "down": 0x61, "left": 0x65, "right": 0x62,
            "select": 0x68, "back": 0x58, "exit": 0x2D, "menu": 0x1A,
            "home": 0x79, "source": 0x01, "info": 0x1F,
            "play": 0x47, "pause": 0x4A, "stop": 0x46,
            "num0": 0x11, "num1": 0x04, "num2": 0x05, "num3": 0x06,
            "num4": 0x08, "num5": 0x09, "num6": 0x0A, "num7": 0x0C,
            "num8": 0x0D, "num9": 0x0E,
        },
    },
    "lg": {
        "protocol": "nec",
        "address": 0x04,
        "keys": {
            "power": 0x08, "power_on": 0x1E, "power_off": 0x1F,
            "volume_up": 0x02, "volume_down": 0x03, "mute": 0x09,
            "channel_up": 0x00, "channel_down": 0x01,
            "up": 0x40, "down": 0x41, "left": 0x07, "right": 0x06,
            "select": 0x44, "back": 0x28, "exit": 0x5B, "menu": 0x43,
            "home": 0x7C, "source": 0x0B, "info": 0x55,
            "num0": 0x10, "num1": 0x11, "num2": 0x12, "num3": 0x13,
            "num4": 0x14, "num5": 0x15, "num6": 0x16, "num7": 0x17,
            "num8": 0x18, "num9": 0x19,
        },
    },
    "sony": {
        "protocol": "sirc",
        "address": 0x01,
        "keys": {
            "power": 0x15, "power_on": 0x2E, "power_off": 0x2F,
            "volume_up": 0x12, "volume_down": 0x13, "mute": 0x14,
            "channel_up": 0x10, "channel_down": 0x11,
            "up": 0x74, "down": 0x75, "left": 0x34, "right": 0x33,
            "select": 0x65, "back": 0x63, "menu": 0x60, "home": 0x60,
            "source": 0x25, "info": 0x3A,
            "num0": 0x09, "num1": 0x00, "num2": 0x01, "num3": 0x02,
            "num4": 0x03, "num5": 0x04, "num6": 0x05, "num7": 0x06,
            "num8": 0x07, "num9": 0x08,
        },
    },
    "philips": {
        "protocol": "rc5",
        "address": 0x00,
        "keys": {
            "power": 0x0C,
            "volume_up": 0x10, "volume_down": 0x11, "mute": 0x0D,
            "channel_up": 0x20, "channel_down": 0x21,
            "up": 0x10, "down": 0x11, "left": 0x15, "right": 0x16,
            "select": 0x17, "back": 0x0A, "menu": 0x12, "info": 0x0F,
            "num0": 0x00, "num1": 0x01, "num2": 0x02, "num3": 0x03,
            "num4": 0x04, "num5": 0x05, "num6": 0x06, "num7": 0x07,
            "num8": 0x08, "num9": 0x09,
        },
    },
    # NEC with address 0 covers a surprising number of budget sets.
    "generic_nec": {
        "protocol": "nec",
        "address": 0x00,
        "keys": {
            "power": 0x45, "volume_up": 0x46, "volume_down": 0x47, "mute": 0x44,
            "channel_up": 0x40, "channel_down": 0x41,
            "up": 0x18, "down": 0x52, "left": 0x08, "right": 0x5A,
            "select": 0x1C, "back": 0x4A, "menu": 0x42,
            "num0": 0x16, "num1": 0x0C, "num2": 0x19, "num3": 0x0D,
            "num4": 0x0E, "num5": 0x1B, "num6": 0x11, "num7": 0x15,
            "num8": 0x09, "num9": 0x07,
        },
    },
}


def pattern_for(brand, key, brands=None, address=None):
    """Return ``(frequency, durations)`` for one button of one brand."""
    table = (brands or BRANDS).get(brand)
    if table is None:
        raise KeyError("unknown IR brand: %r" % (brand,))
    code = table["keys"].get(key)
    if code is None:
        raise KeyError("brand %r has no code for %r" % (brand, key))
    encoder, frequency = PROTOCOLS[table["protocol"]]
    return (
        int(table.get("frequency", frequency)),
        encoder(table["address"] if address is None else address, code),
    )
