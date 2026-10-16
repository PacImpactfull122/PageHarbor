"""Read mdBook projects and downloaded books in the terminal."""

__version__ = "1.0.0"

from .book import Book, Chapter, Hit, load_book

__all__ = ["Book", "Chapter", "Hit", "load_book", "__version__"]
