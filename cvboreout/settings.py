"""Application settings: AI provider, model and API keys.

Kept separate from the CV document so that keys never end up in an exported
or shared resume file.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

PROVIDERS = [
    {"id": "ollama", "name": "Ollama (local)", "needs_key": False,
     "docs": "http://localhost:11434"},
    {"id": "anthropic", "name": "Anthropic", "needs_key": True,
     "docs": "https://console.anthropic.com/settings/keys"},
    {"id": "openai", "name": "OpenAI", "needs_key": True,
     "docs": "https://platform.openai.com/api-keys"},
    {"id": "openrouter", "name": "OpenRouter", "needs_key": True,
     "docs": "https://openrouter.ai/keys"},
]

ENV_KEYS = {
    "anthropic": "ANTHROPIC_API_KEY",
    "openai": "OPENAI_API_KEY",
    "openrouter": "OPENROUTER_API_KEY",
}

DEFAULTS = {
    "provider": "ollama",
    "models": {},   # provider -> last used model
    "keys": {},     # provider -> API key
}


def config_path() -> Path:
    base = os.environ.get("XDG_CONFIG_HOME") or (Path.home() / ".config")
    return Path(base) / "cvboreout" / "settings.json"


def load() -> dict:
    path = config_path()
    data = dict(DEFAULTS)
    if path.exists():
        try:
            stored = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(stored, dict):
                data.update(stored)
        except (json.JSONDecodeError, OSError):
            pass
    data.setdefault("models", {})
    data.setdefault("keys", {})
    return data


def save(data: dict) -> None:
    path = config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    try:
        path.chmod(0o600)  # the file holds API keys
    except OSError:
        pass


def api_key(provider: str, data: dict | None = None) -> str:
    """Stored key first, environment variable as fallback."""
    data = data if data is not None else load()
    stored = (data.get("keys") or {}).get(provider, "")
    if stored:
        return stored
    return os.environ.get(ENV_KEYS.get(provider, ""), "")


def public_view(data: dict) -> dict:
    """Settings for the frontend – keys are reduced to a boolean."""
    return {
        "provider": data.get("provider", "ollama"),
        "models": data.get("models", {}),
        "providers": PROVIDERS,
        "has_key": {
            entry["id"]: bool(api_key(entry["id"], data))
            for entry in PROVIDERS
            if entry["needs_key"]
        },
        "key_from_env": {
            provider: bool(os.environ.get(name)) and not (data.get("keys") or {}).get(provider)
            for provider, name in ENV_KEYS.items()
        },
    }
