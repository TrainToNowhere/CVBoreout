"""AI backends: local Ollama plus the Anthropic, OpenAI and OpenRouter APIs.

All four are reached over plain HTTP through urllib so that the application
stays dependency-free and every provider goes through one streaming interface.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from typing import Iterator

from . import settings

OLLAMA_HOST = os.environ.get("OLLAMA_HOST", "http://127.0.0.1:11434").rstrip("/")
if not OLLAMA_HOST.startswith("http"):
    OLLAMA_HOST = "http://" + OLLAMA_HOST

ANTHROPIC_URL = "https://api.anthropic.com/v1"
ANTHROPIC_VERSION = "2023-06-01"
OPENAI_URL = "https://api.openai.com/v1"
OPENROUTER_URL = "https://openrouter.ai/api/v1"

MAX_TOKENS = 4096          # resume snippets are short by design
REQUEST_TIMEOUT = 600


class ProviderError(RuntimeError):
    pass


def _request(url: str, headers: dict, payload: dict | None = None, timeout: int = 30):
    body = json.dumps(payload).encode() if payload is not None else None
    request = urllib.request.Request(url, data=body, headers=headers)
    try:
        return urllib.request.urlopen(request, timeout=timeout)
    except urllib.error.HTTPError as error:
        detail = ""
        try:
            detail = error.read().decode("utf-8", "replace")[:400]
        except OSError:
            pass
        message = _explain(error.code, detail)
        raise ProviderError(message) from error
    except urllib.error.URLError as error:
        raise ProviderError(f"Connection failed: {error.reason}") from error


def _explain(code: int, detail: str) -> str:
    try:
        parsed = json.loads(detail)
        detail = (parsed.get("error") or {}).get("message") or parsed.get("error") or detail
    except (json.JSONDecodeError, AttributeError):
        pass
    if code in (401, 403):
        return f"HTTP {code} – invalid or missing API key. {detail}"
    if code == 429:
        return f"HTTP 429 – rate limit reached. {detail}"
    if code == 404:
        return f"HTTP 404 – unknown model or endpoint. {detail}"
    return f"HTTP {code} – {detail}"


def _headers(provider: str, key: str) -> dict:
    common = {"Content-Type": "application/json"}
    if provider == "anthropic":
        return {**common, "x-api-key": key, "anthropic-version": ANTHROPIC_VERSION}
    if provider in ("openai", "openrouter"):
        headers = {**common, "Authorization": f"Bearer {key}"}
        if provider == "openrouter":
            headers["HTTP-Referer"] = "https://github.com/cvboreout"
            headers["X-Title"] = "CVBoreout"
        return headers
    return common


def _base(provider: str) -> str:
    return {
        "ollama": OLLAMA_HOST,
        "anthropic": ANTHROPIC_URL,
        "openai": OPENAI_URL,
        "openrouter": OPENROUTER_URL,
    }[provider]


def reachable(provider: str, key: str = "") -> bool:
    try:
        list_models(provider, key)
        return True
    except ProviderError:
        return False


# --- Model listing --------------------------------------------------------


def list_models(provider: str, key: str = "") -> list[dict]:
    if provider != "ollama" and not key:
        raise ProviderError("No API key stored for this provider.")

    if provider == "ollama":
        with _request(f"{OLLAMA_HOST}/api/tags", _headers(provider, key), timeout=8) as answer:
            raw = json.loads(answer.read())
        models = []
        for entry in raw.get("models", []):
            size = entry.get("size", 0) / 1e9
            models.append({"id": entry.get("name", ""),
                           "name": entry.get("name", ""),
                           "note": f"{size:.1f} GB" if size else ""})
        return sorted(models, key=lambda m: m["id"])

    if provider == "anthropic":
        with _request(f"{ANTHROPIC_URL}/models?limit=100",
                      _headers(provider, key), timeout=20) as answer:
            raw = json.loads(answer.read())
        return [{"id": entry["id"], "name": entry.get("display_name") or entry["id"], "note": ""}
                for entry in raw.get("data", [])]

    url = f"{_base(provider)}/models"
    with _request(url, _headers(provider, key), timeout=25) as answer:
        raw = json.loads(answer.read())
    models = []
    for entry in raw.get("data", []):
        identifier = entry.get("id", "")
        if provider == "openai" and not identifier.startswith(("gpt", "o1", "o3", "o4", "chatgpt")):
            continue  # hide embedding, audio and image endpoints
        models.append({
            "id": identifier,
            "name": entry.get("name") or identifier,
            "note": _price_note(entry) if provider == "openrouter" else "",
        })
    return sorted(models, key=lambda m: m["id"])


def _price_note(entry: dict) -> str:
    pricing = entry.get("pricing") or {}
    try:
        prompt = float(pricing.get("prompt", 0)) * 1e6
        completion = float(pricing.get("completion", 0)) * 1e6
    except (TypeError, ValueError):
        return ""
    if not prompt and not completion:
        return "free"
    return f"${prompt:.2f}/${completion:.2f} per 1M"


# --- Streaming chat -------------------------------------------------------


def chat_stream(provider: str, key: str, model: str, system: str, prompt: str,
                temperature: float = 0.4) -> Iterator[str]:
    if not model:
        raise ProviderError("No model selected.")
    if provider != "ollama" and not key:
        raise ProviderError("No API key stored for this provider.")

    if provider == "ollama":
        yield from _stream_ollama(model, system, prompt, temperature)
    elif provider == "anthropic":
        yield from _stream_anthropic(key, model, system, prompt, temperature)
    else:
        yield from _stream_openai(provider, key, model, system, prompt, temperature)


def _stream_ollama(model, system, prompt, temperature) -> Iterator[str]:
    payload = {
        "model": model,
        "messages": [{"role": "system", "content": system},
                     {"role": "user", "content": prompt}],
        "stream": True,
        "think": False,
        "options": {"temperature": temperature},
    }
    with _request(f"{OLLAMA_HOST}/api/chat", {"Content-Type": "application/json"},
                  payload, REQUEST_TIMEOUT) as answer:
        for line in answer:
            line = line.strip()
            if not line:
                continue
            try:
                chunk = json.loads(line)
            except json.JSONDecodeError:
                continue
            if chunk.get("error"):
                raise ProviderError(str(chunk["error"]))
            piece = (chunk.get("message") or {}).get("content", "")
            if piece:
                yield piece
            if chunk.get("done"):
                break


def _sse_events(answer) -> Iterator[dict]:
    """Yield parsed JSON payloads from a text/event-stream response."""
    for raw in answer:
        line = raw.decode("utf-8", "replace").strip()
        if not line or line.startswith(("event:", ":")):
            continue
        if not line.startswith("data:"):
            continue
        data = line[5:].strip()
        if data == "[DONE]":
            return
        try:
            yield json.loads(data)
        except json.JSONDecodeError:
            continue


def _stream_anthropic(key, model, system, prompt, temperature) -> Iterator[str]:
    payload = {
        "model": model,
        "max_tokens": MAX_TOKENS,
        "system": system,
        "messages": [{"role": "user", "content": prompt}],
        "stream": True,
    }
    with _request(f"{ANTHROPIC_URL}/messages", _headers("anthropic", key),
                  payload, REQUEST_TIMEOUT) as answer:
        for event in _sse_events(answer):
            kind = event.get("type")
            if kind == "content_block_delta":
                delta = event.get("delta") or {}
                if delta.get("type") == "text_delta" and delta.get("text"):
                    yield delta["text"]
            elif kind == "error":
                raise ProviderError(str((event.get("error") or {}).get("message", event)))
            elif kind == "message_stop":
                return


def _stream_openai(provider, key, model, system, prompt, temperature) -> Iterator[str]:
    payload = {
        "model": model,
        "messages": [{"role": "system", "content": system},
                     {"role": "user", "content": prompt}],
        "stream": True,
        "max_tokens": MAX_TOKENS,
    }
    with _request(f"{_base(provider)}/chat/completions", _headers(provider, key),
                  payload, REQUEST_TIMEOUT) as answer:
        for event in _sse_events(answer):
            if event.get("error"):
                raise ProviderError(str((event["error"] or {}).get("message", event["error"])))
            for choice in event.get("choices", []):
                piece = (choice.get("delta") or {}).get("content")
                if piece:
                    yield piece


def key_for(provider: str, stored: dict | None = None) -> str:
    return settings.api_key(provider, stored)
