"""Bookmark merging and deduplication."""

from __future__ import annotations

import copy
from typing import Optional

from .models import Bookmark, BookmarkCollection, Folder


def _flatten_bookmarks(folder: Folder, path: str = "") -> list[Bookmark]:
    """Flatten a folder tree into a list of bookmarks with folder paths."""
    bookmarks = []
    for child in folder.children:
        current_path = f"{path}/{folder.name}" if path else folder.name
        if isinstance(child, Bookmark):
            child.source_folder = current_path
            bookmarks.append(child)
        elif isinstance(child, Folder):
            bookmarks.extend(_flatten_bookmarks(child, current_path))
    return bookmarks


def _normalize_url(url: str) -> str:
    """Normalize URL for dedup comparison."""
    url = url.strip().rstrip("/")
    # Remove fragment
    if "#" in url:
        url = url[: url.index("#")]
    return url.lower()


def _index_urls_in_folder(folder: Folder, index: dict[str, Bookmark]) -> None:
    """Recursively index all bookmark URLs in a folder tree."""
    for child in folder.children:
        if isinstance(child, Bookmark):
            key = _normalize_url(child.url)
            if key not in index:
                index[key] = child
        elif isinstance(child, Folder):
            _index_urls_in_folder(child, index)


def _index_urls(collection: BookmarkCollection, index: dict[str, Bookmark]) -> None:
    """Index all bookmark URLs in a collection across all root folders."""
    for root_key in ("bookmark_bar", "other_bookmarks", "synced_bookmarks"):
        _index_urls_in_folder(getattr(collection, root_key), index)


def merge_collections(
    collections: dict[str, BookmarkCollection],
    base_browser: Optional[str] = None,
) -> BookmarkCollection:
    """Merge multiple bookmark collections into one.

    Args:
        collections: Dict mapping browser name to BookmarkCollection.
        base_browser: Name of browser whose folder structure to use as base.
                      If None, uses the browser with the most bookmarks.

    Returns:
        A merged BookmarkCollection.
    """
    if not collections:
        return BookmarkCollection()

    # Determine base browser (the one with most bookmarks)
    if base_browser is None:
        base_browser = max(
            collections, key=lambda b: collections[b].total_bookmarks()
        )

    merged = copy.deepcopy(collections[base_browser])

    # Collect existing URLs from the merged collection
    existing_urls: dict[str, Bookmark] = {}
    _index_urls(merged, existing_urls)

    # Merge other browsers
    for browser_name, coll in collections.items():
        if browser_name == base_browser:
            continue

        for root_key in ("bookmark_bar", "other_bookmarks", "synced_bookmarks"):
            source_root = getattr(coll, root_key)
            target_root = getattr(merged, root_key)

            if not source_root.children:
                continue

            added = _merge_folder_children(
                source_root, target_root, browser_name, existing_urls
            )

    return merged


def _merge_folder_children(
    source: Folder, target: Folder, browser_name: str, existing: dict[str, Bookmark]
) -> int:
    """Merge source folder children into target folder.

    Returns the number of new bookmarks added.
    """
    added = 0
    for child in source.children:
        if isinstance(child, Bookmark):
            key = _normalize_url(child.url)
            if key not in existing:
                child.source = browser_name
                target.children.append(child)
                existing[key] = child
                added += 1
        elif isinstance(child, Folder):
            # Try to find a matching folder in target
            matched = None
            for tc in target.children:
                if isinstance(tc, Folder) and tc.name == child.name:
                    matched = tc
                    break
            if matched:
                added += _merge_folder_children(child, matched, browser_name, existing)
            else:
                # Add the whole folder, but filter out URLs already existing
                filtered = _filter_new_only(child, existing)
                if filtered.total_bookmarks() > 0:
                    _index_urls_in_folder(filtered, existing)
                    target.children.append(filtered)
                    added += filtered.total_bookmarks()
    return added


def _filter_new_only(folder: Folder, existing: dict[str, Bookmark]) -> Folder:
    """Return a new folder with only bookmarks not already in existing."""
    result = Folder(name=folder.name, date_added=folder.date_added, guid=folder.guid)
    for child in folder.children:
        if isinstance(child, Bookmark):
            key = _normalize_url(child.url)
            if key not in existing:
                result.children.append(child)
                existing[key] = child
        elif isinstance(child, Folder):
            filtered = _filter_new_only(child, existing)
            if filtered.total_bookmarks() > 0 or any(
                isinstance(c, Folder) for c in filtered.children
            ):
                result.children.append(filtered)
    return result


def mirror_collections(
    collections: dict[str, BookmarkCollection],
    base_browser: str | None = None,
) -> BookmarkCollection:
    """Mirror the base browser's bookmarks to all browsers.

    Unlike merge_collections(), this simply returns an exact copy of the
    base browser's bookmarks without any merging or deduplication.
    All browsers will receive the exact same content as the base browser.

    Args:
        collections: Dict mapping browser name to BookmarkCollection.
        base_browser: Name of browser whose bookmarks to use as the source.
                      If None, uses the browser with the most bookmarks.

    Returns:
        A deep copy of the base browser's BookmarkCollection.
    """
    if not collections:
        return BookmarkCollection()

    if base_browser is None:
        base_browser = max(
            collections, key=lambda b: collections[b].total_bookmarks()
        )

    return copy.deepcopy(collections[base_browser])
