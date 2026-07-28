"""Base reader interface."""

from __future__ import annotations

from abc import ABC, abstractmethod

from ..models import BookmarkCollection


class Reader(ABC):
    """Abstract base class for bookmark readers."""

    @abstractmethod
    def read(self, path: str) -> BookmarkCollection:
        """Read bookmarks from the given path and return a unified collection."""
        ...
