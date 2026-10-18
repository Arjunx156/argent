"""The kit as deploy targets: every file in kit/ mapped to where it lives on the machine."""

import json
from dataclasses import dataclass
from functools import partial
from pathlib import Path
from typing import Any

from edith.deploy import Build, Target
from edith.merge import claude_settings, editor_settings, managed_block, terminal_settings
from edith.paths import Env
from edith.profile import Profile
from edith.render import render, tools_block
from edith.tools import Detection, Manifest

TEMPLATE = ".tmpl"
FOLIO_VERSION = "1.0.0"
EDITORS = ("Code", "Cursor", "Antigravity", "Antigravity IDE")
TERMINALS = (
    "Packages/Microsoft.WindowsTerminal_8wekyb3d8bbwe/LocalState/settings.json",
    "Packages/Microsoft.WindowsTerminalPreview_8wekyb3d8bbwe/LocalState/settings.json",
    "Microsoft/Windows Terminal/settings.json",
)


@dataclass(frozen=True)
class Kit:
    targets: list[Target]
    mirror: list[Path]


def build_kit(env: Env, profile: Profile, manifest: Manifest, found: Detection) -> Kit:
    context = template_context(env, profile, manifest, found)
    targets: list[Target] = []
    mirror: list[Path] = []

    def file(src: Path, dest: Path) -> None:
        if src.name.endswith(TEMPLATE):
            text = src.read_text(encoding="utf-8")
            name = src.relative_to(env.kit).as_posix()
            content = render(text, context, found.has, name).encode("utf-8")
            dest = dest.with_name(dest.name.removesuffix(TEMPLATE))
        else:
            content = src.read_bytes()
        targets.append(Target(dest, pretty(env, dest), constant(content)))

    claude = env.kit / "claude"
    file(claude / "CLAUDE.md.tmpl", env.claude / "CLAUDE.md")
    file(claude / "statusline.py", env.claude / "statusline.py")
    for skill in sorted(p for p in (claude / "skills").iterdir() if p.is_dir()):
        dest_dir = env.claude / "skills" / skill.name
        mirror.append(dest_dir)
        for src in files_in(skill):
            file(src, dest_dir / src.relative_to(skill))

    folio = env.appdata / "typst" / "packages" / "local" / "folio" / FOLIO_VERSION
    mirror.append(folio)
    for src in files_in(claude / "skills" / "folio" / "typst" / "folio"):
        file(src, folio / src.name)

    statusline = (env.claude / "statusline.py").as_posix()
    settings = env.claude / "settings.json"
    build = partial(claude_settings, statusline=statusline, chimes=profile.chimes)
    targets.append(Target(settings, pretty(env, settings), build, whole=False))

    config = env.kit / "config"
    file(config / "starship.toml", env.home / ".config" / "starship.toml")

    block = (config / "profile.ps1").read_text(encoding="utf-8")
    for shell in ("PowerShell", "WindowsPowerShell"):
        dest = env.documents / shell / "profile.ps1"
        build = partial(managed_block, body=block, supersedes=("tadashi",))
        targets.append(Target(dest, pretty(env, dest), build, whole=False))

    theme = read_json(config / "terminal.json")
    for rel in TERMINALS:
        dest = env.localappdata / rel
        if dest.is_file():
            build = partial(terminal_settings, theme=theme)
            targets.append(Target(dest, pretty(env, dest), build, whole=False))

    wanted = read_json(config / "editor.json")
    for app in EDITORS:
        user = env.appdata / app / "User"
        if user.is_dir():
            dest = user / "settings.json"
            build = partial(editor_settings, wanted=wanted)
            targets.append(Target(dest, pretty(env, dest), build, whole=False))
    return Kit(targets, mirror)


def template_context(
    env: Env, profile: Profile, manifest: Manifest, found: Detection
) -> dict[str, str]:
    roots = [f"`{root.as_posix()}`" for root in profile.roots]
    return {
        **profile.context(),
        "tools": tools_block(manifest, found),
        "projects.roots": join_words(roots) or "no configured folders",
        "edith.repo": env.repo.as_posix(),
    }


def constant(content: bytes) -> Build:
    return lambda _current: content


def files_in(folder: Path) -> list[Path]:
    return sorted(p for p in folder.rglob("*") if p.is_file() and "__pycache__" not in p.parts)


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def join_words(items: list[str]) -> str:
    if len(items) <= 2:
        return " and ".join(items)
    return ", ".join(items[:-1]) + " and " + items[-1]


def pretty(env: Env, path: Path) -> str:
    for base, label in (
        (env.claude, "~/.claude"),
        (env.appdata, "%APPDATA%"),
        (env.localappdata, "%LOCALAPPDATA%"),
        (env.documents, "Documents"),
        (env.home, "~"),
    ):
        if path.is_relative_to(base):
            return f"{label}/{path.relative_to(base).as_posix()}"
    return path.as_posix()
