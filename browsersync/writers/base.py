"""Base writer interface."""

from __future__ import annotations

from abc import ABC, abstractmethod

from ..models import BookmarkCollection


class Writer(ABC):
    """Abstract base class for bookmark writers."""

    @abstractmethod
    def write(self, collection: BookmarkCollection, path: str) -> None:
        """Write the bookmark collection to the given path in native format."""
        ...
