"""Terminal interface for reading, navigating, and searching mdBook chapters."""

from __future__ import annotations

import gettext
import json
from collections.abc import Callable, Iterator
from pathlib import Path

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.screen import ModalScreen
from textual.theme import BUILTIN_THEMES
from textual.widgets import (
    Footer,
    Header,
    Input,
    Label,
    ListItem,
    ListView,
    Markdown,
    Static,
    Tree,
)
from textual.widgets.tree import TreeNode

from .book import Book, Chapter, Hit

STATE_PATH = Path.home() / ".local/share/book-read/state.json"

HELP_TEXT = """\
Navigation
  tab          switch focus between table of contents and text
  arrows/pgup  scroll the text when it has focus
  ]  [         next / previous chapter
  g            go to a chapter number
  /            filter table of contents titles
  ctrl+f       search the whole book
  t            change the theme
  r            reload the current chapter from disk
  ?  F1        show this help
  q            quit

In the table of contents: arrows move, enter opens a chapter
In search: enter searches, arrows select a result, esc closes the dialog"""


class BookTUI(App[None]):
    """Terminal reader with a chapter tree, search, filtering, and themes."""

    BINDINGS = [
        Binding("q", "quit", "Quit"),
        Binding("question_mark", "help", "Help"),
        Binding("f1", "help", "Help"),
        Binding("right_square_bracket", "next_chapter", "Next"),
        Binding("left_square_bracket", "prev_chapter", "Previous"),
        Binding("g", "goto", "Go to"),
        Binding("slash", "filter", "Filter"),
        Binding("ctrl+f", "search", "Search"),
        Binding("t", "next_theme", "Theme"),
        Binding("tab", "swap_focus", "Focus"),
        Binding("r", "reload", "Reload"),
        Binding("escape", "clear_filter", "Clear filter"),
    ]

    CSS = """
    Screen { background: $background; }
    #body { height: 1fr; }
    #sidebar { width: 40; border-right: solid $panel; }
    #filter { height: 3; border: none; border-bottom: solid $panel; }
    #toc { height: 1fr; padding: 0 1; background: transparent; }
    #content { width: 1fr; }
    #scroller { height: 1fr; scrollbar-size-vertical: 1; }
    #page { padding: 1 3 0 3; }
    #hint { height: 1; color: $text-muted; padding: 0 3; }
    .dialog {
        width: 76;
        max-width: 90%;
        height: auto;
        border: round $accent;
        background: $surface;
        padding: 1 2;
    }
    .dialog-title { color: $accent; text-style: bold; }
    #search-results { height: 16; border: none; background: transparent; }
    #search-results:focus { border: none; }
    #search-empty { color: $text-muted; height: 1; }
    #help-body { height: auto; }
    """

    @classmethod
    def for_language(cls, translate: Callable[[str], str]) -> type[BookTUI]:
        bindings = [
            Binding("q", "quit", translate("Quit")),
            Binding("question_mark", "help", translate("Help")),
            Binding("f1", "help", translate("Help")),
            Binding("right_square_bracket", "next_chapter", translate("Next")),
            Binding("left_square_bracket", "prev_chapter", translate("Previous")),
            Binding("g", "goto", translate("Go to")),
            Binding("slash", "filter", translate("Filter")),
            Binding("ctrl+f", "search", translate("Search")),
            Binding("t", "next_theme", translate("Theme")),
            Binding("tab", "swap_focus", translate("Focus")),
            Binding("r", "reload", translate("Reload")),
            Binding("escape", "clear_filter", translate("Clear filter")),
        ]
        return type(
            "LocalizedBookTUI",
            (cls,),
            {"__module__": cls.__module__, "BINDINGS": bindings},
        )

    def __init__(
        self,
        book: Book,
        theme: str | None = None,
        translate: Callable[[str], str] = gettext.gettext,
        state_path: Path = STATE_PATH,
    ) -> None:
        super().__init__()
        self.book = book
        self.current = book.chapter(0)
        self.tr = translate
        self.state_path = state_path
        self._toc_nodes: dict[int, TreeNode] = {}
        self._pending_theme = theme

    def on_mount(self) -> None:
        saved = self._load_state()
        self.title = self.book.title
        self.sub_title = ""
        self.theme = self._resolve_theme(self._pending_theme or saved.get("theme"))
        self._build_toc(self.book.chapters)
        same_book = str(saved.get("book", "")) == str(self.book.root)
        start = int(saved.get("chapter", 0)) if same_book else 0
        self.open_chapter(self.book.chapter(start))
        self.query_one("#scroller", VerticalScroll).focus()

    def _build_toc(self, chapters: list[Chapter]) -> None:
        tree = self.query_one("#toc", Tree)
        tree.clear()
        self._toc_nodes.clear()
        parents: dict[int, TreeNode] = {}
        for chapter in chapters:
            parent = parents.get(chapter.depth - 1, tree.root)
            add = parent.add if chapter.group else parent.add_leaf
            node = add(chapter.title, data=chapter)
            self._toc_nodes[chapter.index] = node
            parents[chapter.depth] = node
        tree.root.expand()
        for node in self._toc_nodes.values():
            if node.data is not None and node.data.depth <= 1:
                node.expand()

    def on_tree_node_selected(self, event: Tree.NodeSelected[Chapter]) -> None:
        if event.node.data is not None:
            self.open_chapter(event.node.data)

    def compose(self) -> ComposeResult:
        yield Header(show_clock=False)
        with Horizontal(id="body"):
            with Vertical(id="sidebar"):
                yield Input(placeholder=self.tr("Filter titles  /"), id="filter")
                yield Tree(self.book.title, id="toc")
            with Vertical(id="content"):
                with VerticalScroll(id="scroller"):
                    yield Markdown("", id="page")
                yield Static("", id="hint")
        yield Footer()

    def open_chapter(self, chapter: Chapter) -> None:
        """Update the displayed chapter, table of contents, and saved position."""
        chapter = self._resolve(chapter.index)
        if chapter is None:
            return
        markdown = self.book.markdown(chapter)
        self.current = chapter
        self.query_one("#page", Markdown).update(markdown)
        self.query_one("#scroller", VerticalScroll).scroll_home(animate=False)
        self.sub_title = f"{chapter.index + 1}/{len(self.book)}  {chapter.title}"
        words = len(markdown.split())
        hint = self.tr("{words} words. F1 help. Ctrl+F search.")
        self.query_one("#hint", Static).update(hint.format(words=words))
        node = self._toc_nodes.get(chapter.index)
        if node is not None:
            self._expand_ancestors(node)
            self.query_one("#toc", Tree).move_cursor(node)
        self._save_state()

    def action_next_chapter(self) -> None:
        self.open_chapter(self._step(1))

    def action_prev_chapter(self) -> None:
        self.open_chapter(self._step(-1))

    def _resolve(self, index: int) -> Chapter | None:
        """Return the next readable chapter, skipping table-of-contents groups."""
        for position in range(index, len(self.book)):
            chapter = self.book.chapter(position)
            if not chapter.group:
                return chapter
        return None

    def _step(self, delta: int) -> Chapter:
        """Return the next or previous readable chapter, skipping groups."""
        step = 1 if delta > 0 else -1
        stop = len(self.book) if step > 0 else -1
        for position in range(self.current.index + delta, stop, step):
            chapter = self.book.chapter(position)
            if not chapter.group:
                return chapter
        return self.book.chapter(max(0, min(self.current.index + delta, len(self.book) - 1)))

    def action_goto(self) -> None:
        screen = GotoScreen.for_language(self.tr)
        self.push_screen(screen(len(self.book), self.tr), self._jump)

    def action_filter(self) -> None:
        field = self.query_one("#filter", Input)
        field.focus()
        field.value = ""
        field.action_end()

    def action_search(self) -> None:
        screen = SearchScreen.for_language(self.tr)
        self.push_screen(screen(self.book, self.tr), self._jump)

    def action_help(self) -> None:
        screen = HelpScreen.for_language(self.tr)
        self.push_screen(screen(self.tr))

    def action_reload(self) -> None:
        self.book._cache.pop(self.current.index, None)
        self.open_chapter(self.current)
        message = self.tr("Chapter {number} reloaded.")
        self.notify(message.format(number=self.current.index + 1))

    def action_clear_filter(self) -> None:
        """Clear the filter or return focus to the chapter when it is empty."""
        field = self.query_one("#filter", Input)
        if field.value:
            field.value = ""
            return
        self.query_one("#scroller", VerticalScroll).focus()

    def action_swap_focus(self) -> None:
        scroller = self.query_one("#scroller", VerticalScroll)
        if scroller.has_focus:
            self.query_one("#toc", Tree).focus()
        else:
            scroller.focus()

    def action_next_theme(self) -> None:
        order = list(BUILTIN_THEMES)
        self.theme = (
            order[(order.index(self.theme) + 1) % len(order)]
            if self.theme in order
            else order[0]
        )
        self._save_state()

    def _jump(self, index: int | None) -> None:
        if index is not None:
            self.open_chapter(self.book.chapter(index))
            self.query_one("#scroller", VerticalScroll).focus()

    def on_input_changed(self, event: Input.Changed) -> None:
        if event.input.id == "filter":
            self._build_toc(self.book.filter_titles(event.value))

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id != "filter":
            return
        tree = self.query_one("#toc", Tree)
        if tree.root.children:
            node = next(node for node in self._walk(tree.root) if node.data is not None)
            tree.move_cursor(node.line)
            tree.select_node(node)

    def _expand_ancestors(self, node: TreeNode) -> None:
        """Expand parent nodes so the selected chapter stays visible."""
        parent = node.parent
        while parent is not None:
            parent.expand()
            parent = parent.parent

    def _walk(self, node: TreeNode) -> Iterator[TreeNode]:
        yield node
        for child in node.children:
            yield from self._walk(child)

    def _resolve_theme(self, wanted: str | None) -> str:
        return wanted if wanted in BUILTIN_THEMES else "textual-dark"

    def _load_state(self) -> dict:
        try:
            state = json.loads(self.state_path.read_text(encoding="utf-8"))
            if not isinstance(state, dict):
                return {}
            chapter = state.get("chapter", 0)
            if not isinstance(chapter, int) or chapter < 0:
                state["chapter"] = 0
            return state
        except (OSError, ValueError):
            return {}

    def _save_state(self) -> None:
        data = {
            "book": str(self.book.root),
            "chapter": self.current.index,
            "theme": self.theme,
        }
        try:
            self.state_path.parent.mkdir(parents=True, exist_ok=True)
            self.state_path.write_text(json.dumps(data), encoding="utf-8")
        except OSError as error:
            self.notify(self.tr("Could not save reader state: {error}").format(error=error))


class GotoScreen(ModalScreen[int | None]):
    """Ask for a chapter number and return its zero-based index."""

    BINDINGS = [Binding("escape", "dismiss(None)", "Cancel")]

    @classmethod
    def for_language(cls, translate: Callable[[str], str]) -> type[GotoScreen]:
        bindings = [Binding("escape", "dismiss(None)", translate("Cancel"))]
        return type(
            "LocalizedGotoScreen",
            (cls,),
            {"__module__": cls.__module__, "BINDINGS": bindings},
        )

    def __init__(self, total: int, translate: Callable[[str], str]) -> None:
        super().__init__()
        self.total = total
        self.tr = translate

    def compose(self) -> ComposeResult:
        with Vertical(classes="dialog"):
            title = self.tr("Go to chapter (1-{total})").format(total=self.total)
            yield Label(title, classes="dialog-title")
            yield Input(placeholder=self.tr("Chapter number"), id="goto-input")

    def on_mount(self) -> None:
        self.query_one(Input).focus()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        try:
            number = int(event.value.strip())
        except ValueError:
            self.notify(self.tr("Enter a chapter number."), severity="warning")
            return
        self.dismiss(number - 1)


class SearchScreen(ModalScreen[int | None]):
    """Search the book and return the selected chapter index."""

    BINDINGS = [Binding("escape", "dismiss(None)", "Cancel")]

    @classmethod
    def for_language(cls, translate: Callable[[str], str]) -> type[SearchScreen]:
        bindings = [Binding("escape", "dismiss(None)", translate("Cancel"))]
        return type(
            "LocalizedSearchScreen",
            (cls,),
            {"__module__": cls.__module__, "BINDINGS": bindings},
        )

    def __init__(self, book: Book, translate: Callable[[str], str]) -> None:
        super().__init__()
        self.book = book
        self.tr = translate
        self.hits: list[Hit] = []

    def compose(self) -> ComposeResult:
        with Vertical(classes="dialog"):
            yield Label(self.tr("Search the whole book"), classes="dialog-title")
            yield Input(placeholder=self.tr("Search term..."), id="search-input")
            yield Static("", id="search-empty")
            yield ListView(id="search-results")

    def on_mount(self) -> None:
        self.query_one(Input).focus()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        hits = self.book.search(event.value)
        self.hits = hits
        results = self.query_one("#search-results", ListView)
        results.clear()
        results.extend(
            ListItem(Label(f"{hit.chapter_title} :{hit.line}  {hit.excerpt}"))
            for hit in hits
        )
        empty = self.query_one("#search-empty", Static)
        if not hits:
            empty.update(self.tr("No matches found.") if event.value.strip() else "")
        else:
            empty.update(self.tr("{count} match(es)").format(count=len(hits)))
            results.focus()
            results.index = 0

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        position = event.list_view.index
        if position is not None and 0 <= position < len(self.hits):
            self.dismiss(self.hits[position].chapter_index)


class HelpScreen(ModalScreen[None]):
    """Show the keyboard reference."""

    BINDINGS = [Binding("escape,q,question_mark", "dismiss(None)", "Close")]

    @classmethod
    def for_language(cls, translate: Callable[[str], str]) -> type[HelpScreen]:
        bindings = [
            Binding(
                "escape,q,question_mark", "dismiss(None)", translate("Close")
            )
        ]
        return type(
            "LocalizedHelpScreen",
            (cls,),
            {"__module__": cls.__module__, "BINDINGS": bindings},
        )

    def __init__(self, translate: Callable[[str], str]) -> None:
        super().__init__()
        self.tr = translate

    def compose(self) -> ComposeResult:
        with Vertical(classes="dialog"):
            yield Label(self.tr("book-read - keyboard help"), classes="dialog-title")
            yield Static(self.tr(HELP_TEXT), id="help-body")
