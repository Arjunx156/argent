"""Find every project under the profile's roots and say which ones need attention."""

import subprocess
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path

SKIP = {"node_modules", ".venv", "venv", "__pycache__", "dist", "build", ".next", "target"}
# never let a repo's own config run code while we only look at it
GIT = ["git", "-c", "core.fsmonitor=false", "-c", "core.hooksPath=", "--no-optional-locks"]


@dataclass(frozen=True)
class Project:
    path: Path
    is_repo: bool
    branch: str = ""
    changed: int = 0
    ahead: int = 0
    behind: int = 0
    upstream: bool = False
    upstream_gone: bool = False
    remotes: tuple[str, ...] = ()
    last_commit: float | None = None
    error: str = ""

    @property
    def name(self) -> str:
        return self.path.name

    @property
    def problems(self) -> list[str]:
        if self.error:
            return [self.error]
        if not self.is_repo:
            return ["no git"]
        found: list[str] = []
        if self.changed:
            found.append(f"{self.changed} changed")
        if self.ahead:
            found.append(f"{self.ahead} unpushed")
        if self.behind:
            found.append(f"{self.behind} behind")
        if not self.remotes:
            found.append("no remote")
        elif self.upstream_gone:
            found.append("upstream gone")
        elif not self.upstream and self.last_commit is not None:
            found.append("branch not pushed")
        if self.last_commit is None:
            found.append("no commits")
        return found


def find_projects(roots: tuple[Path, ...]) -> list[Path]:
    """Repos one or two levels down; a folder with no repo inside counts as one project."""
    found: list[Path] = []
    for root in roots:
        for child in _folders(root):
            if _is_repo(child):
                found.append(child)
                continue
            nested = [g for g in _folders(child) if _is_repo(g)]
            found.extend(nested or [child])
    return found


def inspect(path: Path) -> Project:
    if not _is_repo(path):
        return Project(path, is_repo=False, last_commit=_newest_mtime(path))
    status = _git(path, "status", "--porcelain=v2", "--branch")
    if status.returncode != 0:
        return Project(path, is_repo=True, error=_first_line(status.stderr) or "git status failed")
    branch, upstream, compared, ahead, behind, changed = "", False, False, 0, 0, 0
    for line in status.stdout.splitlines():
        if line.startswith("# branch.head "):
            branch = line.split(" ", 2)[2]
        elif line.startswith("# branch.upstream "):
            upstream = True
        elif line.startswith("# branch.ab "):
            compared = True
            plus, minus = line.split(" ")[2:4]
            ahead, behind = int(plus), abs(int(minus))
        elif line and not line.startswith("#"):
            changed += 1
    remotes = tuple(_git(path, "remote").stdout.split())
    log = _git(path, "log", "-1", "--format=%ct")
    last = float(log.stdout.strip()) if log.returncode == 0 and log.stdout.strip() else None
    gone = upstream and not compared
    return Project(path, True, branch, changed, ahead, behind, upstream, gone, remotes, last)


def survey(roots: tuple[Path, ...]) -> list[Project]:
    paths = find_projects(roots)
    with ThreadPoolExecutor(max_workers=8) as pool:
        projects = list(pool.map(inspect, paths))
    return sorted(projects, key=lambda p: (not p.problems, -(p.last_commit or 0)))


def ago(stamp: float | None, now: float | None = None) -> str:
    if stamp is None:
        return ""
    seconds = max(0, (now or time.time()) - stamp)
    for unit, size in (("year", 31_536_000), ("month", 2_592_000), ("week", 604_800),
                       ("day", 86_400), ("hour", 3_600), ("minute", 60)):  # fmt: skip
        if seconds >= size:
            n = int(seconds // size)
            return f"{n} {unit}{'s' if n > 1 else ''} ago"
    return "just now"


def _folders(root: Path) -> list[Path]:
    try:
        entries = sorted(root.iterdir())
    except OSError:
        return []
    return [p for p in entries if p.is_dir() and not p.name.startswith(".") and p.name not in SKIP]


def _is_repo(path: Path) -> bool:
    return (path / ".git").exists()


def _git(path: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [*GIT, "-C", str(path), *args],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )


def _first_line(text: str) -> str:
    line = next((ln for ln in text.splitlines() if ln.strip()), "")
    return line.removeprefix("fatal: ").strip()


def _newest_mtime(path: Path) -> float | None:
    try:
        stamps = [p.stat().st_mtime for p in path.iterdir() if p.name not in SKIP]
    except OSError:
        return None
    return max(stamps, default=None)
