"""Optional pretty-printing for long leaf values (currently HTML/XML).

This only affects how a value is *displayed* in the popup. The raw value is
always kept intact and reachable via the popup's raw/formatted toggle — nothing
here mutates the underlying data.
"""

from __future__ import annotations

from html.parser import HTMLParser

# Tags that never have children / closing tags.
_VOID_TAGS = {
    "area", "base", "br", "col", "embed", "hr", "img", "input",
    "link", "meta", "param", "source", "track", "wbr",
}


def looks_like_html(value: object) -> bool:
    """Heuristic: does this string look like HTML/XML markup?"""
    if not isinstance(value, str):
        return False
    text = value.strip()
    return text.startswith("<") and ">" in text and ("</" in text or "/>" in text)


class _Prettifier(HTMLParser):
    """Re-emits parsed HTML with indentation, one tag/text run per line."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.lines: list[str] = []
        self.depth = 0

    def _emit(self, text: str) -> None:
        self.lines.append("  " * self.depth + text)

    @staticmethod
    def _attrs(attrs) -> str:
        out = []
        for key, val in attrs:
            if val is None:
                out.append(f" {key}")
            else:
                out.append(f' {key}="{val}"')
        return "".join(out)

    def handle_starttag(self, tag, attrs):
        self._emit(f"<{tag}{self._attrs(attrs)}>")
        if tag not in _VOID_TAGS:
            self.depth += 1

    def handle_startendtag(self, tag, attrs):
        self._emit(f"<{tag}{self._attrs(attrs)}/>")

    def handle_endtag(self, tag):
        if tag not in _VOID_TAGS:
            self.depth = max(0, self.depth - 1)
        self._emit(f"</{tag}>")

    def handle_data(self, data):
        text = data.strip()
        if text:
            self._emit(text)


def pretty_html(value: str) -> str:
    """Indent HTML/XML for readability. Falls back to the original on any error."""
    parser = _Prettifier()
    try:
        parser.feed(value)
        parser.close()
    except Exception:
        return value
    return "\n".join(parser.lines) if parser.lines else value
