"""The interactive Textual app: a collapsible, bracket-free JSON tree."""

from __future__ import annotations

from typing import Any, NamedTuple

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Vertical, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Footer, Header, Input, Static, Tree
from textual.widgets.tree import TreeNode

from rich.syntax import Syntax

from .formatting import looks_like_html, pretty_html
from .render import highlight, is_container, label_for, scalar_text


class NodeData(NamedTuple):
    """What we attach to every tree node: its key and its raw value."""

    key: str
    value: Any


def _add_one_level(node: TreeNode, value: Any) -> None:
    """Attach only the *immediate* children of ``value`` to ``node``.

    Containers are added empty (not yet populated) so we never materialize the
    whole document at once — that is the key to staying fast on big files. Each
    child is filled in lazily when the user expands it (see
    ``JSONTreeApp.on_tree_node_expanded``).
    """
    if isinstance(value, dict):
        items = value.items()
    elif isinstance(value, list):
        # Use the index as the "key" for array elements.
        items = enumerate(value)
    else:
        return

    for key, child in items:
        label = label_for(key, child)
        if is_container(child):
            child_node = node.add(label, data=NodeData(str(key), child))
            # Empty containers have nothing to expand into.
            if len(child) == 0:
                child_node.allow_expand = False
        else:
            node.add_leaf(label, data=NodeData(str(key), child))


def count_nodes(value: Any) -> int:
    """Total number of nodes (containers + leaves) in a JSON value."""
    if isinstance(value, dict):
        return 1 + sum(count_nodes(v) for v in value.values())
    if isinstance(value, list):
        return 1 + sum(count_nodes(v) for v in value)
    return 1


def search_paths(data: Any, query: str) -> list[list]:
    """Find every match for ``query`` (case-insensitive) in the JSON data.

    Returns a list of *paths* (each a list of dict-keys / list-indices from the
    root) in document order. A path matches if the key contains the query, or if
    a leaf value's text contains it. Searching the raw data — not the rendered
    widgets — is what lets search work even though most nodes aren't built yet.
    """
    needle = query.lower()
    results: list[list] = []
    seen: set[tuple] = set()

    def add(path: list) -> None:
        key = tuple(path)
        if key not in seen:
            seen.add(key)
            results.append(path)

    def walk(value: Any, path: list) -> None:
        if isinstance(value, dict):
            for k, v in value.items():
                child_path = path + [k]
                if needle in str(k).lower():
                    add(child_path)
                walk(v, child_path)
        elif isinstance(value, list):
            for i, v in enumerate(value):
                walk(v, path + [i])
        else:
            if needle in str(value).lower():
                add(path)

    walk(data, [])
    return results


class ValueScreen(ModalScreen):
    """A centered, scrollable panel showing the full value of a leaf."""

    BINDINGS = [
        Binding("escape", "close", "Close"),
        Binding("enter", "close", "Close"),
        Binding("q", "close", "Close"),
        Binding("f", "toggle_format", "Raw / formatted"),
    ]

    CSS = """
    ValueScreen {
        align: center middle;
    }
    #dialog {
        width: 80%;
        max-width: 120;
        height: 70%;
        max-height: 30;
        background: $panel;
        border: round $accent;
        padding: 0 1;
    }
    #dialog-title {
        width: 100%;
        height: 1;
        color: $accent;
        text-style: bold;
        padding: 0 1;
    }
    #dialog-body {
        height: 1fr;
        border-top: solid $accent 30%;
        border-bottom: solid $accent 30%;
        padding: 1;
    }
    #dialog-hint {
        width: 100%;
        height: 1;
        color: $text-muted;
        text-align: center;
    }
    """

    def __init__(self, key: str, value: Any) -> None:
        super().__init__()
        self._key = key
        self._value = value
        self._can_format = looks_like_html(value)
        # Default to the formatted view when we can format; otherwise raw.
        self._formatted = self._can_format

    def compose(self) -> ComposeResult:
        with Vertical(id="dialog"):
            yield Static(self._title_text(), id="dialog-title")
            with VerticalScroll(id="dialog-body"):
                yield Static(self._content(), id="dialog-content")
            yield Static(self._hint_text(), id="dialog-hint")

    def _title_text(self) -> str:
        if self._can_format:
            mode = "formatted" if self._formatted else "raw"
            return f"{self._key}   ({mode})"
        return self._key

    def _hint_text(self) -> str:
        base = "↑↓ scroll · Esc / Enter to close"
        if self._can_format:
            return base + " · f raw/formatted"
        return base

    def _content(self):
        """The renderable for the value, honoring the current format mode."""
        if self._formatted and self._can_format and isinstance(self._value, str):
            return Syntax(
                pretty_html(self._value),
                "html",
                theme="ansi_dark",
                word_wrap=True,
                background_color="default",
            )
        return scalar_text(self._value)

    def action_toggle_format(self) -> None:
        if not self._can_format:
            return
        self._formatted = not self._formatted
        self.query_one("#dialog-content", Static).update(self._content())
        self.query_one("#dialog-title", Static).update(self._title_text())

    def action_close(self) -> None:
        self.dismiss()


class JSONTreeApp(App):
    """A terminal app that renders JSON as a navigable tree."""

    CSS = """
    Screen {
        background: $surface;
    }
    Tree {
        padding: 1 2;
    }
    #search {
        dock: bottom;
        display: none;
        border: round $accent;
    }
    #search.visible {
        display: block;
    }
    """

    BINDINGS = [
        Binding("q", "quit", "Quit"),
        Binding("e", "expand_all", "Expand all"),
        Binding("c", "collapse_all", "Collapse all"),
        Binding("slash", "search", "Search"),
        Binding("n", "next_match", "Next match"),
        Binding("N", "prev_match", "Prev match"),
        Binding("escape", "cancel_search", "Cancel search", show=False),
    ]

    # Above this many total nodes, "expand all" is refused — it would
    # materialize the whole document and defeat lazy loading.
    MAX_EXPAND_NODES = 20_000

    def __init__(self, data: Any, title: str = "jsonbonsai") -> None:
        super().__init__()
        self._data = data
        self._title = title
        self._node_count = count_nodes(data)
        self._matches: list[list] = []
        self._match_index = -1
        self._query = ""
        # The node currently highlighted, and its un-highlighted label.
        self._hl_node: TreeNode | None = None
        self._hl_label: Any = None

    def compose(self) -> ComposeResult:
        yield Header(show_clock=False)
        tree: Tree = Tree(
            label_for("root", self._data, is_root=True),
            data=NodeData("root", self._data),
        )
        # Populate only the first level; deeper levels load on expand.
        _add_one_level(tree.root, self._data)
        tree.root.expand()
        tree.show_root = True
        tree.guide_depth = 3
        yield tree
        yield Input(placeholder="Search keys & values…  (Enter to find, Esc to cancel)", id="search")
        yield Footer()

    def on_mount(self) -> None:
        self.title = self._title
        self.sub_title = f"{self._node_count:,} nodes · ↑↓ navigate · Enter open · / search · n/N matches · q quit"

    def on_tree_node_expanded(self, event: Tree.NodeExpanded) -> None:
        """Lazily fill in a container's children the first time it opens."""
        node = event.node
        node_data = node.data
        if node_data is None or not is_container(node_data.value):
            return
        # Empty children list means this node has not been populated yet.
        if len(node.children) == 0 and len(node_data.value) > 0:
            _add_one_level(node, node_data.value)

    def on_tree_node_selected(self, event: Tree.NodeSelected) -> None:
        """Enter on a leaf pops up its full value; containers expand as usual."""
        node_data = event.node.data
        if node_data is None:
            return
        if is_container(node_data.value):
            return  # let the Tree handle expand/collapse
        self.push_screen(ValueScreen(node_data.key, node_data.value))

    def _materialize_all(self, node: TreeNode) -> None:
        """Recursively populate every descendant (used only by expand-all)."""
        node_data = node.data
        if (
            node_data is not None
            and is_container(node_data.value)
            and len(node.children) == 0
            and len(node_data.value) > 0
        ):
            _add_one_level(node, node_data.value)
        for child in node.children:
            self._materialize_all(child)

    def action_expand_all(self) -> None:
        if self._node_count > self.MAX_EXPAND_NODES:
            self.notify(
                f"Too large to expand all ({self._node_count:,} nodes). "
                "Expand sections individually instead.",
                severity="warning",
                timeout=5,
            )
            return
        root = self.query_one(Tree).root
        self._materialize_all(root)
        root.expand_all()

    def action_collapse_all(self) -> None:
        # Collapse everything, then re-open the root so the view isn't empty.
        root = self.query_one(Tree).root
        root.collapse_all()
        root.expand()

    # ----- search -------------------------------------------------------

    def action_search(self) -> None:
        search = self.query_one("#search", Input)
        search.add_class("visible")
        search.focus()

    def action_cancel_search(self) -> None:
        search = self.query_one("#search", Input)
        if search.has_class("visible"):
            search.remove_class("visible")
            self.query_one(Tree).focus()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id != "search":
            return
        query = event.value.strip()
        search = self.query_one("#search", Input)
        search.remove_class("visible")
        self.query_one(Tree).focus()
        self._clear_highlight()
        if not query:
            return
        self._query = query
        self._matches = search_paths(self._data, query)
        if not self._matches:
            self.notify(f"No matches for {query!r}", severity="warning")
            self._match_index = -1
            return
        self._match_index = 0
        self._goto_current_match(query)

    def action_next_match(self) -> None:
        if not self._matches:
            return
        self._match_index = (self._match_index + 1) % len(self._matches)
        self._goto_current_match()

    def action_prev_match(self) -> None:
        if not self._matches:
            return
        self._match_index = (self._match_index - 1) % len(self._matches)
        self._goto_current_match()

    def _goto_current_match(self, query: str | None = None) -> None:
        path = self._matches[self._match_index]
        node = self._reveal_path(path)
        if node is not None:
            self._apply_highlight(node)
        label = f" for {query!r}" if query else ""
        self.notify(f"Match {self._match_index + 1} of {len(self._matches)}{label}")

    def _reveal_path(self, path: list) -> TreeNode | None:
        """Expand the tree along ``path`` (loading lazily) and return the node."""
        tree = self.query_one(Tree)
        node = tree.root
        for segment in path:
            node_data = node.data
            if (
                node_data is not None
                and is_container(node_data.value)
                and len(node.children) == 0
                and len(node_data.value) > 0
            ):
                _add_one_level(node, node_data.value)
            node.expand()
            target = next(
                (c for c in node.children if c.data and c.data.key == str(segment)),
                None,
            )
            if target is None:
                return None  # path no longer resolvable; bail quietly
            node = target
        # Defer until the tree has recomputed its line layout after expanding,
        # otherwise the node's line isn't known yet. move_cursor positions the
        # highlight WITHOUT emitting NodeSelected (which would pop the dialog).
        target_node = node

        def focus_match() -> None:
            tree.move_cursor(target_node)
            tree.scroll_to_node(target_node)

        self.call_after_refresh(focus_match)
        return target_node

    def _apply_highlight(self, node: TreeNode) -> None:
        """Highlight the matched text in ``node``, restoring any previous one."""
        self._clear_highlight()
        self._hl_node = node
        self._hl_label = node.label
        node.set_label(highlight(node.label, self._query))

    def _clear_highlight(self) -> None:
        if self._hl_node is not None and self._hl_label is not None:
            self._hl_node.set_label(self._hl_label)
        self._hl_node = None
        self._hl_label = None
