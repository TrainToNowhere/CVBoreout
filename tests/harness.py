"""Shared pieces for the test scripts, so they all report the same way."""

from __future__ import annotations

import contextlib
import os
import tempfile
from pathlib import Path


def check(condition: bool, message: str) -> bool:
    print(f"  {'✓' if condition else '✗'} {message}")
    return bool(condition)


def summary(failures: int) -> int:
    print(f"\n{'All good.' if not failures else f'{failures} check(s) failed.'}")
    return 1 if failures else 0


@contextlib.contextmanager
def private_config():
    """Point the settings file at a throwaway directory.

    Every suite that touches settings or the server needs this: without it a
    test would read - or overwrite - the API keys of whoever runs it.
    """
    previous = os.environ.get("XDG_CONFIG_HOME")
    with tempfile.TemporaryDirectory() as folder:
        os.environ["XDG_CONFIG_HOME"] = folder
        try:
            yield Path(folder)
        finally:
            if previous is None:
                os.environ.pop("XDG_CONFIG_HOME", None)
            else:
                os.environ["XDG_CONFIG_HOME"] = previous
