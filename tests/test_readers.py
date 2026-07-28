"""Tests for bookmark readers."""

import os
import json
import tempfile

import pytest

from browsersync.readers import ChromiumReader
from browsersync.models import Bookmark, Folder


FIXTURE_DIR = os.path.join(os.path.dirname(__file__), "fixtures")


class TestChromiumReader:
    def test_read_simple_bookmarks(self):
        path = os.path.join(FIXTURE_DIR, "chromium_bookmarks.json")
        reader = ChromiumReader()
        collection = reader.read(path, browser_name="TestBrowser")

        assert collection.total_bookmarks() == 3

        # Check bookmark_bar
        assert collection.bookmark_bar.total_bookmarks() == 2
        # Check other bookmarks
        assert collection.other_bookmarks.total_bookmarks() == 1

    def test_read_preserves_folder_structure(self):
        path = os.path.join(FIXTURE_DIR, "chromium_bookmarks.json")
        reader = ChromiumReader()
        collection = reader.read(path, browser_name="TestBrowser")

        bb = collection.bookmark_bar
        # Should have "Search Engines" subfolder
        search_engines = None
        for child in bb.children:
            if isinstance(child, Folder) and child.name == "Search Engines":
                search_engines = child
                break
        assert search_engines is not None
        assert search_engines.total_bookmarks() == 1

    def test_read_preserves_bookmark_data(self):
        path = os.path.join(FIXTURE_DIR, "chromium_bookmarks.json")
        reader = ChromiumReader()
        collection = reader.read(path, browser_name="TestBrowser")

        # Find the Example bookmark
        example = None
        for child in collection.bookmark_bar.children:
            if isinstance(child, Bookmark) and child.name == "Example":
                example = child
                break
            if isinstance(child, Folder):
                for sub in child.children:
                    if isinstance(sub, Bookmark) and sub.name == "Example":
                        example = sub
                        break
        assert example is not None
        assert example.url == "https://example.com"
        assert example.source == "TestBrowser"

    def test_read_empty_browser(self):
        data = {
            "checksum": "",
            "roots": {
                "bookmark_bar": {"children": [], "name": "Bookmark Bar", "type": "folder"},
                "other": {"children": [], "name": "Other Bookmarks", "type": "folder"},
                "synced": {"children": [], "name": "Synced Bookmarks", "type": "folder"},
            },
            "version": 1,
        }
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(data, f)
            path = f.name

        try:
            reader = ChromiumReader()
            collection = reader.read(path, browser_name="Empty")
            assert collection.total_bookmarks() == 0
        finally:
            os.unlink(path)
