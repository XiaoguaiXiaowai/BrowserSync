"""Data models for bookmarks."""

from __future__ import annotations

import dataclasses
import json
from datetime import datetime, timedelta, timezone
from typing import Optional


# ── Helpers ─────────────────────────────────────────────────────────────────

_CHROMIUM_EPOCH = datetime(1601, 1, 1, tzinfo=timezone.utc)


def _parse_chromium_time(ts: str) -> Optional[datetime]:
    try:
        return _CHROMIUM_EPOCH + timedelta(microseconds=int(ts))
    except (ValueError, TypeError):
        return None


def _dt_to_str(dt: Optional[datetime]) -> Optional[str]:
    return dt.isoformat() if dt else None


def _str_to_dt(s: Optional[str]) -> Optional[datetime]:
    if not s:
        return None
    try:
        return datetime.fromisoformat(s)
    except (ValueError, TypeError):
        return None


# ── Data types ──────────────────────────────────────────────────────────────


@dataclasses.dataclass
class Bookmark:
    """A single bookmark URL."""

    name: str
    url: str
    date_added: Optional[datetime] = None
    date_last_used: Optional[datetime] = None
    guid: str = ""
    source: str = ""
    source_folder: str = ""

    def dedup_key(self) -> str:
        return self.url.strip().rstrip("/").lower()

    def normalized_url(self) -> tuple[str, str]:
        url = self.url.strip().rstrip("/")
        if url.startswith("https://"):
            alt = "http://" + url[8:]
        elif url.startswith("http://"):
            alt = "https://" + url[7:]
        else:
            alt = url
        return url.lower(), alt.lower()

    def to_dict(self) -> dict:
        return {
            "type": "url",
            "name": self.name,
            "url": self.url,
            "date_added": _dt_to_str(self.date_added),
            "date_last_used": _dt_to_str(self.date_last_used),
            "guid": self.guid,
            "source": self.source,
            "source_folder": self.source_folder,
        }

    @classmethod
    def from_dict(cls, d: dict) -> Bookmark:
        return cls(
            name=d.get("name", ""),
            url=d.get("url", ""),
            date_added=_str_to_dt(d.get("date_added")),
            date_last_used=_str_to_dt(d.get("date_last_used")),
            guid=d.get("guid", ""),
            source=d.get("source", ""),
            source_folder=d.get("source_folder", ""),
        )


@dataclasses.dataclass
class Folder:
    """A bookmark folder containing bookmarks and sub-folders."""

    name: str
    children: list[Folder | Bookmark] = dataclasses.field(default_factory=list)
    date_added: Optional[datetime] = None
    guid: str = ""

    def total_bookmarks(self) -> int:
        count = 0
        for child in self.children:
            count += child.total_bookmarks() if isinstance(child, Folder) else 1
        return count

    def to_dict(self) -> dict:
        return {
            "type": "folder",
            "name": self.name,
            "date_added": _dt_to_str(self.date_added),
            "guid": self.guid,
            "children": [c.to_dict() for c in self.children],
        }

    @classmethod
    def from_dict(cls, d: dict) -> Folder:
        children = []
        for c in d.get("children", []):
            if isinstance(c, dict):
                if c.get("type") == "url":
                    children.append(Bookmark.from_dict(c))
                else:
                    children.append(Folder.from_dict(c))
            else:
                children.append(c)
        return cls(
            name=d.get("name", ""),
            children=children,
            date_added=_str_to_dt(d.get("date_added")),
            guid=d.get("guid", ""),
        )


@dataclasses.dataclass
class BookmarkCollection:
    """Unified bookmark collection from all browsers."""

    bookmark_bar: Folder = dataclasses.field(default_factory=lambda: Folder(name="Bookmark Bar"))
    other_bookmarks: Folder = dataclasses.field(default_factory=lambda: Folder(name="Other Bookmarks"))
    synced_bookmarks: Folder = dataclasses.field(default_factory=lambda: Folder(name="Synced Bookmarks"))

    def total_bookmarks(self) -> int:
        return (
            self.bookmark_bar.total_bookmarks()
            + self.other_bookmarks.total_bookmarks()
            + self.synced_bookmarks.total_bookmarks()
        )

    def to_dict(self) -> dict:
        return {
            "bookmark_bar": self.bookmark_bar.to_dict(),
            "other_bookmarks": self.other_bookmarks.to_dict(),
            "synced_bookmarks": self.synced_bookmarks.to_dict(),
        }

    @classmethod
    def from_dict(cls, d: dict) -> BookmarkCollection:
        return cls(
            bookmark_bar=Folder.from_dict(d.get("bookmark_bar", {})),
            other_bookmarks=Folder.from_dict(d.get("other_bookmarks", {})),
            synced_bookmarks=Folder.from_dict(d.get("synced_bookmarks", {})),
        )

    def save_json(self, path: str) -> None:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, ensure_ascii=False, indent=2)

    @classmethod
    def load_json(cls, path: str) -> BookmarkCollection:
        """Load from file, supporting both flat and browsers-wrapped formats."""
        with open(path, "r", encoding="utf-8") as f:
            raw = json.load(f)

        # Format detection: flat (bookmark_bar at root) or browsers-wrapped
        if "bookmark_bar" in raw:
            return cls.from_dict(raw)

        # Browsers-wrapped: rebuild by merging all browser collections
        if "browsers" in raw:
            from .merger import merge_collections
            collections = {}
            for name, data in raw["browsers"].items():
                collections[name] = cls.from_dict(data)
            if not collections:
                return cls()
            base = max(collections, key=lambda b: collections[b].total_bookmarks())
            return merge_collections(collections, base_browser=base)

        return cls()
