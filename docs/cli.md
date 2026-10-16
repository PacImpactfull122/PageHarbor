# Command reference

## `book-read`

Open a local mdBook project, a generated output directory, or a downloaded book
by its access name:

```sh
book-read /path/to/project
book-read /path/to/generated/book
book-read rust-book
book-read /path/to/project --theme tokyo-night
book-read /path/to/project --no-build
book-read /path/to/project --trust
book-read /path/to/project --dest-dir public
```

For a downloaded book, its access name is the value selected during
`book-download` or passed with `--name`. Names use lowercase letters, numbers,
and hyphens. A name that is not installed is treated as a local path.

The input directory may contain `book.toml` and `SUMMARY.md`, `src/SUMMARY.md`
with configured output, or generated HTML/Markdown pages and a matching
`SUMMARY.md`. The reader honors `book.src`, `build.build-dir`, and corresponding
`MDBOOK_*` environment variables. `--dest-dir` overrides the configured output
path and is resolved from the project root.

For multiple renderers, generated pages are expected in the renderer's output
subdirectory. The built-in HTML and Markdown renderers are supported; third-party
renderer output is not interpreted.

When generated pages are missing, `book-read` asks before running `mdbook
build`. A build may execute configured preprocessors and commands. Use `--trust`
to allow it without a prompt or `--no-build` to require existing pages.

## `book-download`

Clone a public HTTPS Git repository, build its mdBook, and store the result in
the local book library:

```sh
book-download https://github.com/owner/repository
book-download https://github.com/owner/repository --name guide --language en --trust
```

In a terminal, the command offers installed languages, suggests a name from the
repository URL, and asks whether it may run `mdbook build`. In a non-interactive
shell, pass `--name`, `--language`, and `--trust` explicitly. `--trust` permits
configured preprocessors and commands to run; use it only for a repository you
trust.

The downloader accepts GitHub, GitLab, Codeberg, Bitbucket, SourceHut, and
Gitea.com repository hosts. The local copy retains source and generated files,
then removes Git metadata. It does not mirror remote URLs or assets. The saved
book is opened as
`book-read <name>`.

## `book-read language`

Manage the reader's interface language. English (`en`) is built in; other
languages are installed from compiled gettext catalogs using the `book_read`
domain. Translate `locale/book_read.pot`, compile a `.po` file with `msgfmt`,
then install the resulting `.mo` catalog:

```sh
book-read language
book-read language list
book-read language install pt_BR ./book_read.mo
book-read language set pt_BR
```

Locale names use lowercase language codes with an optional uppercase region,
for example `pt_BR`. Catalog files are limited to 2 MiB and stored under the
application data directory.

## Keyboard shortcuts

| Key | Action |
| --- | --- |
| `Tab` | Switch focus between the table of contents and chapter text |
| Arrow keys, `Page Up`, `Page Down` | Scroll the chapter when it has focus |
| `]` / `[` | Open the next / previous readable chapter |
| `g` | Open the chapter-number dialog |
| `/` | Focus the title filter |
| `Enter` in the filter | Open the first matching entry |
| `Ctrl+F` | Search all readable chapters |
| `Enter` in search | Open the selected result |
| `t` | Switch to the next Textual theme |
| `r` | Reload the current chapter from disk |
| `Esc` | Clear the filter or return focus to the chapter |
| `?` / `F1` | Show keyboard help |
| `q` | Quit |

In the table of contents, arrows move the selection and `Enter` opens the
chapter. In search, `Esc` closes the dialog.
