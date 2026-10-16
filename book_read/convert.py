"""Convert generated mdBook HTML to Markdown for terminal rendering.

mdBook emits predictable chapter HTML, so a single-pass parser avoids dependencies.
"""

from __future__ import annotations

import re
from html.parser import HTMLParser
from pathlib import Path

_SKIP = frozenset(
    {
        "script",
        "style",
        "svg",
        "nav",
        "header",
        "footer",
        "aside",
        "button",
        "select",
        "template",
        "iframe",
    }
)
_SKIP_VOID = frozenset({"link", "meta"})
_HEADINGS = {"h1": 1, "h2": 2, "h3": 3, "h4": 4, "h5": 5, "h6": 6}
_WHITESPACE = re.compile(r"[ \t\r\n]+")


class ChapterParser(HTMLParser):
    """Acumula blocos Markdown a partir da subtree <main> de uma mdBook page."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.blocks: list[str] = []
        self._skip = 0
        self._inside_main = False
        self._code: list[str] | None = None
        self._code_lang = ""
        self._inline: list[str] = []
        self._marker = ""
        self._list_depth = 0
        self._quote = 0
        self._href: str | None = None
        self._link_text: list[str] = []
        self._table: list[list[str]] = []
        self._row: list[str] | None = None
        self._cell: list[str] | None = None

    def _sink(self) -> list[str]:
        if self._href is not None:
            return self._link_text
        if self._cell is not None:
            return self._cell
        return self._inline

    @staticmethod
    def _take(parts: list[str]) -> str:
        text = "".join(parts)
        parts.clear()
        return _WHITESPACE.sub(" ", text).strip()

    @staticmethod
    def _language(class_attr: str) -> str:
        for part in class_attr.split():
            if part.startswith("language-"):
                return part[len("language-") :].split()[0]
        return ""

    def _flush_inline(self) -> None:
        marker, self._marker = self._marker, ""
        text = self._take(self._inline)
        if not text:
            return
        self.blocks.append(f"> {marker}{text}" if self._quote else f"{marker}{text}")

    def _flush_link(self) -> None:
        href, self._href = self._href, None
        text = self._take(self._link_text)
        if not text:
            return
        if not href or href.startswith("#") or not href.startswith(("http://", "https://")):
            self._inline.append(text)
        else:
            self._inline.append(f"[{text}]({href})")

    def _flush_code(self) -> None:
        code, self._code = self._code, None
        lang, self._code_lang = self._code_lang, ""
        if code is None:
            return
        lines = "".join(code).split("\n")
        while lines and not lines[0].strip():
            lines.pop(0)
        while lines and not lines[-1].strip():
            lines.pop()
        if not lines:
            return
        body = "\n".join(lines)
        fence = "~~~" if "```" in body else "```"
        self.blocks.append(f"{fence}{lang}\n{body}\n{fence}")

    def _flush_table(self) -> None:
        rows = [row for row in self._table if any(cell.strip() for cell in row)]
        self._table = []
        if not rows:
            return
        width = max(len(row) for row in rows)
        cells = (" --- " for _ in range(width))
        lines = ["| " + " | ".join(c.replace("|", "\\|") for c in row) + " |" for row in rows]
        lines.insert(1, "|" + "|".join(cells) + "|")
        self.blocks.append("\n".join(lines))

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attributes = {key: value or "" for key, value in attrs}
        if tag in _SKIP_VOID:
            return
        if tag in _SKIP:
            self._skip += 1
            return
        if self._skip:
            return
        if tag == "main":
            self._inside_main = True
            return
        if not self._inside_main:
            return
        if tag in _HEADINGS:
            self._flush_inline()
            self._marker = "#" * _HEADINGS[tag] + " "
            return
        if tag in {"p", "figcaption"}:
            self._flush_inline()
            return
        if tag in {"ul", "ol"}:
            self._list_depth += 1
            return
        if tag == "li":
            self._flush_inline()
            self._marker = "  " * max(0, self._list_depth - 1) + "- "
            return
        if tag == "blockquote":
            self._flush_inline()
            self._quote += 1
            return
        if tag == "pre":
            self._flush_inline()
            self._code = []
            self._code_lang = self._language(attributes.get("class", ""))
            return
        if tag == "code":
            if self._code is not None:
                self._code_lang = self._language(attributes.get("class", "")) or self._code_lang
            else:
                self._sink().append("`")
            return
        if tag in {"strong", "b"}:
            self._sink().append("**")
            return
        if tag in {"em", "i"}:
            self._sink().append("*")
            return
        if tag == "a":
            self._flush_link()
            self._href = attributes.get("href", "")
            return
        if tag == "br":
            self._sink().append(" ")
            return
        if tag == "hr":
            self._flush_inline()
            self.blocks.append("---")
            return
        if tag == "img":
            alt, src = attributes.get("alt", "").strip(), attributes.get("src", "")
            if alt or src:
                self._flush_inline()
                self.blocks.append(f"![{alt}]({src})")
            return
        if tag == "listing":
            self._flush_inline()
            label = f"Listing {attributes['number']}" if attributes.get("number") else ""
            caption = attributes.get("caption", "").strip()
            heading = " — ".join(part for part in (label, caption) if part)
            if heading:
                self.blocks.append(f"*{heading}*")
            return
        if tag == "table":
            self._flush_inline()
            self._table = []
            return
        if tag == "tr":
            self._row = []
            return
        if tag in {"td", "th"}:
            self._cell = []
            return

    def handle_endtag(self, tag: str) -> None:
        if tag in _SKIP:
            if self._skip:
                self._skip -= 1
            return
        if self._skip or not self._inside_main:
            return
        if tag == "main":
            self._flush_code()
            self._flush_inline()
            self._inside_main = False
            return
        if tag in _HEADINGS or tag in {"p", "figcaption", "li"}:
            self._flush_inline()
            return
        if tag in {"ul", "ol"}:
            self._list_depth = max(0, self._list_depth - 1)
            return
        if tag == "blockquote":
            self._flush_inline()
            self._quote = max(0, self._quote - 1)
            return
        if tag == "pre":
            self._flush_code()
            return
        if tag == "code":
            if self._code is None:
                self._sink().append("`")
            return
        if tag in {"strong", "b"}:
            self._sink().append("**")
            return
        if tag in {"em", "i"}:
            self._sink().append("*")
            return
        if tag == "a":
            self._flush_link()
            return
        if tag == "table":
            self._flush_table()
            return
        if tag == "tr":
            if self._row is not None:
                self._table.append(self._row)
            self._row = None
            return
        if tag in {"td", "th"}:
            if self._cell is not None and self._row is not None:
                self._row.append(self._take(self._cell))
            self._cell = None
            return

    def handle_data(self, data: str) -> None:
        if self._skip or not self._inside_main:
            return
        if self._code is not None:
            self._code.append(data)
            return
        self._sink().append(data)


class MarkdownConverter:
    def convert_html(self, html: str, title: str | None = None) -> str:
        parser = ChapterParser()
        parser.feed(html)
        parser.close()
        blocks = list(parser.blocks)
        if title:
            blocks.insert(0, f"# {title}")
        return "\n\n".join(block for block in blocks if block).strip() + "\n"

    def convert_file(self, path: Path) -> str:
        html = path.read_text(encoding="utf-8", errors="replace")
        return self.convert_html(html)
