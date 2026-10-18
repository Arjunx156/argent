"""argent library: mirror public skill repos, and search them."""

import argparse
from datetime import datetime
from typing import Any

from argent.library import (
    LibraryError,
    Repo,
    find,
    index,
    library_dir,
    load_repos,
    sync_repo,
    write_index,
)
from argent.paths import Env
from argent.ui import Out

SHOWN = 25


def register(sub: Any) -> None:
    parser = sub.add_parser("library", help="mirror public skill repos and search them")
    parser.add_argument("action", nargs="?", choices=("sync", "find"), help="sync or find")
    parser.add_argument("words", nargs="*", help="with find: words every match must contain")
    parser.set_defaults(run=run)


def run(args: argparse.Namespace, env: Env, out: Out) -> int:
    repos = load_repos(env.kit / "library.toml")
    if args.action == "sync":
        return sync(env, repos, out)
    if args.action == "find":
        if not args.words:
            raise LibraryError("find needs words to look for, like: argent library find pdf")
        return search(env, repos, args.words, out)
    return status(env, repos, out)


def sync(env: Env, repos: list[Repo], out: Out) -> int:
    out.heading(f"library  {out.dim(str(library_dir(env)))}")
    failed = 0
    for repo in repos:
        try:
            result = sync_repo(env, repo)
        except LibraryError as err:
            failed += 1
            out.tag("fail", str(err))
            continue
        out.tag({"new": "new", "pulled": "update"}.get(result, "ok"), repo.name)
    cards = index(env, repos)
    stamp = datetime.now().strftime("%Y-%m-%d %H:%M")
    path = write_index(env, repos, cards, stamp)
    out.line()
    out.line(f"{len(cards)} skills indexed  {out.dim(str(path))}")
    out.line(out.dim("search with `argent library find <words>`; nothing here loads into Claude"))
    return 1 if failed else 0


def search(env: Env, repos: list[Repo], words: list[str], out: Out) -> int:
    hits = find(index(env, repos), words)
    out.heading(f"library  {out.dim(f'{len(hits)} match ' + ' '.join(words))}")
    if not hits:
        synced = (library_dir(env) / "INDEX.md").is_file()
        out.line(out.dim("  nothing matches" if synced else "  empty; run `argent library sync`"))
        return 0
    for card in hits[:SHOWN]:
        out.tag("info", f"{card.name}  {out.dim(card.repo)}")
        if card.description:
            out.line(f"         {card.description[:110]}")
        out.line(f"         {out.dim(str(library_dir(env) / card.path))}")
    if len(hits) > SHOWN:
        out.line(out.dim(f"  and {len(hits) - SHOWN} more; add a word to narrow it"))
    out.line()
    out.line(out.dim("read the SKILL.md in full, then copy the folder into kit/claude/skills"))
    return 0


def status(env: Env, repos: list[Repo], out: Out) -> int:
    root = library_dir(env)
    present = [r for r in repos if (root / r.folder / ".git").is_dir()]
    out.heading(f"library  {out.dim(str(root))}")
    if not present:
        out.line(out.dim("  not synced yet; `argent library sync` mirrors the repos"))
        return 0
    cards = index(env, repos)
    out.line(f"  {len(cards)} skills from {len(present)} of {len(repos)} repos")
    out.line(out.dim("  `argent library find <words>` searches them; `sync` updates them"))
    return 0
