# Development

## Environment

The project requires Python 3.11 or later and Textual `>=8.2.8,<9`. Git and
mdBook are needed for `book-download`; mdBook is also needed when a local book
has no generated pages and automatic building is enabled.

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -e .
```

## Project layout

- `book_read/__main__.py`: reader CLI and language commands.
- `book_read/download.py`: download prompts, Git clone, and mdBook build.
- `book_read/library.py`: local paths and downloaded book lookup.
- `book_read/language.py`: gettext catalogs and language preference.
- `book_read/book.py`: mdBook configuration, summary parsing, chapter cache,
  and search.
- `book_read/convert.py`: HTML parser and Markdown conversion.
- `book_read/app.py`: Textual widgets, keyboard actions, and reader state.
- `locale/book_read.pot`: translatable reader strings.
- `tests/test_book_read.py`: reader and conversion coverage.

## Tests

Run the standard-library test suite with:

```sh
.venv/bin/python -m unittest discover -s tests
```

The tests use temporary book projects and do not download external content.
