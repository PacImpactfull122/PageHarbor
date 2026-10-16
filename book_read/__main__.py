"""Command-line entry point for the book-read terminal reader."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .app import BookTUI
from .book import Book, MdBook
from .language import LanguagePack
from .library import BookLibrary


class Reader:
    def __init__(self, library: BookLibrary) -> None:
        self.library = library

    def open(
        self,
        name: str,
        output: Path | None,
        no_build: bool,
        trust: bool,
    ) -> Book:
        installed = self.library.find(name)
        root = installed or Path(name).expanduser()
        mdbook = MdBook(root, output)
        missing = not mdbook.has_pages()
        if missing and no_build:
            raise FileNotFoundError(
                "Generated pages are missing. Build this project with mdBook first."
            )
        if missing:
            self._confirm_build(trust)
            mdbook.build()
        return Book(mdbook.root, mdbook)

    @staticmethod
    def _confirm_build(trust: bool) -> None:
        if trust:
            return
        if not sys.stdin.isatty():
            raise PermissionError(
                "Pass --trust to allow mdbook build to run configured project commands."
            )
        answer = input(
            "mdbook build can run configured preprocessors and commands. "
            "Continue only if you trust this project. Build it? [y/N]: "
        ).strip().lower()
        if answer not in {"y", "yes"}:
            raise PermissionError("Build cancelled.")


def language_main(argv: list[str]) -> int:
    library = BookLibrary()
    language = LanguagePack(library)
    parser = argparse.ArgumentParser(prog="book-read language")
    actions = parser.add_subparsers(dest="action")
    actions.add_parser("list", help="list installed interface languages")
    install = actions.add_parser("install", help="install a gettext .mo catalog")
    install.add_argument("locale", help="locale code, such as pt_BR")
    install.add_argument("catalog", type=Path, help="compiled gettext .mo file")
    choose = actions.add_parser("set", help="set the interface language")
    choose.add_argument("locale", help="installed locale code")
    args = parser.parse_args(argv)
    try:
        if args.action == "install":
            target = language.install(args.locale, args.catalog)
            print(f"Installed language catalog: {target}")
            return 0
        if args.action == "set":
            language.choose(args.locale)
            print(f"Interface language set to {args.locale}")
            return 0
        if args.action == "list":
            for locale in language.available():
                selected = " (current)" if locale == language.selected else ""
                print(f"{locale}{selected}")
            return 0
        if not sys.stdin.isatty():
            for locale in language.available():
                print(locale)
            return 0
        print("Installed interface languages:")
        for index, locale in enumerate(language.available(), start=1):
            selected = " (current)" if locale == language.selected else ""
            print(f"  {index}. {locale}{selected}")
        answer = input(f"Choose a language [{language.selected}]: ").strip()
        if not answer:
            return 0
        choices = language.available()
        if answer.isdigit() and 1 <= int(answer) <= len(choices):
            answer = choices[int(answer) - 1]
        language.choose(answer)
        print(f"Interface language set to {answer}")
    except (OSError, ValueError) as error:
        parser.exit(2, f"book-read language: {error}\n")
    return 0


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if args[:1] == ["language"]:
        return language_main(args[1:])

    parser = argparse.ArgumentParser(
        prog="book-read",
        description="Read any local mdBook project or downloaded book in the terminal.",
        epilog="Run 'book-read language' to manage interface languages.",
    )
    parser.add_argument("book", nargs="?", help="downloaded book name or local mdBook path")
    parser.add_argument("--theme", help="initial Textual theme")
    parser.add_argument(
        "--no-build",
        action="store_true",
        help="do not run mdbook build when generated pages are missing",
    )
    parser.add_argument(
        "--trust",
        action="store_true",
        help="allow mdbook build to run configured project preprocessors and commands",
    )
    parser.add_argument(
        "--dest-dir",
        type=Path,
        help="mdBook output directory, relative to the project root",
    )
    options = parser.parse_args(args)
    if options.book is None:
        parser.print_help()
        return 0

    library = BookLibrary()
    language = LanguagePack(library)
    try:
        book = Reader(library).open(
            options.book,
            options.dest_dir,
            options.no_build,
            options.trust,
        )
    except (OSError, ValueError, RuntimeError) as error:
        parser.exit(2, f"book-read: {error}\n")
    tui = BookTUI.for_language(language.gettext)(
        book,
        theme=options.theme,
        translate=language.gettext,
        state_path=library.state,
    )
    tui.run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
