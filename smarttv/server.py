"""Dependency-free HTTP server: JSON API plus the phone remote.

``http.server`` is deliberate.  The whole point of this project is that it
runs on whatever old hardware is lying around, so requiring pip installs to
serve one HTML page would be a step backwards.
"""

from __future__ import annotations

import hmac
import json
import mimetypes
import os
import posixpath
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

from .api import ApiError

WEB_ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "web")
MAX_BODY = 1 << 20  # 1 MiB is plenty for a remote control


class RemoteHandler(BaseHTTPRequestHandler):
    server_version = "SmartTVBridge"
    protocol_version = "HTTP/1.1"

    # -- helpers ----------------------------------------------------------
    @property
    def api(self):
        return self.server.api

    @property
    def auth_token(self):
        return self.server.auth_token

    def log_message(self, fmt, *args):
        self.server.logger("%s %s" % (self.address_string(), fmt % args))

    def _send(self, status, body, content_type="application/json; charset=utf-8", extra=None):
        if isinstance(body, str):
            body = body.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        for key, value in (extra or {}).items():
            self.send_header(key, value)
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)

    def _send_json(self, status, payload):
        self._send(status, json.dumps(payload, ensure_ascii=False))

    def _authorised(self, query):
        if not self.auth_token:
            return True
        header = self.headers.get("Authorization", "")
        candidate = ""
        if header.lower().startswith("bearer "):
            candidate = header[7:].strip()
        candidate = candidate or self.headers.get("X-Auth-Token", "")
        candidate = candidate or (query.get("token", [""])[0])
        return hmac.compare_digest(candidate, self.auth_token)

    def _read_body(self):
        length = int(self.headers.get("Content-Length") or 0)
        if length <= 0:
            return {}
        if length > MAX_BODY:
            raise ApiError("request body too large", status=413)
        raw = self.rfile.read(length)
        try:
            payload = json.loads(raw.decode("utf-8"))
        except ValueError as exc:
            raise ApiError("invalid JSON body: %s" % exc) from exc
        if not isinstance(payload, dict):
            raise ApiError("JSON body must be an object")
        return payload

    # -- routing ----------------------------------------------------------
    def _handle(self):
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/") or "/"
        query = parse_qs(parsed.query)
        if path.startswith("/api"):
            return self._handle_api(path, query)
        if self.command not in ("GET", "HEAD"):
            return self._send_json(405, {"ok": False, "error": "method not allowed"})
        return self._serve_static(path)

    def _handle_api(self, path, query):
        if not self._authorised(query):
            return self._send_json(401, {"ok": False, "error": "unauthorised"})
        try:
            payload = self._read_body()
            if self.command == "GET":
                payload = {key: values[0] for key, values in query.items()}
            data = self.api.dispatch(self.command, path, payload)
        except ApiError as exc:
            return self._send_json(exc.status, {"ok": False, "error": str(exc)})
        except Exception as exc:  # never leak a traceback to the remote
            self.server.logger("unhandled error on %s: %r" % (path, exc))
            return self._send_json(500, {"ok": False, "error": "internal error"})
        return self._send_json(200, {"ok": True, "data": data})

    def _serve_static(self, path):
        if path == "/":
            path = "/index.html"
        # Normalise first, then join: no ".." can escape WEB_ROOT.
        relative = posixpath.normpath(path).lstrip("/")
        target = os.path.normpath(os.path.join(WEB_ROOT, relative))
        if not target.startswith(WEB_ROOT) or not os.path.isfile(target):
            return self._send(404, "not found", "text/plain; charset=utf-8")
        content_type, _ = mimetypes.guess_type(target)
        with open(target, "rb") as handle:
            body = handle.read()
        self._send(200, body, content_type or "application/octet-stream")

    def do_GET(self):
        self._handle()

    def do_HEAD(self):
        self._handle()

    def do_POST(self):
        self._handle()

    def do_DELETE(self):
        self._handle()


class RemoteServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True

    def __init__(self, address, api, auth_token="", logger=None):
        super().__init__(address, RemoteHandler)
        self.api = api
        self.auth_token = auth_token or ""
        self.logger = logger or (lambda message: None)


def create_server(config, api, logger=None):
    server_config = config["server"]
    return RemoteServer(
        (server_config.get("host", "0.0.0.0"), int(server_config.get("port", 8099))),
        api,
        auth_token=server_config.get("auth_token", ""),
        logger=logger,
    )
