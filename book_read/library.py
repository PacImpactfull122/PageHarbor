"""Local storage and lookup for downloaded books."""

from __future__ import annotations

import os
import re
from pathlib import Path


class BookLibrary:
    _NAME = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")

    def __init__(self, root: Path | None = None) -> None:
        self.root = (root or self._data_root()).expanduser().resolve()
        self.books = self.root / "books"
        self.languages = self.root / "languages"
        self.settings = self.root / "settings.json"
        self.state = self.root / "state.json"

    @staticmethod
    def _data_root() -> Path:
        if os.name == "nt":
            local = os.environ.get("LOCALAPPDATA")
            if local:
                return Path(local) / "book-read"
        data = os.environ.get("XDG_DATA_HOME")
        if data:
            return Path(data) / "book-read"
        return Path.home() / ".local" / "share" / "book-read"

    def prepare(self) -> None:
        self.books.mkdir(parents=True, exist_ok=True)
        self.languages.mkdir(parents=True, exist_ok=True)

    def path(self, name: str) -> Path:
        if not self._NAME.fullmatch(name):
            raise ValueError("Book names must use lowercase letters, numbers, and hyphens.")
        return self.books / name

    def find(self, name: str) -> Path | None:
        try:
            path = self.path(name)
        except ValueError:
            return None
        return path if path.is_dir() and not path.is_symlink() else None
