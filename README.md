# PageHarbor

PageHarbor provides two commands for mdBook projects: `book-read` opens a local
book in the terminal, and `book-download` clones and builds an offline copy
that can be read without contacting its Git repository again.

## Features

- Read HTML or Markdown output from any mdBook project.
- Follow the configured source directory, build directory, renderer, and
  `MDBOOK_*` environment overrides.
- Browse the table of contents, filter chapter titles, search chapter text,
  change Textual themes, and resume the last reading position.
- Store downloaded books under the user's application data directory and open
  them by a short name.
- Use English by default and install gettext language catalogs for other
  interface languages.

## Requirements

- Python 3.11 or later.
- Git and mdBook for `book-download`.
- mdBook for `book-read` only when generated pages are missing and a build is
  allowed.

## Install

```sh
python3 -m venv .venv
.venv/bin/python -m pip install .
```

The installation provides `book-read` and `book-download` in `.venv/bin`.

## Read a local book

Pass a project directory or an existing mdBook output directory:

```sh
book-read /path/to/book
book-read /path/to/book --theme nord
book-read /path/to/book --no-build
book-read /path/to/book --trust
book-read /path/to/book --dest-dir public
```

When no path is passed, the command prints help. If generated pages are
missing, `book-read` asks before running `mdbook build`; use `--trust` to allow
that build without a prompt or `--no-build` to require existing pages.

## Download an offline copy

Pass a public HTTPS Git repository URL. In an interactive terminal, the command
asks for an interface language, an access name, and confirmation before running
`mdbook build`:

```sh
book-download https://github.com/owner/book
```

Then open the saved copy with the selected name:

```sh
book-read book
```

The downloader currently accepts repositories hosted by GitHub, GitLab,
Codeberg, Bitbucket, SourceHut, and Gitea.com. For non-interactive use, provide
the choices explicitly. `--trust` authorizes `mdbook build` to run preprocessors
and commands configured by the repository:

```sh
book-download https://github.com/owner/book \
  --name rust-book \
  --language en \
  --trust
book-read rust-book
```

Names contain lowercase letters, numbers, and hyphens. A downloaded copy keeps
the repository files and generated book output but removes `.git` metadata.
Local images and generated content remain available; remote links and assets
are not mirrored.

## Interface languages

English is built in and is the only bundled language. List available languages,
choose one interactively, or install a compiled gettext `.mo` catalog:

```sh
book-read language list
book-read language
book-read language install pt_BR ./book_read.mo
book-read language set pt_BR
```

Translate a copy of [`locale/book_read.pot`](locale/book_read.pot), compile it
with `msgfmt -o book_read.mo book_read.po`, then install the `.mo` file. Catalogs
use the `book_read` gettext domain. The language is saved in the
application data directory. `book-download --language <locale>` selects an
already installed language during the download prompt.

## Keyboard shortcuts

| Key | Action |
| --- | --- |
| `Tab` | Switch focus between the table of contents and the chapter |
| Arrow keys, `Page Up`, `Page Down` | Scroll the chapter when it has focus |
| `]` / `[` | Open the next / previous chapter |
| `g` | Go to a chapter number |
| `/` | Focus the title filter |
| `Enter` in the filter | Open the first matching chapter |
| `Ctrl+F` | Search the book |
| `Enter` in search | Open the selected match |
| `t` | Switch to the next Textual theme |
| `r` | Reload the current chapter from disk |
| `Esc` | Clear the filter or return focus to the chapter |
| `?` / `F1` | Show keyboard help |
| `q` | Quit |

See [the command reference](docs/cli.md) and [architecture notes](docs/architecture.md).
For development setup and project structure, read [docs/development.md](docs/development.md).
