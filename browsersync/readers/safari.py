"""Safari bookmark reader.

Safari stores bookmarks in ~/Library/Safari/Bookmarks.plist (binary plist).
This file is protected by macOS TCC (Transparency, Consent, and Control)
and requires Full Disk Access permission for the calling process.

We attempt multiple strategies:
1. Direct plist read via plutil (requires TCC)
2. Export via osascript (requires Automation permission)
"""

from __future__ import annotations

import json
import plistlib
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from .base import Reader
from ..models import Bookmark, BookmarkCollection, Folder


def _safari_time_to_dt(ts: Optional[float]) -> Optional[datetime]:
    """Convert Safari CFAbsoluteTime (seconds since 2001-01-01) to datetime."""
    if ts is None:
        return None
    epoch = datetime(2001, 1, 1, tzinfo=timezone.utc)
    try:
        return epoch + __import__("datetime").timedelta(seconds=float(ts))
    except (ValueError, TypeError):
        return None


def _parse_safari_node(
    node: dict, parent_path: str, browser_name: str
) -> Optional[Folder | Bookmark]:
    """Recursively parse a Safari bookmark node."""
    bm_type = node.get("WebBookmarkType", "")

    if bm_type == "WebBookmarkTypeList":
        # Folder
        title = node.get("Title", "") or "Untitled"
        current_path = f"{parent_path}/{title}" if parent_path else title
        folder = Folder(
            name=title,
            date_added=_safari_time_to_dt(node.get("DateAdded")),
        )
        for child in node.get("Children", []):
            parsed = _parse_safari_node(child, current_path, browser_name)
            if parsed:
                folder.children.append(parsed)
        return folder

    elif bm_type == "WebBookmarkTypeLeaf":
        # Bookmark
        uri_dict = node.get("URIDictionary", {})
        title = uri_dict.get("title", "") or node.get("Title", "") or "Untitled"
        url = node.get("URLString", "")
        if not url:
            return None
        return Bookmark(
            name=title,
            url=url,
            date_added=_safari_time_to_dt(node.get("DateAdded")),
            guid=node.get("UUID", ""),
            source=browser_name,
            source_folder=parent_path,
        )

    return None


class SafariReader(Reader):
    """Reads bookmarks from Safari."""

    def read(self, path: str, browser_name: str = "Safari") -> BookmarkCollection:
        """Read Safari bookmarks file and return a BookmarkCollection.

        Raises PermissionError if the file cannot be read (TCC).
        """
        path_obj = Path(path)
        if not path_obj.exists():
            raise FileNotFoundError(f"Safari bookmarks not found: {path}")

        data = self._read_plist(path_obj)
        collection = BookmarkCollection()

        # Safari's root structure: a list of top-level folders
        # Typically: BookmarksBar, OtherBookmarks, etc.
        root_children = data.get("Children", []) if isinstance(data, dict) else []
        for child in root_children:
            parsed = _parse_safari_node(child, "", browser_name)
            if isinstance(parsed, Folder):
                name_lower = parsed.name.lower()
                if "bookmark bar" in name_lower or "favorites" in name_lower or "导航栏" in name_lower:
                    collection.bookmark_bar = parsed
                elif "other" in name_lower or "收藏夹" in name_lower:
                    collection.other_bookmarks = parsed
                else:
                    # Put unrecognized top-level folders into bookmark_bar
                    collection.bookmark_bar.children.append(parsed)

        return collection

    def _read_plist(self, path: Path) -> dict:
        """Attempt to read the plist file using multiple strategies."""
        # Strategy 1: Direct plistlib read
        try:
            with open(path, "rb") as f:
                return plistlib.load(f)
        except PermissionError:
            pass

        # Strategy 2: Try via plutil (JSON conversion)
        try:
            result = subprocess.run(
                ["plutil", "-convert", "json", "-o", "-", str(path)],
                capture_output=True, text=True, timeout=10,
            )
            if result.returncode == 0:
                return json.loads(result.stdout)
        except (subprocess.SubprocessError, json.JSONDecodeError):
            pass

        # Strategy 3: Suggest user grant permissions
        raise PermissionError(
            "Cannot read Safari bookmarks. "
            "Please grant Full Disk Access to your terminal/application:\n"
            "  System Settings → Privacy & Security → Full Disk Access → Add your terminal app\n"
            "Or run: tccutil reset All com.apple.Terminal  (if using Terminal)"
        )
