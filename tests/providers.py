"""Self-test for the AI backends: the four wire formats, parsed offline.

No request leaves the machine - `providers._request` is replaced by a stand-in
that hands the real parsers a canned answer.
"""

from __future__ import annotations

import contextlib
import json
import os
import sys

from cvboreout import providers, settings

from .harness import check, private_config, summary


class _Answer:
    """Stands in for the file object urlopen returns: iterable and readable."""

    def __init__(self, lines: list[bytes]):
        self._lines = lines

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def __iter__(self):
        return iter(self._lines)

    def read(self):
        return b"".join(self._lines)


@contextlib.contextmanager
def _answering(lines, seen: dict | None = None):
    def stand_in(url, headers, payload=None, timeout=30):
        if seen is not None:
            seen.update(url=url, headers=headers, payload=payload, timeout=timeout)
        return _Answer(lines)

    original = providers._request
    providers._request = stand_in
    try:
        yield
    finally:
        providers._request = original


def _collect(provider, key="k", model="m"):
    return "".join(providers.chat_stream(provider, key, model, "system", "prompt"))


def _raises(call) -> bool:
    try:
        call()
    except providers.ProviderError:
        return True
    return False


def main() -> int:
    failures = 0

    print("Ollama stream")
    lines = [
        b'{"message": {"content": "Hallo "}}\n',
        b"\n",                                          # keep-alive
        b"not json at all\n",                           # must not kill the stream
        b'{"message": {"content": ""}}\n',              # empty piece
        b'{"message": {"content": "Welt"}}\n',
        b'{"done": true}\n',
        b'{"message": {"content": "danach"}}\n',        # after done: ignored
    ]
    seen = {}
    with _answering(lines, seen):
        failures += not check(_collect("ollama", key="") == "Hallo Welt",
                              "text assembled, noise and empty chunks skipped")
    failures += not check(seen["payload"]["stream"] is True
                          and seen["payload"]["messages"][0]["role"] == "system",
                          "request carries system prompt and streams")
    with _answering([b'{"error": "model not found"}\n']):
        failures += not check(_raises(lambda: _collect("ollama", key="")),
                              "error chunk becomes a ProviderError")

    print("\nAnthropic stream")
    lines = [
        b": ping\n",                                    # comment line
        b"event: content_block_delta\n",                # event lines are skipped
        b'data: {"type": "content_block_delta", "delta": {"type": "text_delta", "text": "Guten "}}\n',
        b'data: {"type": "content_block_delta", "delta": {"type": "thinking_delta", "text": "hmm"}}\n',
        b'data: {"type": "content_block_delta", "delta": {"type": "text_delta", "text": "Tag"}}\n',
        b'data: {"type": "message_stop"}\n',
        b'data: {"type": "content_block_delta", "delta": {"type": "text_delta", "text": "too late"}}\n',
    ]
    seen = {}
    with _answering(lines, seen):
        failures += not check(_collect("anthropic") == "Guten Tag",
                              "only text deltas, stops at message_stop")
    failures += not check(seen["headers"].get("x-api-key") == "k"
                          and seen["headers"].get("anthropic-version"),
                          "key and version travel in the headers")
    with _answering([b'data: {"type": "error", "error": {"message": "overloaded"}}\n']):
        failures += not check(_raises(lambda: _collect("anthropic")),
                              "error event becomes a ProviderError")

    print("\nOpenAI and OpenRouter stream")
    lines = [
        b'data: {"choices": [{"delta": {"role": "assistant"}}]}\n',     # no content yet
        b'data: {"choices": [{"delta": {"content": "Kurz"}}]}\n',
        b"\n",
        b'data: {"choices": [{"delta": {"content": "profil"}}]}\n',
        b"data: [DONE]\n",
        b'data: {"choices": [{"delta": {"content": "danach"}}]}\n',
    ]
    for provider in ("openai", "openrouter"):
        seen = {}
        with _answering(lines, seen):
            failures += not check(_collect(provider) == "Kurzprofil", f"{provider}: deltas joined")
        failures += not check(seen["headers"].get("Authorization") == "Bearer k",
                              f"{provider}: bearer token set")
    with _answering(lines, seen := {}):
        _collect("openrouter")
    failures += not check(seen["headers"].get("X-Title") == "CVBoreout",
                          "openrouter identifies the app")
    with _answering([b'data: {"error": {"message": "no credit"}}\n']):
        failures += not check(_raises(lambda: _collect("openai")),
                              "error payload becomes a ProviderError")

    print("\nStream guards")
    failures += not check(_raises(lambda: _collect("openai", key="", model="m")),
                          "missing key refused before any request")
    failures += not check(_raises(lambda: _collect("ollama", key="", model="")),
                          "missing model refused before any request")

    print("\nModel listing")
    tags = [json.dumps({"models": [{"name": "qwen3:8b", "size": 5_200_000_000},
                                   {"name": "gemma3:4b", "size": 0}]}).encode()]
    with _answering(tags):
        models = providers.list_models("ollama")
    failures += not check([m["id"] for m in models] == ["gemma3:4b", "qwen3:8b"], "ollama: sorted")
    failures += not check(models[1]["note"] == "5.2 GB" and models[0]["note"] == "",
                          "ollama: size only when known")

    catalogue = [json.dumps({"data": [
        {"id": "gpt-4o-mini"},
        {"id": "text-embedding-3-small"},
        {"id": "o3-mini"},
    ]}).encode()]
    with _answering(catalogue):
        models = providers.list_models("openai", "k")
    failures += not check([m["id"] for m in models] == ["gpt-4o-mini", "o3-mini"],
                          "openai: embedding endpoints hidden")

    priced = [json.dumps({"data": [
        {"id": "a/b", "name": "A B", "pricing": {"prompt": "0.0000002", "completion": "0.0000012"}},
        {"id": "c/d", "pricing": {"prompt": "0", "completion": "0"}},
    ]}).encode()]
    with _answering(priced):
        models = providers.list_models("openrouter", "k")
    failures += not check(models[0]["note"] == "$0.20/$1.20 per 1M", "openrouter: price per million")
    failures += not check(models[1]["note"] == "free", "openrouter: free models marked")

    claude = [json.dumps({"data": [{"id": "claude-x", "display_name": "Claude X"}]}).encode()]
    with _answering(claude):
        models = providers.list_models("anthropic", "k")
    failures += not check(models[0]["name"] == "Claude X", "anthropic: display name kept")
    failures += not check(_raises(lambda: providers.list_models("openai", "")),
                          "listing without a key refused")

    print("\nError messages")
    failures += not check("invalid or missing API key" in providers._explain(401, ""),
                          "401 explained in plain words")
    failures += not check("rate limit" in providers._explain(429, ""), "429 explained")
    failures += not check("boom" in providers._explain(500, '{"error": {"message": "boom"}}'),
                          "detail lifted out of the error JSON")

    print("\nKeys and settings")
    with private_config() as folder:
        settings.save({"provider": "openai", "models": {"openai": "gpt-4o"},
                       "keys": {"openai": "sk-secret"}})
        path = settings.config_path()
        failures += not check(path.exists() and str(path).startswith(str(folder)),
                              "settings land in the configured directory")
        failures += not check(path.stat().st_mode & 0o777 == 0o600, "key file is owner-only")

        stored = settings.load()
        failures += not check(settings.api_key("openai", stored) == "sk-secret", "stored key wins")

        public = settings.public_view(stored)
        failures += not check("sk-secret" not in json.dumps(public),
                              "public view carries no key")
        failures += not check(public["has_key"]["openai"] is True
                              and public["has_key"]["anthropic"] is False,
                              "public view reports only whether a key exists")

        os.environ["ANTHROPIC_API_KEY"] = "env-key"
        try:
            failures += not check(settings.api_key("anthropic", stored) == "env-key",
                                  "environment variable fills in")
            failures += not check(settings.public_view(stored)["key_from_env"]["anthropic"] is True,
                                  "frontend learns the key came from the environment")
            failures += not check(settings.public_view(stored)["key_from_env"]["openai"] is False,
                                  "a stored key is not reported as environment key")
        finally:
            os.environ.pop("ANTHROPIC_API_KEY", None)

    return summary(failures)


if __name__ == "__main__":
    sys.exit(main())
