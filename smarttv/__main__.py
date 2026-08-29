"""Command line entry point.

    python3 -m smarttv                       # serve the remote
    python3 -m smarttv --demo                # no TV needed, for development
    python3 -m smarttv --discover            # list TVs on the LAN
    python3 -m smarttv --cmd power on        # one-shot control from a script
    python3 -m smarttv --cmd search الجزيرة  # search the library
    python3 -m smarttv --import-ir magic.conf # teach it your own remote
"""

from __future__ import annotations

import argparse
import json
import socket
import sys
import time

from . import __version__, config as config_module, discovery
from .api import Api, ApiError
from .server import create_server


def log(message):
    sys.stderr.write("[%s] %s\n" % (time.strftime("%H:%M:%S"), message))
    sys.stderr.flush()


def local_ip():
    """Best-effort LAN address, for printing a URL you can actually open."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        sock.connect(("8.8.8.8", 80))
        return sock.getsockname()[0]
    except OSError:
        return "127.0.0.1"
    finally:
        sock.close()


COMMANDS = {
    "power": lambda api, args: api.dispatch(
        "POST", "/api/power", {"state": args[0] if args else "toggle"}
    ),
    "key": lambda api, args: api.dispatch("POST", "/api/key", {"key": args[0]}),
    "volume": lambda api, args: api.dispatch(
        "POST", "/api/volume", {"action": args[0] if args else "up"}
    ),
    "source": lambda api, args: api.dispatch(
        "POST", "/api/source", {"index": args[0] if args else 1}
    ),
    "cast": lambda api, args: api.dispatch("POST", "/api/cast", {"url": args[0]}),
    "app": lambda api, args: api.dispatch("POST", "/api/app", {"app": args[0]}),
    "raw": lambda api, args: api.dispatch("POST", "/api/raw", {"command": " ".join(args)}),
    "status": lambda api, args: api.dispatch("GET", "/api/status", {}),
    "sleep": lambda api, args: api.dispatch(
        "POST", "/api/sleep", {"minutes": float(args[0])} if args else {}
    ),
    "search": lambda api, args: api.dispatch(
        "GET", "/api/catalog", {"q": " ".join(args), "limit": 20}
    ),
    "refresh": lambda api, args: api.dispatch("POST", "/api/catalog/refresh", {}),
    "favorites": lambda api, args: api.dispatch("GET", "/api/favorites", {}),
    "ir-candidates": lambda api, args: api.dispatch("GET", "/api/ir/candidates", {}),
    "ir-test": lambda api, args: api.dispatch(
        "POST",
        "/api/ir/test",
        {"brand": args[0], "address": int(args[1]) if len(args) > 2 else None,
         "key": args[-1] if len(args) > 1 else "power"},
    ),
    "ir-save": lambda api, args: api.dispatch(
        "POST",
        "/api/ir/save",
        {"brand": args[0], "address": int(args[1]) if len(args) > 1 else None},
    ),
}


def build_parser():
    parser = argparse.ArgumentParser(
        prog="smarttv", description="Turn any HDMI TV into a smart TV."
    )
    parser.add_argument("-c", "--config", help="path to config.json")
    parser.add_argument("--host", help="override the listen address")
    parser.add_argument("--port", type=int, help="override the listen port")
    parser.add_argument(
        "--demo", action="store_true", help="use the in-memory TV (no hardware)"
    )
    parser.add_argument(
        "--discover", action="store_true", help="scan the LAN for TVs and exit"
    )
    parser.add_argument(
        "--import-ir",
        metavar="FILE",
        help="import a lircd.conf or irdb CSV for your remote, then exit",
    )
    parser.add_argument(
        "--cmd",
        nargs=argparse.REMAINDER,
        help="run one command and exit, e.g. --cmd power on",
    )
    parser.add_argument("--version", action="version", version=__version__)
    return parser


def main(argv=None):
    args = build_parser().parse_args(argv)

    if args.discover:
        print(json.dumps(discovery.scan(), ensure_ascii=False, indent=2))
        return 0

    try:
        settings = config_module.load(args.config)
    except (OSError, ValueError) as exc:
        log("cannot read config: %s" % exc)
        return 2
    if args.host:
        settings["server"]["host"] = args.host
    if args.port:
        settings["server"]["port"] = args.port

    api = Api(settings, demo=args.demo, logger=log)

    if args.import_ir:
        try:
            with open(args.import_ir, "r", encoding="utf-8", errors="replace") as handle:
                text = handle.read()
        except OSError as exc:
            log("cannot read %s: %s" % (args.import_ir, exc))
            api.shutdown()
            return 2
        try:
            result = api.dispatch("POST", "/api/ir/import", {"text": text})
        except ApiError as exc:
            log("import failed: %s" % exc)
            api.shutdown()
            return 1
        finally:
            pass
        print(json.dumps(result, ensure_ascii=False, indent=2))
        log("saved as brand %r - it is now the active remote" % result["brand"])
        api.shutdown()
        return 0

    if args.cmd:
        name, cmd_args = args.cmd[0], args.cmd[1:]
        handler = COMMANDS.get(name)
        if handler is None:
            log("unknown command %r; try one of: %s" % (name, ", ".join(sorted(COMMANDS))))
            return 2
        try:
            print(json.dumps(handler(api, cmd_args), ensure_ascii=False, indent=2))
        except ApiError as exc:
            log("error: %s" % exc)
            return 1
        except IndexError:
            log("command %r needs an argument" % name)
            return 2
        finally:
            api.shutdown()
        return 0

    api.start()
    server = create_server(settings, api, logger=log)
    host, port = server.server_address
    log("smarttv %s listening on http://%s:%d" % (__version__, host, port))
    log("open the remote at http://%s:%d" % (local_ip(), port))
    active = api.registry.active()
    log("active backend: %s" % (active.name if active else "none - check your config"))
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        log("shutting down")
    finally:
        server.shutdown()
        server.server_close()
        api.shutdown()
    return 0


if __name__ == "__main__":
    sys.exit(main())
