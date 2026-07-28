"""Configuration management."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

import yaml

DEFAULT_CONFIG_DIR = Path.home() / ".browsersync"
DEFAULT_CONFIG_PATH = DEFAULT_CONFIG_DIR / "config.yaml"


# Known Chromium-based browsers on macOS
KNOWN_BROWSERS = {
    "Tabbit": {
        "bookmark_path": "Library/Application Support/Tabbit/Default/Bookmarks",
        "type": "chromium",
    },
    "Tabbit Browser": {
        "bookmark_path": "Library/Application Support/Tabbit Browser/Default/Bookmarks",
        "type": "chromium",
    },
    "Quark": {
        "bookmark_path": "Library/Application Support/Quark/Default/Bookmarks",
        "type": "chromium",
    },
    "Google Chrome": {
        "bookmark_path": "Library/Application Support/Google/Chrome/Default/Bookmarks",
        "type": "chromium",
    },
    "Microsoft Edge": {
        "bookmark_path": "Library/Application Support/Microsoft Edge/Default/Bookmarks",
        "type": "chromium",
    },
    "Safari": {
        "bookmark_path": "Library/Safari/Bookmarks.plist",
        "type": "safari",
    },
}


def default_config() -> dict:
    """Generate default configuration with auto-detected browsers."""
    browsers = {}
    for name, info in KNOWN_BROWSERS.items():
        path = os.path.expanduser(f"~/{info['bookmark_path']}")
        browsers[name] = {
            "enabled": os.path.exists(path),
            "path": path,
            "type": info["type"],
        }
    return {
        "browsers": browsers,
        "backup_dir": str(DEFAULT_CONFIG_DIR / "backups"),
        "log_dir": str(DEFAULT_CONFIG_DIR / "logs"),
        "merge_output": str(DEFAULT_CONFIG_DIR / "merged.json"),
    }


def load_config(config_path: Optional[Path] = None) -> dict:
    """Load config from file or create default."""
    path = config_path or DEFAULT_CONFIG_PATH
    if path.exists():
        with open(path) as f:
            return yaml.safe_load(f) or default_config()
    return default_config()


def save_config(cfg: dict, config_path: Optional[Path] = None) -> Path:
    """Save config to file."""
    path = config_path or DEFAULT_CONFIG_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        yaml.safe_dump(cfg, f, default_flow_style=False, allow_unicode=True)
    return path


def ensure_dirs(cfg: dict) -> None:
    """Ensure required directories exist."""
    for key in ("backup_dir", "log_dir"):
        if key in cfg:
            Path(cfg[key]).mkdir(parents=True, exist_ok=True)
