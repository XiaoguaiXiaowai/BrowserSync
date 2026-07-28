"""Chromium-based browser bookmark reader."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from .base import Reader
from ..models import Bookmark, BookmarkCollection, Folder


def _webkit_to_dt(ts_str: Optional[str]) -> Optional[datetime]:
    """Convert Chromium WebKit timestamp to datetime."""
    if not ts_str:
        return None
    try:
        micros = int(ts_str)
        epoch = datetime(1601, 1, 1, tzinfo=timezone.utc)
        return epoch + __import__("datetime").timedelta(microseconds=micros)
    except (ValueError, TypeError):
        return None


def _chromium_node_to_bookmark(
    node: dict, parent_folder: str, browser_name: str
) -> Optional[Bookmark]:
    """Convert a Chromium bookmark node dict to a Bookmark."""
    if node.get("type") != "url":
        return None
    return Bookmark(
        name=node.get("name", ""),
        url=node.get("url", ""),
        date_added=_webkit_to_dt(node.get("date_added")),
        date_last_used=_webkit_to_dt(node.get("date_last_used")),
        guid=node.get("guid", ""),
        source=browser_name,
        source_folder=parent_folder,
    )


def _chromium_node_to_folder_or_bookmark(
    node: dict, parent_path: str, browser_name: str
) -> Optional[Bookmark | Folder]:
    """Convert a single Chromium node (could be URL or folder)."""
    if node.get("type") == "url":
        return _chromium_node_to_bookmark(node, parent_path, browser_name)
    elif node.get("type") == "folder":
        folder = Folder(
            name=node.get("name", "Unnamed"),
            date_added=_webkit_to_dt(node.get("date_added")),
            guid=node.get("guid", ""),
        )
        current_path = f"{parent_path}/{folder.name}" if parent_path else folder.name
        for child in node.get("children", []):
            parsed = _chromium_node_to_folder_or_bookmark(child, current_path, browser_name)
            if parsed:
                folder.children.append(parsed)
        return folder
    return None


class ChromiumReader(Reader):
    """Reads bookmarks from Chromium-based browsers (Chrome, Edge, Tabbit, etc.)."""

    def read(self, path: str, browser_name: str = "Unknown") -> BookmarkCollection:
        """Read Chromium bookmarks file and return a BookmarkCollection."""
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)

        roots = data.get("roots", {})
        collection = BookmarkCollection()

        # bookmark_bar: root's children are the actual top-level items
        bb = roots.get("bookmark_bar", {})
        for child in bb.get("children", []):
            parsed = _chromium_node_to_folder_or_bookmark(child, "", browser_name)
            if parsed:
                collection.bookmark_bar.children.append(parsed)

        # other bookmarks
        other = roots.get("other", {})
        for child in other.get("children", []):
            parsed = _chromium_node_to_folder_or_bookmark(child, "", browser_name)
            if parsed:
                collection.other_bookmarks.children.append(parsed)

        # synced bookmarks
        synced = roots.get("synced", {})
        for child in synced.get("children", []):
            parsed = _chromium_node_to_folder_or_bookmark(child, "", browser_name)
            if parsed:
                collection.synced_bookmarks.children.append(parsed)

        return collection
