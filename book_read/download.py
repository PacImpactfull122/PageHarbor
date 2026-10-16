"""Download and build an offline copy of an mdBook Git repository."""

from __future__ import annotations

import argparse
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from urllib.parse import urlsplit

from .book import load_book
from .language import LanguagePack
from .library import BookLibrary


class BookDownload:
    _SLUG = re.compile(r"[^a-z0-9]+")
    _TIMEOUT_S = 300
    _HOSTS = frozenset(
        {"github.com", "gitlab.com", "codeberg.org", "bitbucket.org", "git.sr.ht", "gitea.com"}
    )

    def __init__(self, library: BookLibrary) -> None:
        self.library = library

    def run(self, repository: str, name: str, trust: bool) -> Path:
        url = self._repository(repository)
        target = self.library.path(name)
        if target.exists() or target.is_symlink():
            raise FileExistsError(f"A book named '{name}' is already installed.")
        git = shutil.which("git")
        mdbook = shutil.which("mdbook")
        if git is None:
            raise FileNotFoundError("Git was not found on PATH.")
        if mdbook is None:
            raise FileNotFoundError("mdbook was not found on PATH; install mdBook first.")
        if not trust:
            raise PermissionError("Building this repository requires explicit trust.")

        self.library.prepare()
        with tempfile.TemporaryDirectory(dir=self.library.root) as temporary:
            source = Path(temporary) / "source"
            self._clone(git, url, source)
            self._build(mdbook, source)
            load_book(source, allow_build=False)
            shutil.rmtree(source / ".git")
            source.replace(target)
        return target

    @staticmethod
    def default_name(repository: str) -> str:
        path = urlsplit(repository).path.rstrip("/")
        raw = path.rsplit("/", 1)[-1]
        if raw.endswith(".git"):
            raw = raw[:-4]
        slug = BookDownload._SLUG.sub("-", raw.lower()).strip("-")
        return slug or "book"

    @staticmethod
    def _repository(repository: str) -> str:
        parsed = urlsplit(repository)
        if (
            parsed.scheme != "https"
            or not parsed.hostname
            or parsed.hostname.lower() not in BookDownload._HOSTS
            or parsed.port not in (None, 443)
            or parsed.username
            or parsed.password
            or parsed.query
            or parsed.fragment
            or not parsed.path.strip("/")
        ):
            raise ValueError("Use a public HTTPS Git repository URL without credentials.")
        return repository

    def _clone(self, git: str, url: str, target: Path) -> None:
        config = target.parent / "gitconfig"
        config.touch()
        environment = os.environ.copy()
        environment["GIT_CONFIG_NOSYSTEM"] = "1"
        environment["GIT_CONFIG_GLOBAL"] = str(config)
        environment["GIT_TERMINAL_PROMPT"] = "0"
        environment.pop("GIT_ASKPASS", None)
        environment.pop("GIT_CONFIG_PARAMETERS", None)
        environment.pop("GIT_CONFIG_COUNT", None)
        try:
            result = subprocess.run(
                [git, "clone", "--depth", "1", "--", url, str(target)],
                capture_output=True,
                text=True,
                timeout=self._TIMEOUT_S,
                check=False,
                env=environment,
            )
        except subprocess.TimeoutExpired as error:
            raise RuntimeError("Git clone exceeded the 5-minute time limit.") from error
        if result.returncode:
            detail = (result.stderr or result.stdout).strip().splitlines()
            raise RuntimeError(detail[-1] if detail else "Git clone failed.")

    def _build(self, mdbook: str, source: Path) -> None:
        try:
            result = subprocess.run(
                [mdbook, "build"],
                cwd=source,
                capture_output=True,
                text=True,
                timeout=self._TIMEOUT_S,
                check=False,
            )
        except subprocess.TimeoutExpired as error:
            raise RuntimeError("mdbook build exceeded the 5-minute time limit.") from error
        if result.returncode:
            detail = (result.stderr or result.stdout).strip().splitlines()
            raise RuntimeError(detail[-1] if detail else "mdbook build failed.")


class DownloadWizard:
    def __init__(self, language: LanguagePack, library: BookLibrary) -> None:
        self.language = language
        self.library = library
        self.download = BookDownload(library)

    def run(self, args: list[str] | None = None) -> int:
        parser = argparse.ArgumentParser(
            prog="book-download",
            description="Download and build an offline mdBook from a Git repository.",
        )
        parser.add_argument("repository", help="public HTTPS Git repository URL")
        parser.add_argument("--name", help="access name used with 'book-read <name>'")
        parser.add_argument(
            "--language", help="installed interface language, such as en"
        )
        parser.add_argument(
            "--trust",
            action="store_true",
            help="allow mdbook build to run project preprocessors",
        )
        options = parser.parse_args(args)
        try:
            locale = self._select_language(options.language)
            name = self._select_name(options.name, options.repository)
            trust = self._confirm_build(options.trust)
            target = self.download.run(options.repository, name, trust)
            self.language.choose(locale)
        except (OSError, RuntimeError, ValueError) as error:
            parser.exit(2, f"book-download: {error}\n")
        print(f"Offline book installed at {target}")
        print(f"Open it with: book-read {name}")
        return 0

    def _select_language(self, requested: str | None) -> str:
        choices = self.language.available()
        if requested:
            if requested not in choices:
                raise ValueError(f"Language '{requested}' is not installed.")
            return requested
        if not sys.stdin.isatty():
            return self.language.selected
        print("Available interface languages:")
        for index, locale in enumerate(choices, start=1):
            current = " (current)" if locale == self.language.selected else ""
            print(f"  {index}. {locale}{current}")
        answer = input(f"Choose a language [{self.language.selected}]: ").strip()
        if not answer:
            return self.language.selected
        if answer.isdigit() and 1 <= int(answer) <= len(choices):
            return choices[int(answer) - 1]
        if answer in choices:
            return answer
        raise ValueError("Choose an installed language by number or locale.")

    def _select_name(self, requested: str | None, repository: str) -> str:
        default = requested or self.download.default_name(repository)
        if requested or not sys.stdin.isatty():
            self.library.path(default)
            return default
        answer = input(f"Access name for 'book-read' [{default}]: ").strip()
        name = answer or default
        self.library.path(name)
        return name

    @staticmethod
    def _confirm_build(trust: bool) -> bool:
        if trust:
            return True
        if not sys.stdin.isatty():
            raise PermissionError(
                "Pass --trust to allow mdbook build to run commands from this repository."
            )
        answer = input(
            "mdbook build can run configured preprocessors and commands. "
            "Continue only if you trust this repository. Build it? [y/N]: "
        ).strip().lower()
        if answer not in {"y", "yes"}:
            raise PermissionError("Build cancelled.")
        return True


def main(argv: list[str] | None = None) -> int:
    library = BookLibrary()
    language = LanguagePack(library)
    return DownloadWizard(language, library).run(argv)


if __name__ == "__main__":
    raise SystemExit(main())
