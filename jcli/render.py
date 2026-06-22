"""Helpers for turning JSON values into pretty, bracket-free terminal labels."""

from __future__ import annotations

from typing import Any

from rich.text import Text

# Type-based color theme. These are Rich/Textual color names.
STYLE_KEY = "bold #82aaff"      # keys
STYLE_STRING = "#c3e88d"        # string values
STYLE_NUMBER = "#f78c6c"        # int / float
STYLE_BOOL = "#c792ea"          # true / false
STYLE_NULL = "italic #717cb4"   # null
STYLE_COUNT = "#546e7a"         # the "3 items" hint
STYLE_OBJECT = "bold #ffcb6b"   # object node names
STYLE_ARRAY = "bold #89ddff"    # array node names


def is_container(value: Any) -> bool:
    """True if the value is a dict or list (i.e. an expandable node)."""
    return isinstance(value, (dict, list))


def _count_hint(value: Any) -> str:
    """A human description of how many children a container has."""
    n = len(value)
    if isinstance(value, dict):
        noun = "field" if n == 1 else "fields"
    else:
        noun = "item" if n == 1 else "items"
    return f"{n} {noun}"


def scalar_text(value: Any) -> Text:
    """Render a leaf (non-container) value with type-appropriate color."""
    if value is None:
        return Text("null", style=STYLE_NULL)
    if isinstance(value, bool):
        return Text("true" if value else "false", style=STYLE_BOOL)
    if isinstance(value, (int, float)):
        return Text(str(value), style=STYLE_NUMBER)
    # Strings (and any fallback) — shown without surrounding quotes for calm reading.
    return Text(str(value), style=STYLE_STRING)


STYLE_MATCH = "black on #ffcb6b"  # highlighted search match


def highlight(label: Any, query: str) -> Text:
    """Return a copy of ``label`` with every occurrence of ``query`` highlighted."""
    text = label.copy() if isinstance(label, Text) else Text(str(label))
    if not query:
        return text
    haystack = text.plain.lower()
    needle = query.lower()
    start = 0
    while True:
        idx = haystack.find(needle, start)
        if idx == -1:
            break
        text.stylize(STYLE_MATCH, idx, idx + len(needle))
        start = idx + len(needle)
    return text


def label_for(key: Any, value: Any, *, is_root: bool = False) -> Text:
    """Build the label shown on a tree node.

    For containers we show the name plus a soft "N items" hint.
    For leaves we show "name: value".
    """
    text = Text()

    if is_container(value):
        name = "root" if is_root else str(key)
        style = STYLE_OBJECT if isinstance(value, dict) else STYLE_ARRAY
        text.append(name, style=style)
        text.append("   ")
        text.append(_count_hint(value), style=STYLE_COUNT)
        return text

    # Leaf node: "key  value"
    text.append(str(key), style=STYLE_KEY)
    text.append(":  ")
    text.append_text(scalar_text(value))
    return text
