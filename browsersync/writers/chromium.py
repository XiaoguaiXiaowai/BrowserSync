"""Chromium-based browser bookmark writer."""

from __future__ import annotations

import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from .base import Writer
from ..models import Bookmark, BookmarkCollection, Folder


def _dt_to_webkit(dt: Optional[datetime]) -> str:
    """Convert datetime to Chromium WebKit timestamp (microseconds since 1601-01-01)."""
    if dt is None:
        dt = datetime.now(timezone.utc)
    epoch = datetime(1601, 1, 1, tzinfo=timezone.utc)
    delta = dt - epoch
    micros = int(delta.total_seconds() * 1_000_000)
    return str(micros)


def _folder_to_chromium(folder: Folder, next_id: list[int]) -> dict:
    """Convert a Folder to a Chromium bookmark node dict."""
    node_id = next_id[0]
    next_id[0] += 1
    node = {
        "children": [],
        "date_added": _dt_to_webkit(folder.date_added),
        "date_modified": _dt_to_webkit(None),
        "guid": folder.guid or f"folder-{node_id}",
        "id": str(node_id),
        "name": folder.name,
        "type": "folder",
    }
    for child in folder.children:
        if isinstance(child, Folder):
            node["children"].append(_folder_to_chromium(child, next_id))
        elif isinstance(child, Bookmark):
            node["children"].append(_bookmark_to_chromium(child, next_id))
    return node


def _bookmark_to_chromium(bm: Bookmark, next_id: list[int]) -> dict:
    """Convert a Bookmark to a Chromium bookmark node dict."""
    node_id = next_id[0]
    next_id[0] += 1
    return {
        "date_added": _dt_to_webkit(bm.date_added),
        "date_last_used": _dt_to_webkit(bm.date_last_used),
        "guid": bm.guid or f"bookmark-{node_id}",
        "id": str(node_id),
        "name": bm.name,
        "type": "url",
        "url": bm.url,
    }


class ChromiumWriter(Writer):
    """Writes bookmarks to Chromium-based browsers."""

    def write(self, collection: BookmarkCollection, path: str) -> None:
        """Write the collection to a Chromium Bookmarks file.

        Preserves the original file structure (checksum, sync_metadata, version)
        if the file already exists.
        """
        path = Path(path)
        original = {}
        if path.exists():
            try:
                with open(path, "r", encoding="utf-8") as f:
                    original = json.load(f)
            except (json.JSONDecodeError, OSError):
                pass

        next_id = [1]

        roots = {
            "bookmark_bar": _folder_to_chromium(collection.bookmark_bar, next_id),
            "other": _folder_to_chromium(collection.other_bookmarks, next_id),
            "synced": _folder_to_chromium(collection.synced_bookmarks, next_id),
        }

        output = {
            "checksum": "",
            "roots": roots,
            "sync_metadata": original.get("sync_metadata", ""),
            "version": original.get("version", 1),
        }

        # Backup original
        if path.exists():
            backup = path.with_suffix(path.suffix + ".browsersync.bak")
            shutil.copy2(path, backup)

        # Write
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(output, f, ensure_ascii=False, indent=2)
