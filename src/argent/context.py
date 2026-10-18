"""What Claude Code reads into every session before the first message, measured from disk.

Skills cost their name and description per session; the body loads only when a task
matches. Rules without `paths:` frontmatter, the standing orders, slash commands, agent
descriptions and enabled plugins load every time. Tokens are estimated at four characters
each, which is close for English prose and plenty for spotting what's heavy.
"""

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from argent.paths import Env

CHARS_PER_TOKEN = 4
# argent's own budget for always-loaded text, not a Claude Code limit: the kit itself needs
# about 2,700 tokens, and past this the skill list gets long enough to crowd descriptions out
TARGET = 6_000
FRONTMATTER = re.compile(r"\A---\r?\n(.*?)\r?\n---", re.DOTALL)


@dataclass(frozen=True)
class Source:
    name: str
    items: int
    chars: int

    @property
    def tokens(self) -> int:
        return self.chars // CHARS_PER_TOKEN


def measure(env: Env) -> list[Source]:
    claude = env.claude
    settings = _json(claude / "settings.json")
    off = {name for name, mode in settings.get("skillOverrides", {}).items() if mode == "off"}
    orders = claude / "CLAUDE.md"
    rules = claude / "rules"
    rule_files = sorted(rules.rglob("*.md")) if rules.is_dir() else []
    always = [p for p in rule_files if not scoped_rule(p)]
    skills = _skill_cards(claude / "skills", skip=off)
    roots = enabled_plugin_roots(env, settings)
    plugin_cards = [card for root in roots for card in _plugin_cards(root)]
    return [
        Source("standing orders", int(orders.is_file()), _size(orders)),
        Source("always-on rules", len(always), sum(_size(p) for p in always)),
        Source("skills", len(skills), sum(card_size(c) for c in skills)),
        Source("slash commands", *_cards(sorted((claude / "commands").glob("*.md")))),
        Source("agents", *_cards(sorted((claude / "agents").glob("*.md")))),
        Source("plugins", len(plugin_cards), sum(card_size(c) for c in plugin_cards)),
    ]


def desktop_plugins(env: Env) -> Source:
    """Skills from plugins installed in the Claude desktop app, which manages them itself."""
    root = env.appdata / "Claude" / "rpm"
    cards = sorted(root.rglob("SKILL.md")) if root.is_dir() else []
    return Source("desktop app plugins", len(cards), sum(card_size(c) for c in cards))


def enabled_plugin_roots(env: Env, settings: dict[str, Any]) -> list[Path]:
    enabled = {name for name, on in settings.get("enabledPlugins", {}).items() if on is True}
    installed = _json(env.claude / "plugins" / "installed_plugins.json").get("plugins", {})
    roots: list[Path] = []
    for name, versions in installed.items():
        if name in enabled and versions:
            roots.append(Path(versions[0]["installPath"]))
    return roots


def scoped_rule(path: Path) -> bool:
    """Rules with paths: in their frontmatter load only when matching files are touched."""
    head = path.read_text(encoding="utf-8", errors="replace")[:2000]
    match = FRONTMATTER.match(head)
    return bool(match and re.search(r"(?m)^paths:", match.group(1)))


def card_size(card: Path) -> int:
    """What a skill, command or agent costs per session: its name plus its description."""
    text = card.read_text(encoding="utf-8", errors="replace")
    match = FRONTMATTER.match(text)
    default = card.parent.name if card.name == "SKILL.md" else card.stem
    if not match:
        return len(default) + len(next(iter(text.splitlines()), ""))
    block = match.group(1)
    name = re.search(r"(?m)^name:(.*)$", block)
    found = re.search(r"(?ms)^description:(.*?)(?=^\S|\Z)", block)
    named = name.group(1).strip() if name else default
    return len(named) + (len(found.group(1).strip()) if found else 0)


def _skill_cards(root: Path, skip: set[str]) -> list[Path]:
    if not root.is_dir():
        return []
    return [
        p / "SKILL.md"
        for p in sorted(root.iterdir())
        if p.name not in skip and (p / "SKILL.md").is_file()
    ]


def _plugin_cards(root: Path) -> list[Path]:
    cards = list(root.rglob("SKILL.md"))
    for folder in ("commands", "agents"):
        cards += sorted((root / folder).glob("*.md"))
    return cards


def _cards(paths: list[Path]) -> tuple[int, int]:
    return len(paths), sum(card_size(p) for p in paths)


def _size(path: Path) -> int:
    return path.stat().st_size if path.is_file() else 0


def _json(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except (FileNotFoundError, ValueError):
        return {}
