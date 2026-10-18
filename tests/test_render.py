from collections.abc import Callable
from pathlib import Path

import pytest

from edith.render import TemplateError, render, tools_block
from edith.tools import Detection, load_manifest

KIT = Path(__file__).resolve().parents[1] / "kit"
CONTEXT = {"me.name": "Test Person"}


def nothing(_tool: str) -> bool:
    return False


def everything(_tool: str) -> bool:
    return True


def test_values_are_substituted() -> None:
    assert render("by {{ me.name }}.", CONTEXT, nothing, "t") == "by Test Person."


def test_unknown_values_fail_with_the_line() -> None:
    with pytest.raises(TemplateError, match=r"t:2: unknown value \{\{ me.phone \}\}"):
        render("ok\n{{ me.phone }}", CONTEXT, nothing, "t")


def test_sections_follow_detection() -> None:
    text = "a{{#has x}}+x{{/has}}{{^has x}}-x{{/has}}b"
    assert render(text, CONTEXT, everything, "t") == "a+xb"
    assert render(text, CONTEXT, nothing, "t") == "a-xb"


def test_standalone_section_tags_leave_no_blank_lines() -> None:
    text = "top\n{{#has x}}\nonly with x\n{{/has}}\n{{^has x}}\nonly without\n{{/has}}\nend\n"
    assert render(text, CONTEXT, everything, "t") == "top\nonly with x\nend\n"
    assert render(text, CONTEXT, nothing, "t") == "top\nonly without\nend\n"


def test_nested_sections_are_refused() -> None:
    with pytest.raises(TemplateError, match="nest"):
        render("{{#has a}}{{#has b}}x{{/has}}{{/has}}", CONTEXT, everything, "t")


def test_malformed_tags_are_caught() -> None:
    with pytest.raises(TemplateError, match="malformed"):
        render("{{#has a}}never closed", CONTEXT, everything, "t")


def test_tools_block_drops_missing_tools_and_empty_areas() -> None:
    manifest = load_manifest(KIT / "tools.toml")
    block = tools_block(manifest, Detection({"rg": "x", "uv": "x"}))
    assert block.splitlines() == [
        "  - Search: `rg` for text.",
        "  - Python: `uv` for Pythons, environments and tools; never global pip.",
    ]


@pytest.mark.parametrize("has", [everything, nothing])
def test_the_real_standing_orders_render_both_ways(has: Callable[[str], bool]) -> None:
    context = {
        "me.name": "N",
        "me.email": "e@x",
        "me.github": "g",
        "me.about": "a",
        "me.university": "u",
        "tools": "  - Search: `rg` for text.",
        "projects.roots": "`~/code`",
        "edith.repo": "C:/edith",
    }
    text = (KIT / "claude" / "CLAUDE.md.tmpl").read_text(encoding="utf-8")
    rendered = render(text, context, has, "CLAUDE.md")
    assert "{{" not in rendered
    assert "\n\n\n" not in rendered
    assert ("tectonic -X compile" in rendered) == (has is everything)
