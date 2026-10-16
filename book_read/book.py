"""mdBook configuration, chapter lookup, content caching, and search."""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import tomllib
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from urllib.parse import unquote, urlsplit

from .convert import MarkdownConverter

_LINK = re.compile(
    r"^(?P<indent>[ \t]*)(?P<marker>[-*]\s*)?\[(?P<title>[^\]]+)\]"
    r"\((?P<url>[^)]*)\)\s*$"
)
_TITLE = re.compile(r"^(?P<marks>#{1,6})\s+(?P<title>.+?)\s*#*\s*$")
_MAX_EXCERPT = 110
_DEFAULT_TITLES = frozenset(
    {"summary", "contents", "table of contents", "index"}
)


@dataclass(frozen=True, slots=True)
class Chapter:
    """A book chapter or a structural entry in SUMMARY.md."""

    index: int
    title: str
    depth: int
    href: str
    path: Path | None
    external: bool = False
    group: bool = False


@dataclass(frozen=True, slots=True)
class Hit:
    """A matching line returned by book search."""

    chapter_index: int
    chapter_title: str
    line: int
    excerpt: str


class MdBook:
    def __init__(self, root: Path, output: Path | None = None) -> None:
        self.root = root.expanduser().resolve()
        self.config = self._read_config()
        self.source = self._path("book", "src", "src")
        self.output = self._path("build", "build-dir", "book")
        self.has_output = output is not None
        if output is not None:
            path = output.expanduser()
            self.output = path.resolve() if path.is_absolute() else (self.root / path).resolve()
        self.summary = self._summary()
        self.renderer, self.pages = self._pages()

    def _read_config(self) -> dict:
        path = self.root / "book.toml"
        try:
            config = (
                tomllib.loads(path.read_text(encoding="utf-8"))
                if path.is_file()
                else {}
            )
        except (OSError, ValueError) as error:
            raise ValueError(f"Invalid mdBook configuration at {path}: {error}") from error

        environment: dict = {}
        for name, raw in sorted(os.environ.items(), key=lambda pair: len(pair[0])):
            if not name.startswith("MDBOOK_"):
                continue
            keys = [part.lower().replace("_", "-") for part in name[7:].split("__")]
            if not keys or not keys[0]:
                continue
            try:
                value = json.loads(raw)
            except ValueError:
                value = raw
            self._set_value(environment, keys, value)
        return self._merge(config, environment)

    @staticmethod
    def _set_value(config: dict, keys: list[str], value: object) -> None:
        for key in keys[:-1]:
            child = config.setdefault(key, {})
            if not isinstance(child, dict):
                return
            config = child
        config[keys[-1]] = value

    @classmethod
    def _merge(cls, config: dict, overrides: dict) -> dict:
        for key, value in overrides.items():
            current = config.get(key)
            if isinstance(current, dict) and isinstance(value, dict):
                config[key] = cls._merge(current, value)
            else:
                config[key] = value
        return config

    def _path(self, section: str, key: str, default: str) -> Path:
        values = self.config.get(section, {})
        value = values.get(key, default) if isinstance(values, dict) else default
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"{section}.{key} must be a non-empty path string")
        path = Path(value).expanduser()
        return path.resolve() if path.is_absolute() else (self.root / path).resolve()

    def _summary(self) -> Path:
        for path in (self.root / "SUMMARY.md", self.source / "SUMMARY.md"):
            if path.is_file():
                return path
        raise FileNotFoundError(
            f"{self.root} has no SUMMARY.md at its root or in {self.source}"
        )

    def _pages(self) -> tuple[str, Path]:
        outputs = self.config.get("output", {})
        if not isinstance(outputs, dict):
            raise ValueError("The mdBook [output] setting must be a table")
        if not outputs:
            renderer = "html"
        elif "html" in outputs:
            renderer = "html"
        elif "markdown" in outputs:
            renderer = "markdown"
        else:
            raise ValueError("book-read requires [output.html] or [output.markdown]")
        has_many = bool(outputs) and len(outputs) > 1
        expected = self.output / renderer if has_many else self.output
        suffix = ".html" if renderer == "html" else ".md"
        paths = [expected, self.output]
        if renderer == "html":
            paths.extend((self.output / "html", self.root))
        else:
            paths.append(self.output / "markdown")
        for path in dict.fromkeys(paths):
            if path.is_dir() and next(path.rglob(f"*{suffix}"), None) is not None:
                return renderer, path
        return renderer, expected

    def page(self, url: str) -> Path | None:
        link = urlsplit(url)
        if link.scheme or link.netloc or not link.path:
            return None
        relative = PurePosixPath(unquote(link.path).lstrip("/"))
        if relative == PurePosixPath("README.md"):
            suffix = ".html" if self.renderer == "html" else ".md"
            relative = PurePosixPath(f"index{suffix}")
        elif relative.suffix.lower() == ".md" and self.renderer == "html":
            relative = relative.with_suffix(".html")
        elif relative.suffix.lower() == ".html" and self.renderer == "markdown":
            relative = relative.with_suffix(".md")
        elif not relative.suffix:
            suffix = ".html" if self.renderer == "html" else ".md"
            relative = relative.with_suffix(suffix)
        path = (self.pages / Path(*relative.parts)).resolve()
        try:
            path.relative_to(self.pages.resolve())
        except ValueError:
            return None
        return path if path.is_file() else None

    def build(self) -> None:
        executable = shutil.which("mdbook")
        if executable is None:
            raise FileNotFoundError(
                "mdbook was not found on PATH; install mdBook to build this book"
            )
        command = [executable, "build"]
        if self.has_output:
            command.extend(("--dest-dir", str(self.output)))
        try:
            result = subprocess.run(
                command, cwd=self.root, capture_output=True, text=True, timeout=300
            )
        except subprocess.TimeoutExpired as error:
            raise RuntimeError("mdbook build exceeded the 5-minute time limit") from error
        if result.returncode:
            lines = (result.stderr or result.stdout).strip().splitlines()
            detail = lines[-1] if lines else "No details were provided."
            raise RuntimeError(f"mdbook build failed: {detail}")

    def has_pages(self) -> bool:
        suffix = ".html" if self.renderer == "html" else ".md"
        return self.pages.is_dir() and next(self.pages.rglob(f"*{suffix}"), None) is not None

    def title(self) -> str:
        book = self.config.get("book", {})
        title = book.get("title") if isinstance(book, dict) else None
        return str(title).strip() if title else ""


class Book:
    """Loaded book with chapter lookup, lazy Markdown conversion, and search."""

    def __init__(
        self,
        root: Path,
        mdbook: MdBook | None = None,
        converter: MarkdownConverter | None = None,
    ) -> None:
        self.root = root.expanduser().resolve()
        self.mdbook = mdbook or MdBook(self.root)
        self.converter = converter or MarkdownConverter()
        self.pages = self.mdbook.pages
        self.chapters = self._read_summary(self.mdbook.summary, self.mdbook)
        if not any(not chapter.group for chapter in self.chapters):
            raise ValueError(f"{self.mdbook.summary} has no chapters with matching output pages")
        self.title = self.mdbook.title() or self.root.name
        self._cache: dict[int, str] = {}

    @staticmethod
    def _read_summary(summary: Path, mdbook: MdBook) -> list[Chapter]:
        entries = Book._read_entries(summary)
        return Book._make_chapters(entries, mdbook)

    @staticmethod
    def _read_entries(summary: Path) -> list[tuple[int, str, str, bool]]:
        entries: list[tuple[int, str, str, bool]] = []
        levels: dict[int, int] = {}
        depth = 0
        for line in summary.read_text(encoding="utf-8").splitlines():
            if not line.strip() or re.fullmatch(r"-{3,}", line.strip()):
                continue
            title = _TITLE.match(line)
            if title:
                name = title.group("title").strip()
                if name.casefold() in _DEFAULT_TITLES:
                    continue
                depth = len(title.group("marks")) - 1
                entries.append((depth, name, "", True))
                continue
            entry = _LINK.match(line)
            if not entry:
                continue
            indent = len(entry.group("indent").expandtabs(2))
            level = levels.setdefault(indent, len(levels))
            url = entry.group("url").strip()
            entries.append((depth + 1 + level, entry.group("title"), url, False))
        return entries

    @staticmethod
    def _make_chapters(
        entries: list[tuple[int, str, str, bool]], mdbook: MdBook
    ) -> list[Chapter]:
        chapters: list[Chapter] = []
        for depth, name, url, is_group in entries:
            link = urlsplit(url)
            if is_group:
                chapter = Chapter(len(chapters), name, depth, "", None, group=True)
            elif link.scheme or link.netloc:
                chapter = Chapter(len(chapters), name, depth, url, None, external=True)
            elif not url:
                chapter = Chapter(len(chapters), name, depth, "", None)
            else:
                path = mdbook.page(url)
                if path is None:
                    continue
                chapter = Chapter(len(chapters), name, depth, url, path)
            chapters.append(chapter)
        return chapters

    @classmethod
    def open(
        cls,
        root: Path,
        allow_build: bool = True,
        output: Path | None = None,
    ) -> Book:
        mdbook = MdBook(root, output)
        if not mdbook.has_pages():
            if not allow_build:
                raise FileNotFoundError(
                    "Generated pages are missing. Allow a build or generate them with mdBook."
                )
            mdbook.build()
        return cls(mdbook.root, mdbook)

    def __len__(self) -> int:
        return len(self.chapters)

    def chapter(self, index: int) -> Chapter:
        return self.chapters[max(0, min(index, len(self.chapters) - 1))]

    def markdown(self, chapter: Chapter) -> str:
        if chapter.index in self._cache:
            return self._cache[chapter.index]
        if chapter.external:
            text = f"# {chapter.title}\n\nExternal link: {chapter.href}\n"
        elif chapter.path is None:
            text = f"# {chapter.title}\n\nThis chapter has no generated page.\n"
        elif chapter.path.suffix.lower() == ".md":
            text = chapter.path.read_text(encoding="utf-8")
        else:
            text = self.converter.convert_file(chapter.path)
        self._cache[chapter.index] = text
        return text

    def filter_titles(self, needle: str) -> list[Chapter]:
        needle = needle.strip().lower()
        if not needle:
            return list(self.chapters)
        return [chapter for chapter in self.chapters if needle in chapter.title.lower()]

    def search(self, needle: str, limit: int = 150) -> list[Hit]:
        needle = needle.strip().lower()
        if not needle:
            return []
        hits: list[Hit] = []
        for chapter in self.chapters:
            if chapter.external or chapter.group or chapter.path is None:
                continue
            for number, line in enumerate(self.markdown(chapter).splitlines(), start=1):
                column = line.lower().find(needle)
                if column < 0:
                    continue
                start = max(0, column - 30)
                excerpt = line[start : start + _MAX_EXCERPT].strip()
                hits.append(Hit(chapter.index, chapter.title, number, excerpt))
                if len(hits) >= limit:
                    return hits
        return hits


def load_book(root: Path, allow_build: bool = True, output: Path | None = None) -> Book:
    root = root.expanduser().resolve()
    if not root.exists():
        raise FileNotFoundError(f"Book directory does not exist: {root}")
    return Book.open(root, allow_build, output)
