"""The skill library: shallow mirrors of public skill repos, indexed and searchable.

Mirrors are untrusted data. Cloning never runs their hooks, follows their symlinks, pulls
submodules or LFS objects, and nothing inside a mirror is ever executed.
"""

import os
import re
import subprocess
import tomllib
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from pathlib import Path

from argent.paths import Env

Git = Callable[[list[str]], subprocess.CompletedProcess[str]]
FRONTMATTER = re.compile(r"\A---\r?\n(.*?)\r?\n---", re.DOTALL)


class LibraryError(RuntimeError):
    pass


@dataclass(frozen=True)
class Repo:
    name: str
    why: str

    @property
    def folder(self) -> str:
        return self.name.replace("/", "__")


@dataclass(frozen=True)
class Card:
    name: str
    description: str
    repo: str
    path: Path


def load_repos(path: Path) -> list[Repo]:
    try:
        data = tomllib.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise LibraryError(f"{path} is missing") from None
    repos = [Repo(r["name"], r.get("why", "")) for r in data.get("repo", [])]
    for repo in repos:
        if not re.fullmatch(r"[\w.-]+/[\w.-]+", repo.name):
            raise LibraryError(f"{repo.name!r} isn't an owner/name GitHub repo")
    return repos


def library_dir(env: Env) -> Path:
    return env.claude / "skill-library"


def safe_git(env: Env) -> list[str]:
    """git, configured so a mirror can't run anything on this machine."""
    no_hooks = env.state / "no-hooks"
    no_hooks.mkdir(parents=True, exist_ok=True)
    return [
        "git",
        "-c", f"core.hooksPath={no_hooks}",
        "-c", "core.symlinks=false",
        "-c", "core.fsmonitor=false",
        "-c", "core.longpaths=true",
        "-c", "protocol.allow=never",
        "-c", "protocol.https.allow=always",
        "-c", "advice.detachedHead=false",
    ]  # fmt: skip


def run_git(argv: list[str]) -> subprocess.CompletedProcess[str]:
    env = {**os.environ, "GIT_LFS_SKIP_SMUDGE": "1", "GIT_TERMINAL_PROMPT": "0"}
    return subprocess.run(
        argv,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=env,
        check=False,
        timeout=600,
    )


def sync_repo(env: Env, repo: Repo, git: Git = run_git) -> str:
    """Clone or fast-forward one mirror. Returns new, pulled or ok."""
    base = safe_git(env)
    target = library_dir(env) / repo.folder
    url = f"https://github.com/{repo.name}.git"
    if not (target / ".git").is_dir():
        target.parent.mkdir(parents=True, exist_ok=True)
        clone = [*base, "clone", "--quiet", "--depth", "1", "--no-recurse-submodules", url]
        _ok(git([*clone, str(target)]), repo, "clone")
        return "new"
    before = git([*base, "-C", str(target), "rev-parse", "HEAD"]).stdout.strip()
    _ok(
        git([*base, "-C", str(target), "fetch", "--quiet", "--depth", "1", "origin"]), repo, "fetch"
    )
    # mirrors are read-only, so jump straight to whatever upstream has now
    reset = [*base, "-C", str(target), "reset", "--quiet", "--hard", "FETCH_HEAD"]
    _ok(git(reset), repo, "reset")
    after = git([*base, "-C", str(target), "rev-parse", "HEAD"]).stdout.strip()
    return "ok" if before == after else "pulled"


def _ok(done: subprocess.CompletedProcess[str], repo: Repo, step: str) -> None:
    if done.returncode != 0:
        last = next((ln for ln in reversed(done.stderr.splitlines()) if ln.strip()), "no output")
        raise LibraryError(f"{repo.name}: git {step} failed: {last.strip()}")


def read_card(path: Path, repo: str, root: Path) -> Card:
    text = path.read_text(encoding="utf-8", errors="replace")
    meta = frontmatter(text)
    name = meta.get("name") or path.parent.name
    return Card(name, meta.get("description", ""), repo, path.relative_to(root))


def frontmatter(text: str) -> dict[str, str]:
    """name and description from YAML frontmatter, enough for how skills write them:
    plain, quoted, folded (>) or literal (|) scalars, wrapped over indented lines."""
    match = FRONTMATTER.match(text)
    if not match:
        return {}
    found: dict[str, str] = {}
    key: str | None = None
    for line in match.group(1).splitlines():
        top = re.match(r"^([A-Za-z0-9_-]+):\s*(.*)$", line)
        if top:
            key = top.group(1) if top.group(1) in ("name", "description") else None
            if key:
                found[key] = top.group(2).strip()
        elif key and line.startswith((" ", "\t")):
            found[key] = f"{found[key]} {line.strip()}".strip()
    return {k: _unquote(re.sub(r"^[>|][-+]?\s*", "", v)) for k, v in found.items()}


def _unquote(value: str) -> str:
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
        inner = value[1:-1]
        return inner.replace("''", "'") if value[0] == "'" else inner.replace('\\"', '"')
    return value


def index(env: Env, repos: Iterable[Repo]) -> list[Card]:
    root = library_dir(env)
    cards: list[Card] = []
    for repo in repos:
        folder = root / repo.folder
        if not folder.is_dir():
            continue
        for path in sorted(folder.rglob("SKILL.md")):
            if ".git" not in path.relative_to(folder).parts:
                cards.append(read_card(path, repo.name, root))
    return cards


def write_index(env: Env, repos: list[Repo], cards: list[Card], stamp: str) -> Path:
    lines = [
        "# Skill library",
        "",
        f"{len(cards)} skills from {len(repos)} repos, synced {stamp} by `argent library sync`.",
        "Nothing here loads into Claude. Read a skill in full before copying it into the kit.",
        "",
    ]
    for repo in repos:
        mine = [c for c in cards if c.repo == repo.name]
        if not mine:
            continue
        lines += ["", f"## {repo.name}", "", repo.why, "", "| Skill | What it's for |", "|---|---|"]
        for card in mine:
            link = card.path.as_posix().replace(" ", "%20")
            what = _short(card.description).replace("|", "\\|")
            lines.append(f"| [{card.name}]({link}) | {what} |")
    path = library_dir(env) / "INDEX.md"
    path.write_bytes(("\n".join(lines) + "\n").encode("utf-8"))
    return path


def find(cards: Iterable[Card], words: list[str]) -> list[Card]:
    terms = [w.lower() for w in words]
    hits = [
        c for c in cards if all(t in f"{c.name} {c.description} {c.repo}".lower() for t in terms)
    ]
    # a word in the name beats a word buried in a description
    return sorted(hits, key=lambda c: (-sum(t in c.name.lower() for t in terms), c.name))


def _short(text: str, words: int = 24) -> str:
    parts = text.split()
    short = " ".join(parts[:words])
    return short + " ..." if len(parts) > words else short
