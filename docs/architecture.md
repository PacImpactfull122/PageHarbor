# Architecture

## Entry points and storage

`book_read.__main__` implements `book-read`; `book_read.download` implements
`book-download`. Both commands use `BookLibrary` to resolve the platform data
directory. On Linux and macOS it honors `XDG_DATA_HOME`, otherwise it uses
`~/.local/share/book-read`; on Windows it uses `%LOCALAPPDATA%/book-read`.
Downloaded projects are stored in `books/<name>`, language catalogs in
`languages/<locale>/LC_MESSAGES/book_read.mo`, and reader preferences in
`settings.json` and `state.json`.

`book-read <name>` checks the library first, then treats the input as a local
path. A book name is restricted to lowercase letters, digits, and hyphens before
it is joined to the library path.

## mdBook loading

`MdBook` reads `book.toml`, applies `MDBOOK_*` environment overrides, and
resolves `[book].src`, `[build].build-dir`, and the selected renderer. With
multiple renderers, it locates HTML or Markdown output under the renderer
subdirectory. `--dest-dir` overrides the configured output directory.

`Book.open` runs `mdbook build` only when pages are missing and builds are
allowed. `book-download` uses a separate flow: it clones to a temporary
folder, asks for explicit trust before `mdbook build`, validates the generated
book, removes `.git`, and moves the result into the library. Clone and build
commands use argument arrays rather than a shell and have a five-minute timeout.
The download URL must use HTTPS without credentials, a query, or a fragment.
The accepted hosts are GitHub, GitLab, Codeberg, Bitbucket, SourceHut, and
Gitea.com; this host allowlist prevents a crafted URL from targeting local
services.

See the official mdBook references for
[configuration](https://rust-lang.github.io/mdBook/format/configuration/general.html),
[environment variables](https://rust-lang.github.io/mdBook/format/configuration/environment-variables.html),
[renderers](https://rust-lang.github.io/mdBook/format/configuration/renderers.html),
and the [`SUMMARY.md` format](https://rust-lang.github.io/mdBook/format/summary.html).

## Chapters and conversion

`Book` follows `SUMMARY.md` order, reads section headings and nested lists,
keeps external links as entries, and skips local links that escape the generated
pages directory. Each chapter is converted on demand and cached. Search is
case-insensitive and returns up to 150 matching lines.

`convert.py` uses Python's standard-library `html.parser.HTMLParser`. It reads
`<main>` and converts common headings, paragraphs, lists, quotes, code, links,
images, tables, and listing blocks to Markdown. Navigation elements and scripts
are ignored. Generated Markdown output is read directly.

## Language catalogs

`LanguagePack` manages `.mo` files using Python's `gettext` module. English is
source text and needs no catalog. Additional catalogs are validated, limited to
2 MiB, installed in the user's data directory, and selected in `settings.json`.
No translation package is bundled. `locale/book_read.pot` lists the reader
strings that language packs can translate.

## Terminal interface and state

`BookTUI` renders chapters with Textual's Markdown widget and manages the table
of contents, search, chapter navigation, filtering, and themes. The selected
chapter and theme are stored in `state.json`. A saved chapter is restored only
when its project path matches the current book.

## Current limits

- Third-party renderer output is not parsed; use the built-in HTML or Markdown
  renderer.
- Building a book can execute configured preprocessors and commands. Approve a
  build only when the source is trusted.
- External links and remotely hosted assets are not mirrored for offline use.
- Search scans the book on its first query and caps results at 150 matches.
- The HTML converter handles common chapter markup; custom themes and
  preprocessor-generated structures may lose formatting.
