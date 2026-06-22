"""Test suite for jcli: pure helpers + interactive app behavior."""

from __future__ import annotations

import pytest

from jcli.app import (
    JSONTreeApp,
    ValueScreen,
    count_nodes,
    search_paths,
)
from jcli.formatting import looks_like_html, pretty_html
from jcli.render import highlight, label_for


SAMPLE = {
    "name": "Ada",
    "age": 36,
    "active": True,
    "nickname": None,
    "tags": ["math", "logic"],
    "address": {"city": "London", "zip": "W1"},
    "bio_html": "<p>Hello <b>world</b></p>",
}


# --------------------------------------------------------------------------
# pure helpers
# --------------------------------------------------------------------------

def test_count_nodes():
    # 7 top-level + tags(list)+2 items + address(dict)+2 items = 1 root counted? no:
    # count_nodes counts every container and leaf. Verify against a known shape.
    assert count_nodes({"a": 1}) == 2          # dict + 1 leaf
    assert count_nodes([1, 2, 3]) == 4          # list + 3 leaves
    assert count_nodes(42) == 1                  # bare scalar
    assert count_nodes(SAMPLE) == 12


def test_search_paths_value_and_key():
    # value match
    assert search_paths(SAMPLE, "ada") == [["name"]]
    # nested value match
    assert search_paths(SAMPLE, "london") == [["address", "city"]]
    # key match
    assert ["address"] in search_paths(SAMPLE, "address")
    # list element value
    assert search_paths(SAMPLE, "logic") == [["tags", 1]]


def test_search_paths_case_insensitive_and_nomatch():
    assert search_paths(SAMPLE, "LONDON") == [["address", "city"]]
    assert search_paths(SAMPLE, "nonexistent") == []


def test_search_paths_dedupes_key_and_value_overlap():
    data = {"city": "city hall"}  # both key and value contain "city"
    # path to that single node should appear once, not twice
    assert search_paths(data, "city") == [["city"]]


def test_looks_like_html():
    assert looks_like_html("<p>hi</p>") is True
    assert looks_like_html("<br/>") is True
    assert looks_like_html("plain text") is False
    assert looks_like_html("a < b and c > d") is False
    assert looks_like_html(123) is False


def test_pretty_html_indents():
    out = pretty_html("<div><p>hi</p></div>")
    lines = out.splitlines()
    assert lines[0] == "<div>"
    assert lines[1] == "  <p>"          # indented one level
    assert "</div>" in lines[-1]


def test_pretty_html_falls_back_on_garbage():
    # should never raise; returns something string-like
    assert isinstance(pretty_html("<<<not really html"), str)


def test_label_for_container_hint_no_brackets():
    text = label_for("address", {"a": 1, "b": 2}).plain
    assert "address" in text and "2 fields" in text
    assert "{" not in text and "}" not in text
    arr = label_for("tags", [1, 2, 3]).plain
    assert "3 items" in arr and "[" not in arr


def test_label_for_leaf_strips_quotes():
    assert label_for("name", "Ada").plain == "name:  Ada"   # no surrounding quotes
    assert label_for("nickname", None).plain == "nickname:  null"


def test_highlight_marks_query():
    text = highlight(label_for("name", "Ada"), "ada")
    # the matched span should carry the match style
    spans = [s for s in text.spans if "ffcb6b" in str(s.style)]
    assert spans, "expected a highlighted span"


# --------------------------------------------------------------------------
# interactive app behavior
# --------------------------------------------------------------------------

async def test_lazy_loading_only_builds_visible_nodes():
    big = {"items": [{"id": i, "v": {"x": i}} for i in range(2000)]}

    def widget_count(node):
        return 1 + sum(widget_count(c) for c in node.children)

    app = JSONTreeApp(big)
    async with app.run_test() as pilot:
        tree = app.query_one("Tree")
        # at open, only root + its single child level is built
        assert widget_count(tree.root) < 10
        # expand 'items' -> 2000 children appear, but NOT their grandchildren
        items = tree.root.children[0]
        items.expand()
        await pilot.pause()
        assert len(items.children) == 2000
        assert len(items.children[0].children) == 0  # grandchildren still lazy


async def test_enter_on_leaf_opens_popup_container_does_not():
    app = JSONTreeApp(SAMPLE)
    async with app.run_test() as pilot:
        tree = app.query_one("Tree")
        await pilot.pause()
        name_node = next(c for c in tree.root.children if c.data.key == "name")
        tree.move_cursor(name_node)
        await pilot.pause()
        await pilot.press("enter")
        await pilot.pause()
        assert isinstance(app.screen, ValueScreen)
        assert app.screen._value == "Ada"
        await pilot.press("escape")
        await pilot.pause()
        assert not isinstance(app.screen, ValueScreen)
        # a container should expand, not pop
        addr = next(c for c in tree.root.children if c.data.key == "address")
        tree.move_cursor(addr)
        await pilot.pause()
        await pilot.press("enter")
        await pilot.pause()
        assert not isinstance(app.screen, ValueScreen)


async def test_html_value_format_toggle():
    app = JSONTreeApp(SAMPLE)
    async with app.run_test() as pilot:
        tree = app.query_one("Tree")
        await pilot.pause()
        bio = next(c for c in tree.root.children if c.data.key == "bio_html")
        tree.move_cursor(bio)
        await pilot.pause()
        await pilot.press("enter")
        await pilot.pause()
        scr = app.screen
        assert isinstance(scr, ValueScreen)
        assert scr._can_format and scr._formatted        # HTML defaults to formatted
        await pilot.press("f")
        await pilot.pause()
        assert scr._formatted is False                    # toggled to raw
        # raw must equal the exact source value
        assert scr._value == SAMPLE["bio_html"]


async def test_search_jumps_to_matches_and_highlights():
    data = {"users": [{"name": "Alice"}, {"name": "Bob"}, {"name": "Alvin"}]}
    app = JSONTreeApp(data)
    async with app.run_test() as pilot:
        tree = app.query_one("Tree")
        await pilot.pause()
        await pilot.press("slash")
        await pilot.pause()
        for ch in "al":
            await pilot.press(ch)
        await pilot.press("enter")
        await pilot.pause()
        await pilot.pause()
        # "al" matches Alice and Alvin
        assert len(app._matches) == 2
        assert not isinstance(app.screen, ValueScreen)     # no popup from a leaf jump
        first = tree.cursor_node
        assert "al" in str(first.data.value).lower()
        # current match label carries a highlight span
        assert any("ffcb6b" in str(s.style) for s in first.label.spans)
        # navigate next
        await pilot.press("n")
        await pilot.pause()
        await pilot.pause()
        assert app._match_index == 1
        assert "al" in str(tree.cursor_node.data.value).lower()


async def test_search_no_match_notifies_and_keeps_state():
    app = JSONTreeApp(SAMPLE)
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("slash")
        await pilot.pause()
        for ch in "zzz":
            await pilot.press(ch)
        await pilot.press("enter")
        await pilot.pause()
        assert app._matches == []
        assert app._match_index == -1
