"""Self-test for the local HTTP server: routes, the token gate and error codes.

The real server is started on a free port and driven over real HTTP, with the
document file and the settings pointing at a throwaway directory.
"""

from __future__ import annotations

import contextlib
import http.server
import json
import socketserver
import sys
import tempfile
import threading
import urllib.error
import urllib.request
from pathlib import Path

from cvboreout import model, server

from .harness import check, private_config, summary

PAGE = (
    '<!doctype html><html><head><title>Stelle</title><script>var t = 1;</script></head>'
    '<body><h1>Testingenieur (m/w/d)</h1><p>F&uuml;r unser Team.</p></body></html>'
).encode()


@contextlib.contextmanager
def _job_board():
    """A stand-in for a job portal, so the URL import needs no internet."""

    class Handler(http.server.BaseHTTPRequestHandler):
        def log_message(self, *_):
            pass

        def do_GET(self):
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(PAGE)))
            self.end_headers()
            self.wfile.write(PAGE)

    board = socketserver.TCPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=board.serve_forever, daemon=True).start()
    try:
        yield f"http://127.0.0.1:{board.server_address[1]}/stelle"
    finally:
        board.shutdown()
        board.server_close()


class Client:
    """Talks to the running application the way the frontend does."""

    def __init__(self, address: str, token: str):
        self.address = address.split("/?")[0]
        self.token = token

    def raw(self, path, body=None, token=True, method=None):
        data = json.dumps(body).encode() if body is not None else None
        request = urllib.request.Request(self.address + path, data=data,
                                         method=method or ("POST" if data else "GET"))
        request.add_header("Content-Type", "application/json")
        if token:
            request.add_header("X-Token", self.token)
        try:
            with urllib.request.urlopen(request, timeout=30) as answer:
                return answer.status, answer.read()
        except urllib.error.HTTPError as error:
            return error.code, error.read()

    def json(self, path, body=None, token=True):
        code, raw = self.raw(path, body, token)
        return code, json.loads(raw or b"{}")


def main() -> int:
    failures = 0

    with private_config(), tempfile.TemporaryDirectory() as folder:
        document = Path(folder) / "resume.json"
        state = server.State(document)
        state.data = model.normalize(model.SAMPLE)
        running, address = server.serve(state, port=0)
        client = Client(address, state.token)

        try:
            print("Frontend delivery")
            code, raw = client.raw("/", token=False)
            page = raw.decode()
            failures += not check(code == 200 and "<title>CVBoreout</title>" in page,
                                  "index page served")
            failures += not check(state.token in page and "__TOKEN__" not in page,
                                  "session token substituted into the page")
            code, raw = client.raw("/static/app.js", token=False)
            failures += not check(code == 200 and b"function renderEditor" in raw,
                                  "static files served")
            code, _ = client.raw("/static/../server.py", token=False)
            failures += not check(code == 404, "no escaping the static directory")

            print("\nThe token gate")
            code, payload = client.json("/api/data", token=False)
            failures += not check(code == 403 and "error" in payload,
                                  "API refuses a request without a token")
            wrong = Client(address, "not-the-token")
            failures += not check(wrong.json("/api/data")[0] == 403, "a wrong token is refused")
            failures += not check(client.json("/api/data")[0] == 200, "the real token passes")

            print("\nReading and writing the document")
            code, payload = client.json("/api/status")
            failures += not check(code == 200 and payload["file"] == str(document),
                                  "status names the document file")
            failures += not check("sk-" not in json.dumps(payload["settings"])
                                  and "keys" not in payload["settings"],
                                  "status carries no API key")

            _, data = client.json("/api/data")
            failures += not check(data["person"]["lastName"] == "Musterfrau", "document read")

            changed = json.loads(json.dumps(data))
            changed["person"]["lastName"] = "Neumann"
            code, payload = client.json("/api/data", {"data": changed})
            failures += not check(code == 200 and payload["ok"], "document accepted")
            failures += not check(document.exists()
                                  and json.loads(document.read_text())["person"]["lastName"] == "Neumann",
                                  "document written to disk")
            failures += not check(model.load(document)["person"]["street"] == "Musterweg 7",
                                  "saved file reloads through the model")

            print("\nDocument routes")
            code, payload = client.json("/api/language", {"data": data, "language": "en"})
            titles = [s["title"] for s in payload["meta"]["sections"]]
            failures += not check(code == 200 and "Experience" in titles,
                                  "language switch retitles the sections")
            code, payload = client.json("/api/preview", {"data": data, "scale": 1.0})
            failures += not check(code == 200 and payload["pages"]
                                  and payload["pages"][0].startswith("data:image"),
                                  f"preview returns {len(payload.get('pages', []))} page image(s)")
            code, payload = client.json("/api/sample")
            failures += not check(code == 200 and payload["person"]["firstName"] == "Manuela",
                                  "sample document")
            code, payload = client.json("/api/blank")
            failures += not check(code == 200 and payload["person"]["firstName"] == ""
                                  and payload["meta"]["sections"],
                                  "blank document keeps its section list")

            print("\nJob posting by URL")
            with _job_board() as url:
                code, payload = client.json("/api/posting", {"url": url})
                failures += not check(code == 200 and "Testingenieur (m/w/d)" in payload["text"],
                                      "posting fetched through the server")
                failures += not check("var t = 1" not in payload["text"], "script content dropped")
            code, payload = client.json("/api/posting", {"url": "file:///etc/passwd"})
            failures += not check(code == 400 and "http" in payload.get("error", ""),
                                  "a local file is refused with HTTP 400")
            code, payload = client.json("/api/posting", {"url": ""})
            failures += not check(code == 400, "an empty address is refused")

            print("\nUnknown routes")
            failures += not check(client.json("/api/nonsense")[0] == 404, "unknown GET route")
            failures += not check(client.json("/api/nonsense", {"x": 1})[0] == 404,
                                  "unknown POST route")
            failures += not check(client.raw("/nonsense", token=False)[0] == 404, "unknown page")
        finally:
            running.shutdown()
            running.server_close()

    return summary(failures)


if __name__ == "__main__":
    sys.exit(main())
