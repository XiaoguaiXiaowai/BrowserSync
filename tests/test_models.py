"""Tests for data models."""

import json
import os
import tempfile
from datetime import datetime, timezone

import pytest

from browsersync.models import Bookmark, BookmarkCollection, Folder, _parse_chromium_time


class TestBookmark:
    def test_dedup_key(self):
        bm = Bookmark(name="Test", url="https://example.com/path/")
        assert bm.dedup_key() == "https://example.com/path"

    def test_dedup_key_case_insensitive(self):
        bm1 = Bookmark(name="A", url="https://EXAMPLE.com")
        bm2 = Bookmark(name="B", url="https://example.com")
        assert bm1.dedup_key() == bm2.dedup_key()

    def test_normalized_url(self):
        bm = Bookmark(name="Test", url="https://example.com/#fragment")
        norm, alt = bm.normalized_url()
        assert "fragment" in norm
        assert "fragment" in alt

    def test_serialization_roundtrip(self):
        bm = Bookmark(
            name="Test",
            url="https://example.com",
            date_added=datetime(2024, 1, 1, tzinfo=timezone.utc),
            guid="abc-123",
            source="Chrome",
            source_folder="Bookmarks/Dev",
        )
        d = bm.to_dict()
        restored = Bookmark.from_dict(d)
        assert restored.name == bm.name
        assert restored.url == bm.url
        assert restored.guid == bm.guid
        assert restored.source == bm.source


class TestFolder:
    def test_empty_folder(self):
        f = Folder(name="Empty")
        assert f.total_bookmarks() == 0

    def test_folder_with_children(self):
        f = Folder(name="Root")
        f.children.append(Bookmark(name="A", url="https://a.com"))
        f.children.append(Bookmark(name="B", url="https://b.com"))
        sub = Folder(name="Sub")
        sub.children.append(Bookmark(name="C", url="https://c.com"))
        f.children.append(sub)
        assert f.total_bookmarks() == 3


class TestBookmarkCollection:
    def test_empty_collection(self):
        coll = BookmarkCollection()
        assert coll.total_bookmarks() == 0

    def test_save_load_json(self):
        coll = BookmarkCollection()
        coll.bookmark_bar.children.append(Bookmark(name="A", url="https://a.com"))
        coll.other_bookmarks.children.append(Bookmark(name="B", url="https://b.com"))

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            path = f.name

        try:
            coll.save_json(path)
            loaded = BookmarkCollection.load_json(path)
            assert loaded.total_bookmarks() == 2
            assert loaded.bookmark_bar.total_bookmarks() == 1
            assert loaded.other_bookmarks.total_bookmarks() == 1
        finally:
            os.unlink(path)


class TestParseChromiumTime:
    def test_valid_timestamp(self):
        dt = _parse_chromium_time("13250000000000000")
        assert dt is not None
        assert dt.year > 2000

    def test_invalid_timestamp(self):
        assert _parse_chromium_time("not-a-number") is None
        assert _parse_chromium_time(None) is None
