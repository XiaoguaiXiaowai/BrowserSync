"""Tests for bookmark writers."""

import json
import os
import tempfile

import pytest

from browsersync.writers import ChromiumWriter
from browsersync.models import Bookmark, BookmarkCollection, Folder


class TestChromiumWriter:
    def test_write_and_read_back(self):
        collection = BookmarkCollection()
        collection.bookmark_bar.children.append(
            Bookmark(name="Test", url="https://test.com")
        )
        collection.other_bookmarks.children.append(
            Bookmark(name="Other", url="https://other.com")
        )

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            path = f.name

        try:
            writer = ChromiumWriter()
            writer.write(collection, path)

            # Verify the output
            with open(path, "r") as f:
                data = json.load(f)

            assert "checksum" in data
            assert "roots" in data
            assert "version" in data
            assert data["version"] == 1

            # Check bookmark bar
            bb = data["roots"]["bookmark_bar"]
            assert bb["type"] == "folder"
            assert len(bb["children"]) == 1
            assert bb["children"][0]["name"] == "Test"
            assert bb["children"][0]["url"] == "https://test.com"

            # Check other bookmarks
            other = data["roots"]["other"]
            assert len(other["children"]) == 1
            assert other["children"][0]["name"] == "Other"

        finally:
            os.unlink(path)

    def test_write_preserves_folder_structure(self):
        collection = BookmarkCollection()
        sub = Folder(name="SubFolder")
        sub.children.append(Bookmark(name="Nested", url="https://nested.com"))
        collection.bookmark_bar.children.append(sub)

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            path = f.name

        try:
            writer = ChromiumWriter()
            writer.write(collection, path)

            with open(path, "r") as f:
                data = json.load(f)

            bb = data["roots"]["bookmark_bar"]
            assert len(bb["children"]) == 1
            assert bb["children"][0]["type"] == "folder"
            assert bb["children"][0]["name"] == "SubFolder"
            assert len(bb["children"][0]["children"]) == 1
            assert bb["children"][0]["children"][0]["name"] == "Nested"

        finally:
            os.unlink(path)

    def test_write_creates_backup(self):
        collection = BookmarkCollection()
        collection.bookmark_bar.children.append(
            Bookmark(name="Test", url="https://test.com")
        )

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            # Write initial content
            json.dump({"version": 1, "roots": {}, "checksum": ""}, f)
            path = f.name

        try:
            writer = ChromiumWriter()
            writer.write(collection, path)

            # Check backup was created
            backup_path = path + ".browsersync.bak"
            assert os.path.exists(backup_path)

            # Verify backup contains original content
            with open(backup_path, "r") as f:
                backup_data = json.load(f)
            assert backup_data["version"] == 1

            # Clean up backup
            os.unlink(backup_path)
        finally:
            os.unlink(path)
