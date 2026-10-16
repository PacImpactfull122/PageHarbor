"""Installable gettext catalogs and the user's interface language."""

from __future__ import annotations

import gettext
import json
import os
import re
import shutil
import struct
import tempfile
from pathlib import Path

from .library import BookLibrary


class LanguagePack:
    _LOCALE = re.compile(r"^[a-z]{2,3}(?:_[A-Z]{2})?$")
    _MAX_BYTES = 2 * 1024 * 1024
    _DOMAIN = "book_read"

    def __init__(self, library: BookLibrary) -> None:
        self.library = library
        self._selected = self._read_selected()
        self._catalog = self._load_catalog()

    @property
    def selected(self) -> str:
        return self._selected

    def available(self) -> list[str]:
        locales = ["en"]
        if self.library.languages.is_dir():
            for path in self.library.languages.iterdir():
                catalog = path / "LC_MESSAGES" / f"{self._DOMAIN}.mo"
                if self._LOCALE.fullmatch(path.name) and catalog.is_file():
                    locales.append(path.name)
        return sorted(set(locales))

    def gettext(self, message: str) -> str:
        return self._catalog.gettext(message)

    def _load_catalog(self) -> gettext.NullTranslations:
        return gettext.translation(
            self._DOMAIN,
            localedir=self.library.languages,
            languages=[self._selected],
            fallback=True,
        )

    def choose(self, locale: str) -> None:
        if locale not in self.available():
            raise ValueError(f"Language '{locale}' is not installed.")
        self._selected = locale
        self._catalog = self._load_catalog()
        self._write_selected(locale)

    def install(self, locale: str, source: Path) -> Path:
        if not self._LOCALE.fullmatch(locale) or locale == "en":
            raise ValueError("Use a locale such as 'pt_BR'; English is built in.")
        source = source.expanduser().resolve(strict=True)
        if not source.is_file() or source.stat().st_size > self._MAX_BYTES:
            raise ValueError("The catalog must be a file no larger than 2 MiB.")
        try:
            with source.open("rb") as stream:
                gettext.GNUTranslations(stream)
        except (OSError, EOFError, ValueError, struct.error) as error:
            raise ValueError("The file is not a valid gettext .mo catalog.") from error

        target = self.library.languages / locale / "LC_MESSAGES" / f"{self._DOMAIN}.mo"
        target.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(dir=target.parent, delete=False) as stream:
            temp = Path(stream.name)
            with source.open("rb") as catalog:
                shutil.copyfileobj(catalog, stream)
        os.replace(temp, target)
        return target

    def _read_selected(self) -> str:
        try:
            settings = json.loads(self.library.settings.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return "en"
        selected = settings.get("language", "en") if isinstance(settings, dict) else "en"
        return selected if selected in self.available() else "en"

    def _write_selected(self, locale: str) -> None:
        self.library.root.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", dir=self.library.root, delete=False
        ) as stream:
            temp = Path(stream.name)
            json.dump({"language": locale}, stream)
            stream.write("\n")
        os.replace(temp, self.library.settings)
