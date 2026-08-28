import json
import threading
import unittest
import urllib.error
import urllib.request

from smarttv.api import Api
from smarttv.config import load
from smarttv.server import RemoteServer


class ServerTestCase(unittest.TestCase):
    auth_token = ""

    def setUp(self):
        settings = load()
        settings["server"]["auth_token"] = self.auth_token
        self.api = Api(settings, demo=True)
        self.server = RemoteServer(("127.0.0.1", 0), self.api, auth_token=self.auth_token)
        self.thread = threading.Thread(
            target=self.server.serve_forever, kwargs={"poll_interval": 0.05}, daemon=True
        )
        self.thread.start()
        host, port = self.server.server_address
        self.base = "http://%s:%d" % (host, port)

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=3)
        self.api.shutdown()

    def request(self, method, path, body=None, headers=None):
        data = json.dumps(body).encode("utf-8") if body is not None else None
        request = urllib.request.Request(
            self.base + path, data=data, method=method, headers=headers or {}
        )
        if data:
            request.add_header("Content-Type", "application/json")
        try:
            with urllib.request.urlopen(request, timeout=5) as response:
                return response.status, response.read()
        except urllib.error.HTTPError as error:
            return error.code, error.read()


class ApiRouteTests(ServerTestCase):
    def test_status_returns_json_envelope(self):
        status, body = self.request("GET", "/api/status")
        payload = json.loads(body)
        self.assertEqual(status, 200)
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["data"]["backend"], "dummy")

    def test_post_command_reaches_the_tv(self):
        status, _ = self.request("POST", "/api/power", {"state": "on"})
        self.assertEqual(status, 200)
        self.assertEqual(self.api.registry.get("dummy").power_status(), "on")

    def test_unknown_route_is_404(self):
        status, body = self.request("GET", "/api/missing")
        self.assertEqual(status, 404)
        self.assertFalse(json.loads(body)["ok"])

    def test_bad_json_body_is_400(self):
        request = urllib.request.Request(
            self.base + "/api/power", data=b"{nope", method="POST"
        )
        request.add_header("Content-Type", "application/json")
        try:
            urllib.request.urlopen(request, timeout=5)
            self.fail("expected an error")
        except urllib.error.HTTPError as error:
            self.assertEqual(error.code, 400)

    def test_backend_error_is_502_not_a_crash(self):
        status, body = self.request("POST", "/api/app", {"app": "youtube"})
        self.assertEqual(status, 502)
        self.assertIn("error", json.loads(body))

    def test_get_query_parameters_become_the_payload(self):
        status, body = self.request("GET", "/api/config?x=1")
        self.assertEqual(status, 200)
        self.assertIn("shortcuts", json.loads(body)["data"])


class StaticFileTests(ServerTestCase):
    def test_index_is_served(self):
        status, body = self.request("GET", "/")
        self.assertEqual(status, 200)
        self.assertIn(b"<html", body.lower())

    def test_assets_are_served(self):
        for path in ("/app.js", "/style.css", "/manifest.json"):
            status, body = self.request("GET", path)
            self.assertEqual(status, 200, path)
            self.assertTrue(body)

    def test_directory_traversal_is_refused(self):
        for path in ("/../config.py", "/%2e%2e/config.py", "/../../etc/passwd"):
            status, _ = self.request("GET", path)
            self.assertIn(status, (400, 404), path)

    def test_unknown_file_is_404(self):
        status, _ = self.request("GET", "/nope.html")
        self.assertEqual(status, 404)

    def test_static_rejects_post(self):
        status, _ = self.request("POST", "/index.html", {})
        self.assertEqual(status, 405)


class AuthTests(ServerTestCase):
    auth_token = "s3cret"

    def test_api_requires_the_token(self):
        status, _ = self.request("GET", "/api/status")
        self.assertEqual(status, 401)

    def test_bearer_header_is_accepted(self):
        status, _ = self.request(
            "GET", "/api/status", headers={"Authorization": "Bearer s3cret"}
        )
        self.assertEqual(status, 200)

    def test_custom_header_is_accepted(self):
        status, _ = self.request("GET", "/api/status", headers={"X-Auth-Token": "s3cret"})
        self.assertEqual(status, 200)

    def test_query_token_is_accepted(self):
        status, _ = self.request("GET", "/api/status?token=s3cret")
        self.assertEqual(status, 200)

    def test_wrong_token_is_refused(self):
        status, _ = self.request("GET", "/api/status", headers={"X-Auth-Token": "nope"})
        self.assertEqual(status, 401)

    def test_the_remote_page_stays_public(self):
        # The UI has to load before it can send a token.
        status, _ = self.request("GET", "/")
        self.assertEqual(status, 200)


if __name__ == "__main__":
    unittest.main()
