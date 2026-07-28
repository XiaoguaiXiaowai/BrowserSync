"""Tests for the merger module."""

import os
import pytest

from browsersync.merger import merge_collections
from browsersync.models import Bookmark, BookmarkCollection, Folder
from browsersync.readers import ChromiumReader


FIXTURE_DIR = os.path.join(os.path.dirname(__file__), "fixtures")


class TestMerger:
    def test_merge_single_browser(self):
        """Merging a single browser returns the same collection."""
        coll = BookmarkCollection()
        coll.bookmark_bar.children.append(Bookmark(name="A", url="https://a.com"))

        merged = merge_collections({"Test": coll})
        assert merged.total_bookmarks() == 1

    def test_merge_deduplicates_by_url(self):
        """Two browsers with the same URL should result in one bookmark."""
        coll1 = BookmarkCollection()
        coll1.bookmark_bar.children.append(Bookmark(name="A", url="https://a.com"))

        coll2 = BookmarkCollection()
        coll2.bookmark_bar.children.append(Bookmark(name="A dup", url="https://a.com"))

        merged = merge_collections({"Browser1": coll1, "Browser2": coll2})
        assert merged.total_bookmarks() == 1

    def test_merge_unique_bookmarks(self):
        """Two browsers with different URLs should combine both."""
        coll1 = BookmarkCollection()
        coll1.bookmark_bar.children.append(Bookmark(name="A", url="https://a.com"))

        coll2 = BookmarkCollection()
        coll2.bookmark_bar.children.append(Bookmark(name="B", url="https://b.com"))

        merged = merge_collections({"Browser1": coll1, "Browser2": coll2})
        assert merged.total_bookmarks() == 2

    def test_merge_preserves_folder_structure(self):
        """Merged collection should preserve the base browser's folder structure."""
        reader = ChromiumReader()
        coll1 = reader.read(
            os.path.join(FIXTURE_DIR, "chromium_bookmarks.json"),
            browser_name="Browser1",
        )
        coll2 = reader.read(
            os.path.join(FIXTURE_DIR, "chromium_bookmarks_2.json"),
            browser_name="Browser2",
        )

        merged = merge_collections({"Browser1": coll1, "Browser2": coll2})

        # Browser1 has 3 bookmarks, Browser2 has 3 bookmarks
        # They share 1 (example.com), so total should be 5
        assert merged.total_bookmarks() == 5

    def test_merge_empty_collections(self):
        """Merging empty collections returns empty."""
        merged = merge_collections({})
        assert merged.total_bookmarks() == 0

    def test_merge_none_collection(self):
        """Merging single empty collection."""
        merged = merge_collections({"Empty": BookmarkCollection()})
        assert merged.total_bookmarks() == 0

    def test_merge_with_base_browser(self):
        """Specifying a base browser works correctly."""
        coll1 = BookmarkCollection()
        coll1.bookmark_bar.children.append(Bookmark(name="A", url="https://a.com"))

        coll2 = BookmarkCollection()
        coll2.bookmark_bar.children.append(Bookmark(name="B", url="https://b.com"))

        merged = merge_collections(
            {"Browser1": coll1, "Browser2": coll2},
            base_browser="Browser1",
        )
        assert merged.total_bookmarks() == 2
