"""Local HTTP server: serves the frontend and the JSON/stream endpoints."""

from __future__ import annotations

import copy
import json
import mimetypes
import secrets
import threading
import traceback
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from . import model, pdf, posting, prompts, providers, settings

STATIC = Path(__file__).parent / "static"


class State:
    """Shared state between window and server."""

    def __init__(self, path: Path):
        self.path = Path(path)
        self.data = model.load(self.path)
        self.settings = settings.load()
        self.token = secrets.token_urlsafe(16)
        self.lock = threading.Lock()
        self.file_dialog = None  # set in window mode

    def replace(self, data: dict) -> dict:
        with self.lock:
            self.data = model.normalize(data)
            model.save(self.path, self.data)
            return self.data

    def update_settings(self, changes: dict) -> dict:
        with self.lock:
            provider = changes.get("provider")
            if provider:
                self.settings["provider"] = provider
            if changes.get("model") and provider:
                self.settings.setdefault("models", {})[provider] = changes["model"]
            if "key" in changes and provider:
                key = (changes.get("key") or "").strip()
                keys = self.settings.setdefault("keys", {})
                if key:
                    keys[provider] = key
                else:
                    keys.pop(provider, None)
            settings.save(self.settings)
            return settings.public_view(self.settings)


def _default_target(state: State, kind: str = "resume") -> Path:
    person = state.data.get("person", {})
    name = "_".join(x for x in [person.get("firstName", ""), person.get("lastName", "")] if x) or "Resume"
    name = "".join(c for c in name if c.isalnum() or c in "_-")
    prefix = {"letter": "Letter", "both": "Application"}.get(kind, "CV")
    filename = f"{prefix}_{name}.pdf"
    for folder in (Path.home() / "Dokumente", Path.home() / "Documents", Path.home()):
        if folder.exists():
            return folder / filename
    return Path.cwd() / filename


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    server_version = "CVBoreout"
    state: State = None  # assigned by serve()

    def log_message(self, *_):  # keep the console quiet
        pass

    # --- plumbing --------------------------------------------------------
    def _head(self, code=200, kind="application/json; charset=utf-8", length=None, extra=None):
        self.send_response(code)
        self.send_header("Content-Type", kind)
        if length is not None:
            self.send_header("Content-Length", str(length))
        self.send_header("Cache-Control", "no-store")
        for key, value in (extra or {}).items():
            self.send_header(key, value)
        self.end_headers()

    def _json(self, payload, code=200):
        raw = json.dumps(payload, ensure_ascii=False).encode()
        self._head(code, length=len(raw))
        self.wfile.write(raw)

    def _fail(self, message, code=400):
        self._json({"error": str(message)}, code)

    def _body(self) -> dict:
        length = int(self.headers.get("Content-Length") or 0)
        if not length:
            return {}
        return json.loads(self.rfile.read(length) or b"{}")

    def _authorized(self, query) -> bool:
        sent = self.headers.get("X-Token") or (query.get("token", [""])[0])
        return secrets.compare_digest(sent or "", self.state.token)

    # --- routing ---------------------------------------------------------
    def do_GET(self):
        parsed = urlparse(self.path)
        path, query = parsed.path, parse_qs(parsed.query)
        try:
            if path in ("/", "/index.html"):
                return self._file(STATIC / "index.html")
            if path.startswith("/static/"):
                return self._file(STATIC / Path(path[8:]).name)
            if path.startswith("/api/"):
                if not self._authorized(query):
                    return self._fail("Unauthorized", 403)
                return self._get(path, query)
            return self._fail("Not found", 404)
        except providers.ProviderError as error:
            return self._fail(error, 502)
        except Exception as error:  # pragma: no cover
            traceback.print_exc()
            return self._fail(error, 500)

    def do_POST(self):
        parsed = urlparse(self.path)
        try:
            if not self._authorized(parse_qs(parsed.query)):
                return self._fail("Unauthorized", 403)
            return self._post(parsed.path)
        except pdf.RenderError as error:
            return self._fail(error, 500)
        except posting.FetchError as error:
            return self._fail(error, 400)
        except providers.ProviderError as error:
            return self._fail(error, 502)
        except Exception as error:  # pragma: no cover
            traceback.print_exc()
            return self._fail(error, 500)

    def _get(self, path, query):
        state = self.state
        if path == "/api/status":
            return self._json({
                "file": str(state.path),
                "templates": model.TEMPLATES,
                "accents": model.ACCENTS,
                "fonts": model.FONTS,
                "languages": model.LANGUAGES,
                "proficiency": model.PROFICIENCY,
                "sectionTitles": model.SECTION_TITLES,
                "settings": settings.public_view(state.settings),
                "dialog": state.file_dialog is not None,
            })
        if path == "/api/data":
            return self._json(state.data)
        if path == "/api/models":
            provider = (query.get("provider", [""])[0]) or state.settings.get("provider", "ollama")
            try:
                return self._json({
                    "provider": provider,
                    "models": providers.list_models(provider, settings.api_key(provider, state.settings)),
                })
            except providers.ProviderError as error:
                return self._json({"provider": provider, "models": [], "error": str(error)})
        if path == "/api/sample":
            return self._json(model.normalize(copy.deepcopy(model.SAMPLE)))
        if path == "/api/blank":
            return self._json(model.normalize({}))
        return self._fail("Unknown route", 404)

    def _post(self, path):
        state = self.state
        body = self._body()
        if path == "/api/data":
            return self._json({"ok": True, "data": state.replace(body.get("data", {}))})
        if path == "/api/settings":
            return self._json({"ok": True, "settings": state.update_settings(body)})
        if path == "/api/preview":
            data = model.normalize(body.get("data") or state.data)
            return self._json(pdf.preview(data, float(body.get("scale", 1.6)),
                                          body.get("doc", "resume")))
        if path == "/api/pdf":
            return self._export(body)
        if path == "/api/language":
            data = model.normalize(body.get("data") or state.data)
            language = body.get("language", "de")
            data["meta"]["language"] = language
            return self._json(model.retitle_sections(data, language))
        if path == "/api/ai":
            return self._stream(body)
        if path == "/api/posting":
            return self._json({"text": posting.fetch(body.get("url", ""))})
        return self._fail("Unknown route", 404)

    def _export(self, body):
        state = self.state
        data = model.normalize(body.get("data") or state.data)
        kind = body.get("doc", "resume")
        target = body.get("path")
        if not target and state.file_dialog:
            target = state.file_dialog(_default_target(state, kind))
            if not target:
                return self._json({"cancelled": True})
        target = Path(target) if target else _default_target(state)
        if target.suffix.lower() != ".pdf":
            target = target.with_suffix(".pdf")
        return self._json({"ok": True, "path": str(pdf.write_pdf(data, target, kind))})

    def _stream(self, body):
        state = self.state
        data = model.normalize(body.get("data") or state.data)
        provider = body.get("provider") or state.settings.get("provider", "ollama")
        chosen = body.get("model") or (state.settings.get("models") or {}).get(provider, "")
        system, prompt, kind, applicable = prompts.build(
            body.get("action", "free"), data, body.get("options", {}))

        self._head(200, "text/event-stream; charset=utf-8",
                   extra={"Transfer-Encoding": "chunked"})

        def send(event: str, payload: dict):
            block = f"event: {event}\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n".encode()
            self.wfile.write(f"{len(block):X}\r\n".encode() + block + b"\r\n")
            self.wfile.flush()

        try:
            send("start", {"kind": kind, "applicable": applicable, "provider": provider,
                           "model": chosen})
            key = settings.api_key(provider, state.settings)
            for piece in providers.chat_stream(provider, key, chosen, system, prompt,
                                               float(body.get("temperature", 0.4))):
                send("token", {"t": piece})
            send("end", {"ok": True})
        except (providers.ProviderError, OSError) as error:
            try:
                send("error", {"message": str(error)})
            except OSError:
                pass
        finally:
            try:
                self.wfile.write(b"0\r\n\r\n")
                self.wfile.flush()
            except OSError:
                pass

    def _file(self, path: Path):
        if not path.is_file():
            return self._fail("Not found", 404)
        kind = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        raw = path.read_bytes()
        if path.name == "index.html":
            raw = raw.replace(b"__TOKEN__", self.state.token.encode())
        self._head(200, f"{kind}; charset=utf-8" if kind.startswith("text") else kind,
                   length=len(raw))
        self.wfile.write(raw)


def serve(state: State, port: int = 0) -> tuple[ThreadingHTTPServer, str]:
    Handler.state = state
    server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    server.daemon_threads = True
    threading.Thread(target=server.serve_forever, daemon=True).start()
    address = f"http://127.0.0.1:{server.server_address[1]}/?token={state.token}"
    return server, address
