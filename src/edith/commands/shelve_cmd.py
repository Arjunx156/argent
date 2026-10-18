"""edith shelve and unshelve: park Claude config edith doesn't manage, and bring it back."""

import argparse
import shutil
from pathlib import Path
from typing import Any

from edith.paths import Env
from edith.ui import Out

INDEX = "index.txt"
PROTECTED = {"CLAUDE.md", "settings.json", "statusline.py", ".credentials.json", "projects"}


class ShelfError(ValueError):
    pass


def register(sub: Any) -> None:
    shelve = sub.add_parser("shelve", help="park unmanaged Claude config (skills, rules, agents)")
    shelve.add_argument("paths", nargs="*", help="paths under ~/.claude, like rules/ecc")
    shelve.set_defaults(run=run_shelve)
    unshelve = sub.add_parser("unshelve", help="put shelved config back")
    unshelve.add_argument("paths", nargs="+", help="paths as shelved, like rules/ecc")
    unshelve.set_defaults(run=run_unshelve)


def resolve(env: Env, raw: str) -> tuple[Path, Path, str]:
    rel = Path(raw.replace("\\", "/").removeprefix("~/.claude/").strip("/"))
    if not rel.parts or rel.is_absolute() or ".." in rel.parts:
        raise ShelfError(f"{raw}: give a path inside ~/.claude, like rules/ecc")
    if rel.parts[0] in PROTECTED or rel.parts[0] == INDEX:
        raise ShelfError(f"{raw}: edith or Claude Code owns that; it can't be shelved")
    ours = env.kit / "claude" / "skills"
    if rel.parts[0] == "skills" and len(rel.parts) > 1 and (ours / rel.parts[1]).is_dir():
        raise ShelfError(f"{raw}: that skill comes from the kit; remove it there instead")
    return env.claude / rel, env.shelf / rel, rel.as_posix()


def run_shelve(args: argparse.Namespace, env: Env, out: Out) -> int:
    if not args.paths:
        return list_shelf(env, out)
    index = read_index(env)
    for raw in args.paths:
        live, parked, rel = resolve(env, raw)
        if not live.exists() and not live.is_symlink():
            raise ShelfError(f"{raw}: nothing there to shelve")
        if parked.exists() or parked.is_symlink():
            raise ShelfError(f"{raw}: already on the shelf; unshelve it first")
        parked.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(live), str(parked))
        index.append(rel)
        write_index(env, index)
        out.tag("set", f"shelved {rel}  {out.dim('edith unshelve ' + rel + ' brings it back')}")
    out.line(out.dim("new Claude sessions start without it"))
    return 0


def run_unshelve(args: argparse.Namespace, env: Env, out: Out) -> int:
    index = read_index(env)
    for raw in args.paths:
        live, parked, rel = resolve(env, raw)
        if not parked.exists() and not parked.is_symlink():
            raise ShelfError(f"{raw}: not on the shelf; `edith shelve` lists it")
        if live.exists() or live.is_symlink():
            raise ShelfError(f"{raw}: something already lives there; move it first")
        live.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(parked), str(live))
        _prune(parked.parent, env.shelf)
        index = [e for e in index if e != rel]
        write_index(env, index)
        out.tag("set", f"unshelved {rel}")
    return 0


def list_shelf(env: Env, out: Out) -> int:
    shelved = read_index(env)
    out.heading("shelf")
    if not shelved:
        out.line(out.dim("  empty. `edith doctor` names what's worth parking"))
        return 0
    for rel in shelved:
        out.tag("info", rel)
    out.line()
    out.line(out.dim("bring one back with `edith unshelve <path>`"))
    return 0


def read_index(env: Env) -> list[str]:
    try:
        lines = (env.shelf / INDEX).read_text(encoding="utf-8").splitlines()
    except FileNotFoundError:
        return []
    return [line for line in lines if line.strip()]


def write_index(env: Env, entries: list[str]) -> None:
    env.shelf.mkdir(parents=True, exist_ok=True)
    lines = [f"{entry}\n" for entry in sorted(set(entries))]
    (env.shelf / INDEX).write_bytes("".join(lines).encode("utf-8"))


def _prune(folder: Path, stop: Path) -> None:
    while folder != stop and folder.is_dir() and not any(folder.iterdir()):
        folder.rmdir()
        folder = folder.parent
