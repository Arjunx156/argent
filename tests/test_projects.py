import shutil
import subprocess
from pathlib import Path

import pytest

from argent.projects import ago, find_projects, inspect, survey

pytestmark = pytest.mark.skipif(not shutil.which("git"), reason="needs git")


def git(cwd: Path, *args: str) -> None:
    subprocess.run(
        ["git", "-c", "user.name=t", "-c", "user.email=t@x", *args],
        cwd=cwd,
        check=True,
        capture_output=True,
    )


def repo(path: Path, commits: int = 1) -> Path:
    path.mkdir(parents=True)
    git(path, "init", "-q", "-b", "main")
    for n in range(commits):
        (path / f"f{n}.txt").write_text(str(n), encoding="utf-8")
        git(path, "add", "-A")
        git(path, "commit", "-q", "-m", f"c{n}")
    return path


@pytest.fixture
def roots(tmp_path: Path) -> Path:
    root = tmp_path / "projects"
    pushed = repo(root / "pushed")
    remote = tmp_path / "remote.git"
    git(tmp_path, "init", "-q", "--bare", "-b", "main", str(remote))
    git(pushed, "remote", "add", "origin", str(remote))
    git(pushed, "push", "-q", "-u", "origin", "main")

    ahead = root / "ahead"
    git(tmp_path, "clone", "-q", str(remote), str(ahead))
    (ahead / "more.txt").write_text("x", encoding="utf-8")
    git(ahead, "add", "-A")
    git(ahead, "commit", "-q", "-m", "local only")

    dirty = repo(root / "dirty")
    (dirty / "f0.txt").write_text("edited", encoding="utf-8")
    (dirty / "new.txt").write_text("new", encoding="utf-8")

    repo(root / "Hackathons" / "nested")
    (root / "plain").mkdir()
    (root / "plain" / "notes.md").write_text("no git", encoding="utf-8")
    (root / "node_modules").mkdir()
    return root


def test_finds_repos_one_or_two_deep_and_plain_folders(roots: Path) -> None:
    names = sorted(p.relative_to(roots).as_posix() for p in find_projects((roots,)))
    assert names == ["Hackathons/nested", "ahead", "dirty", "plain", "pushed"]


def test_status_reads_changes_ahead_and_remotes(roots: Path) -> None:
    assert inspect(roots / "pushed").problems == []
    assert inspect(roots / "ahead").problems == ["1 unpushed"]
    dirty = inspect(roots / "dirty")
    assert dirty.problems == ["2 changed", "no remote"]
    assert dirty.branch == "main"
    assert inspect(roots / "plain").problems == ["no git"]


def test_survey_puts_what_needs_you_first(roots: Path) -> None:
    projects = survey((roots,))
    assert projects[-1].name == "pushed"
    assert all(p.problems for p in projects[:-1])


def test_a_vanished_upstream_is_named(roots: Path, tmp_path: Path) -> None:
    pushed = roots / "pushed"
    git(pushed, "branch", "-q", "--set-upstream-to=origin/main")
    git(pushed, "update-ref", "-d", "refs/remotes/origin/main")
    assert inspect(pushed).problems == ["upstream gone"]


def test_missing_roots_are_simply_empty(tmp_path: Path) -> None:
    assert find_projects((tmp_path / "nope",)) == []


@pytest.mark.parametrize(
    ("seconds", "text"),
    [(5, "just now"), (120, "2 minutes ago"), (3600, "1 hour ago"), (86_400 * 3, "3 days ago")],
)
def test_ago_reads_like_a_person(seconds: int, text: str) -> None:
    assert ago(1000.0, now=1000.0 + seconds) == text
