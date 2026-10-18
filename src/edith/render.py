"""A deliberately tiny template language for the kit.

    {{ me.name }}                 a value from the context; unknown keys are errors
    {{#has tectonic}}..{{/has}}   kept only when the tool was detected
    {{^has tectonic}}..{{/has}}   kept only when it wasn't

A section tag alone on its line takes the line with it, so sections leave no blank lines.
"""

import re
from collections.abc import Callable

from edith.tools import Detection, Manifest

STANDALONE = re.compile(r"(?m)^[ \t]*(\{\{[#^/]has[^}]*\}\})[ \t]*\r?\n")
SECTION = re.compile(r"\{\{([#^])has ([^}]+?)\}\}(.*?)\{\{/has\}\}", re.DOTALL)
VALUE = re.compile(r"\{\{\s*([\w.]+)\s*\}\}")
BRANCH = re.compile(r"\{\{[#^]has ([^}]+?)\}\}")


class TemplateError(ValueError):
    pass


def render(text: str, context: dict[str, str], has: Callable[[str], bool], name: str) -> str:
    text = STANDALONE.sub(r"\1", text)

    def section(match: re.Match[str]) -> str:
        sign, tool, body = match.group(1), match.group(2).strip(), match.group(3)
        if "{{#has" in body or "{{^has" in body:
            raise TemplateError(f"{name}: sections can't nest (inside has {tool})")
        return body if has(tool) == (sign == "#") else ""

    text = SECTION.sub(section, text)

    def value(match: re.Match[str]) -> str:
        key = match.group(1)
        if key not in context:
            line = text.count("\n", 0, match.start()) + 1
            raise TemplateError(f"{name}:{line}: unknown value {{{{ {key} }}}}")
        return context[key]

    text = VALUE.sub(value, text)
    leftover = text.find("{{")
    if leftover != -1:
        line = text.count("\n", 0, leftover) + 1
        raise TemplateError(f"{name}:{line}: unclosed or malformed tag")
    return text


def tools_block(manifest: Manifest, found: Detection, indent: str = "  ") -> str:
    """The standing orders' tool lines, one per area, from detected tools only."""
    lines: list[str] = []
    for area in manifest.areas:
        claims = [
            t.claim for t in manifest.tools if t.area == area.name and t.claim and found.has(t.cmd)
        ]
        if not claims:
            continue
        note = f"; {area.note}" if area.note else ""
        lines.append(f"{indent}- {area.name}: {', '.join(claims)}{note}.")
    return "\n".join(lines)


def branched_tools(text: str) -> set[str]:
    """Tools a template changes its wording for."""
    return {name.strip() for name in BRANCH.findall(text)}
