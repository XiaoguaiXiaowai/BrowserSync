"""Safari bookmark writer."""

from __future__ import annotations

import plistlib
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from .base import Writer
from ..models import Bookmark, BookmarkCollection, Folder


def _dt_to_safari_time(dt: Optional[datetime]) -> float:
    """Convert datetime to Safari CFAbsoluteTime (seconds since 2001-01-01)."""
    if dt is None:
        dt = datetime.now(timezone.utc)
    epoch = datetime(2001, 1, 1, tzinfo=timezone.utc)
    return (dt - epoch).total_seconds()


def _bookmark_to_safari(bm: Bookmark) -> dict:
    """Convert a Bookmark to a Safari plist node."""
    node = {
        "WebBookmarkType": "WebBookmarkTypeLeaf",
        "URIDictionary": {"title": bm.name},
        "URLString": bm.url,
        "ReadingList": False,
    }
    # Only add DateAdded if we have one, otherwise Safari adds it
    if bm.date_added:
        node["DateAdded"] = _dt_to_safari_time(bm.date_added)
    return node


def _folder_to_safari(folder: Folder) -> dict:
    """Convert a Folder to a Safari plist node."""
    children = []
    for child in folder.children:
        if isinstance(child, Folder):
            children.append(_folder_to_safari(child))
        elif isinstance(child, Bookmark):
            children.append(_bookmark_to_safari(child))

    node: dict = {
        "WebBookmarkType": "WebBookmarkTypeList",
        "Title": folder.name,
        "Children": children,
        "ReadingList": False,
    }
    return node


class SafariWriter(Writer):
    """Writes bookmarks to Safari's plist format, preserving iCloud sync metadata."""

    def write(self, collection: BookmarkCollection, path: str) -> None:
        """Write the collection to Safari's Bookmarks.plist.

        Preserves existing iCloud Sync metadata (CloudKit state, device ID,
        server data) so that iCloud doesn't override our changes.
        """
        path = Path(path)

        # Read existing file to preserve sync metadata
        original = {}
        if path.exists():
            try:
                with open(path, "rb") as f:
                    original = plistlib.load(f)
            except Exception:
                pass

        # Build the Safari plist structure
        root_children = []

        # Bookmark Bar → Safari calls this "Favorites"
        bb = _folder_to_safari(collection.bookmark_bar)
        bb["Title"] = "Favorites"
        root_children.append(bb)

        # Other Bookmarks
        other = _folder_to_safari(collection.other_bookmarks)
        other["Title"] = "Other Bookmarks"
        root_children.append(other)

        # Synced Bookmarks
        if collection.synced_bookmarks.total_bookmarks() > 0:
            synced = _folder_to_safari(collection.synced_bookmarks)
            synced["Title"] = "Synced Bookmarks"
            root_children.append(synced)

        # Build plist data, preserving essential Safari metadata
        plist_data = {
            "Title": "com.apple.ReadingList",
            "WebBookmarkFileVersion": 1,
            "WebBookmarkType": "WebBookmarkTypeList",
            "Children": root_children,
        }

        # Preserve iCloud Sync metadata so Safari doesn't override our changes
        for key in ("WebBookmarkUUID", "Sync", "WebBookmarkIdentifier"):
            if key in original:
                plist_data[key] = original[key]

        # Preserve built-in ReadingList if it exists
        for key in ("BuiltInBookmarkPlistPath",):
            if key in original:
                plist_data[key] = original[key]

        # Backup original
        if path.exists():
            backup = path.with_suffix(path.suffix + ".browsersync.bak")
            shutil.copy2(path, backup)

        # Write binary plist
        path.parent.mkdir(parents=True, exist_ok=True)
        try:
            with open(path, "wb") as f:
                plistlib.dump(plist_data, f, fmt=plistlib.FMT_BINARY)
        except PermissionError:
            raise PermissionError(
                "Cannot write Safari bookmarks. "
                "Please grant Full Disk Access to your terminal/application:\n"
                "  System Settings → Privacy & Security → Full Disk Access → Add your terminal app"
            )
