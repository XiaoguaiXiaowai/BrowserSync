"""Browser auto-detection."""

from __future__ import annotations

import os
from typing import Iterator

from .config import KNOWN_BROWSERS


def detect_browsers() -> dict[str, dict]:
    """Scan the system for installed browsers with bookmark files."""
    found = {}
    for name, info in KNOWN_BROWSERS.items():
        path = os.path.expanduser(f"~/{info['bookmark_path']}")
        found[name] = {
            "enabled": os.path.exists(path),
            "path": path,
            "type": info["type"],
        }
    return found


def get_enabled_browsers(cfg: dict) -> Iterator[tuple[str, dict]]:
    """Yield (name, info) for enabled browsers with existing bookmark files."""
    for name, info in cfg.get("browsers", {}).items():
        if info.get("enabled") and os.path.exists(info.get("path", "")):
            yield name, info
